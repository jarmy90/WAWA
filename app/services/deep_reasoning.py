"""Servicio de razonamiento profundo por la ventana OX Alpha (iteración 015).

Coordina las tareas P0 reservadas (reformulación, coherencia, red-team,
comparación de variantes) a través del gateway OmniRoute con el slug
EXACTO verificado. Propiedades inmutables:

1. PUERTA DETERMINISTA: solo corre si ox_alpha_status() == AVAILABLE
   (gateway activo + dentro de la ventana hasta 2026-08-27 + slug
   verificado). En cualquier otro caso devuelve ausencia NEUTRAL sin
   llamar a nada y sin declarar uso de OX Alpha.
2. REGISTRO HONESTO: cada intento queda en llm_call_log con
   requested_model, actual_model, actual_provider, routing_strategy,
   fallback_used=False (nunca hay sustitución silenciosa), fallback_reason,
   latencia, tokens, reported_cost/estimated_cost/cost_source y
   billing_verified=False; response_is_external=True solo en éxito real.
3. SIN FABRICACIÓN: si el gateway falla NO se sustituye por mock ni se
   presenta salida sintética como OX Alpha; se registra el error y se
   continúa sin la aportación (ausencia neutral).
4. NUNCA EVIDENCIA: el resultado lleva label MODEL_* e is_evidence=False.
   El llamador no puede usarlo para subir proven_demand, aprobar
   finalistas, crear grupos de evidencia ni iniciar PRE_CYCLE: esos
   caminos siguen siendo exclusivamente deterministas + evidencia web.
5. LÍMITES: tope diario de tareas profundas y recorte defensivo del
   expediente enviado (sin secretos, datos personales ni bases completas).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from app.core.errors import ProviderUnavailableError, ValidationError
from app.core.ox_alpha import (
    DEEP_TASKS,
    TASK_LABEL,
    _SYSTEM_BASE,
    build_coherence_prompt,
    build_red_team_prompt,
    build_reformulation_prompt,
    build_variation_comparison_prompt,
    deep_task_gate,
    ox_alpha_status,
)
from app.models.llm_call import LLMCallRecord


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_iso() -> str:
    return date.today().isoformat()


class DeepReasoningService:
    def __init__(self, settings: Any, providers: Any, llm_calls: Any) -> None:
        self.settings = settings
        self.providers = providers  # ProviderManager (usa .omniroute)
        self.llm_calls = llm_calls  # LLMCallRepository (append-only)

    # ------------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        """Estado visible en la interfaz (sin secretos)."""
        st = ox_alpha_status(self.settings)
        st["daily_tasks_used"] = self.llm_calls.count_since(_today_iso(), provider="omniroute")
        st["daily_task_limit"] = int(getattr(self.settings, "ox_alpha_daily_task_limit", 40))
        st["tasks_reserved"] = list(DEEP_TASKS)
        st["gateway_endpoint"] = getattr(self.providers.omniroute, "base_url", None) if hasattr(self.providers, "omniroute") else None
        return st

    # ------------------------------------------------------------------
    def catalog_check(self) -> dict[str, Any]:
        """Intenta identificar 'OX Alpha' contra el catálogo REAL del gateway.

        Nunca inventa slugs: si el gateway no responde o no hay coincidencia
        inequívoca, la identidad sigue siendo OX_ALPHA_UNVERIFIED."""
        provider = getattr(self.providers, "omniroute", None)
        result: dict[str, Any] = {
            "identity": ox_alpha_status(self.settings)["identity"],
            "gateway_enabled": bool(provider and provider.available()),
            "catalog_fetched": False,
            "models_total": None,
            "matches": [],
            "verified": False,
            "reason": "",
        }
        if not (provider and provider.available()):
            result["reason"] = "Gateway desactivado: no se puede consultar el catálogo."
            return result
        try:
            catalog = provider.list_models()
        except Exception as exc:  # noqa: BLE001 — fallo => catálogo no disponible
            result["reason"] = f"Catálogo no accesible ({type(exc).__name__}): {str(exc)[:200]}"
            return result
        items = catalog.get("data") if isinstance(catalog, dict) else catalog
        ids = []
        for item in items or []:
            mid = item.get("id") if isinstance(item, dict) else item
            if isinstance(mid, str):
                ids.append(mid)
        result["catalog_fetched"] = True
        result["models_total"] = len(ids)
        needle = (self.settings.ox_alpha_slug or "").strip().lower()
        matches = [
            mid for mid in ids
            if ("ox" in mid.lower() and "alpha" in mid.lower())
            or (needle and needle != "auto" and mid.lower() == needle)
        ]
        result["matches"] = matches[:20]
        configured = needle and needle != "auto"
        if configured:
            exact = [m for m in matches if m.lower() == needle]
            if exact:
                result["verified"] = True
                result["identity"] = exact[0]
                result["reason"] = "Slug configurado verificado textualmente en el catálogo."
            else:
                result["reason"] = (
                    "El slug configurado NO aparece en el catálogo actual: "
                    "la identidad permanece sin verificar."
                )
                result["identity"] = "OX_ALPHA_UNVERIFIED"
        else:
            result["reason"] = (
                "Sin slug configurado. Coincidencias heurísticas ('ox'+'alpha') listadas; "
                "fija OX_ALPHA_SLUG con el slug EXACTO tras revisarlas para verificar."
                if matches else
                "Sin slug configurado y ninguna coincidencia 'ox'+'alpha' en el catálogo."
            )
        return result

    # ------------------------------------------------------------------
    def run_deep_task(
        self,
        task: str,
        concept: dict[str, Any],
        *,
        opportunity_id: str | None = None,
        concepts_for_comparison: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Ejecuta una tarea P0 por la ventana. Ausencia neutral ante bloqueo."""
        gate = deep_task_gate(self.settings, task)
        base = {
            "task": task,
            "output_label": TASK_LABEL.get(task, "HIPÓTESIS SIN VERIFICAR"),
            "is_evidence": False,
            "response_is_external": False,
            "response_is_synthetic": False,
            "routing_strategy": "omniroute-deep-priority",
        }
        if not gate["can_use"]:
            # Bloqueo ANTES de llamar: no se registra llamada (no hubo), no se fabrica.
            return {
                **base,
                "status": gate["state"],
                "can_use": False,
                "identity": gate["identity"],
                "expires_at": gate.get("expires_at"),
                "used_model": None,
                "result": None,
                "reason": gate["reason"],
            }

        used_today = self.llm_calls.count_since(_today_iso(), provider="omniroute")
        limit = int(getattr(self.settings, "ox_alpha_daily_task_limit", 40))
        if used_today >= limit:
            return {
                **base,
                "status": "DAILY_LIMIT_REACHED",
                "used_model": None,
                "result": None,
                "reason": f"Tope diario de tareas profundas alcanzado ({limit}). Ausencia neutral.",
            }

        prompt, schema = self._build_prompt(task, concept, concepts_for_comparison)
        max_chars = int(getattr(self.settings, "ox_alpha_max_input_chars", 24_000))
        prompt = prompt[:max_chars]

        requested = self.settings.ox_alpha_slug.strip()
        started_at = _now()
        try:
            response = self.providers.omniroute.generate(
                prompt,
                system=_SYSTEM_BASE,
                task=f"deep_{task}",
                output_schema=schema,
                temperature=0.3,
                model=requested,
            )
        except ProviderUnavailableError as exc:
            record = LLMCallRecord(
                provider="omniroute",
                action=f"ox_alpha:{task}",
                opportunity_id=opportunity_id,
                requested_model=requested,
                actual_model=None,
                response_status="error",
                fallback_used=False,
                fallback_reason=str(exc.message)[:500],
                routing_strategy="omniroute-deep-priority",
                response_is_external=False,
                response_is_synthetic=False,
                notes="FALLO registrado: ausencia neutral; sin salida sintética.",
            )
            saved = self.llm_calls.create(record)
            return {
                **base,
                "status": "UNAVAILABLE",
                "call_id": saved["id"],
                "used_model": None,
                "result": None,
                "reason": f"OX Alpha no disponible ({str(exc.message)[:180]}). Ausencia NEUTRAL: "
                          "no se fabrica salida ni se sustituye silenciosamente.",
            }
        except Exception as exc:  # noqa: BLE001 — cualquier otro fallo también es neutro
            record = LLMCallRecord(
                provider="omniroute",
                action=f"ox_alpha:{task}",
                opportunity_id=opportunity_id,
                requested_model=requested,
                actual_model=None,
                response_status="error",
                fallback_used=False,
                fallback_reason=f"{type(exc).__name__}: {str(exc)[:400]}",
                routing_strategy="omniroute-deep-priority",
                response_is_external=False,
                response_is_synthetic=False,
                notes="FALLO registrado: ausencia neutral; sin salida sintética.",
            )
            saved = self.llm_calls.create(record)
            return {
                **base,
                "status": "UNAVAILABLE",
                "call_id": saved["id"],
                "used_model": None,
                "result": None,
                "reason": f"Fallo inesperado ({type(exc).__name__}). Ausencia NEUTRAL.",
            }

        usage = response.usage or {}
        estimated = response.cost_estimate_usd or None
        record = LLMCallRecord(
            provider="omniroute",
            action=f"ox_alpha:{task}",
            opportunity_id=opportunity_id,
            requested_model=response.model,
            actual_model=response.actual_model or response.model,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            reported_cost=response.reported_cost,
            estimated_cost=float(estimated) if estimated else None,
            cost_source=response.cost_source,
            billing_verified=False,
            latency_ms=response.latency_ms,
            retry_count=response.retry_count,
            fallback_used=False,
            response_status="ok",
            routing_strategy="omniroute-deep-priority",
            response_is_external=True,
            response_is_synthetic=False,
            notes=(response.notes or "")[:2_000],
        )
        saved = self.llm_calls.create(record)

        structured = response.structured
        if task == "reformulation" and isinstance(structured, dict):
            variants = structured.get("variants") or []
            for v in variants:
                if isinstance(v, dict):
                    v.setdefault("provenance_label", "HIPÓTESIS SIN VERIFICAR")
                    v["is_evidence"] = False
        return {
            **base,
            "status": "OK",
            "call_id": saved["id"],
            "requested_model": response.model,
            "actual_model": response.actual_model or response.model,
            "actual_provider": "omniroute-gateway",
            "fallback_used": False,  # nunca hay sustitución silenciosa
            "fallback_reason": None,
            "latency_ms": response.latency_ms,
            "reported_cost": response.reported_cost,
            "estimated_cost": float(estimated) if estimated else None,
            "cost_source": response.cost_source,
            "billing_verified": False,
            "started_at": started_at,
            "used_model": response.actual_model or response.model,
            "result": structured if structured is not None else {"text": response.text},
            "deterministic_review_pending": True,
            "reason": "Respuesta registrada como razonamiento de modelo: requiere validación determinista posterior.",
        }

    # ------------------------------------------------------------------
    def _build_prompt(self, task: str, concept: dict[str, Any], extra: list[dict[str, Any]] | None):
        if task == "reformulation":
            return build_reformulation_prompt(concept)
        if task == "coherence_check":
            return build_coherence_prompt(concept)
        if task == "red_team":
            return build_red_team_prompt(concept)
        if task == "variation_comparison":
            return build_variation_comparison_prompt(extra or [])
        raise ValidationError(f"Tarea profunda desconocida: {task}")
