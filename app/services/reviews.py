"""Comité de contraste para oportunidades finalistas (iteración 005).

Flujo:
1.  Una oportunidad con evaluación interna >= umbral entra en la cola de
    revisión (automáticamente al aprobarse, o manualmente).
2.  Se genera un EXPEDIENTE idéntico para todos los revisores
    (`data/external_reviews/opportunity_{id}/review_packet.md`).
3.  Se importan revisiones (TXT/Markdown) desde el panel: raw conservado,
    parsing estructurado con allowlist, hash anti-duplicado.
4.  La síntesis agrega recomendaciones y riesgos SIN convertir opiniones en
    evidencia; el consenso se etiqueta como basado en opinión o en evidencia.
5.  Si la ventana expira sin revisiones, el sistema continúa (neutral) si la
    configuración lo permite.

SEGURIDAD: el contenido importado es DATO no confiable. Nunca ejecuta nada,
nunca cambia modos, presupuesto ni autoriza producción. El parsing solo lee
claves en una allowlist y señala posibles inyecciones sin interpretarlas.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, PayloadTooLargeError, ProviderUnavailableError, ValidationError
from app.core.logging import get_logger
from app.core.security import validate_extension
from app.models.decision_log import DecisionLog
from app.models.external_review import (
    KNOWN_PROVIDERS,
    PARSED_FIELDS,
    REVIEWER_HEADERS,
    VALID_RECOMMENDATIONS,
    CombinedReviewImportIn,
    ExternalReview,
    ReviewImportIn,
    ReviewSynthesis,
)
from app.models.llm_call import CostSource, LLMCallRecord
from app.providers.manager import ProviderManager
from app.repositories import Repos

RECOMMENDATION_LABELS = {
    "REJECT": "Rechazar",
    "MORE_RESEARCH": "Más investigación",
    "SMALL_EXPERIMENT": "Experimento pequeño",
    "PRIORITY_EXPERIMENT": "Experimento prioritario",
}

_INJECTION_PHRASES = (
    "ignore previous instructions",
    "ignore all previous",
    "ignore the instructions",
    "you are now",
    "override your instructions",
    "disregard",
    "act as the system",
    "system prompt",
    "reveal your instructions",
    "forget your",
)

_URL_RE = re.compile(r"https?://\S+")

_NORMALIZED_REVIEW_PROMPT = """Actúa como revisor empresarial independiente y adversarial.

Tu trabajo no es apoyar la propuesta, sino determinar si merece más investigación o una prueba limitada.

Utiliza exclusivamente el expediente proporcionado.

No inventes demanda, cifras, competidores, precios ni capacidades.

Separa hechos, inferencias y supuestos.

Evalúa:

1. Claridad y gravedad del problema.
2. Cliente objetivo.
3. Evidencia de demanda.
4. Disposición a pagar.
5. Acceso al cliente.
6. Competencia.
7. Diferenciación.
8. Modelo de ingresos.
9. Margen.
10. Automatización.
11. Coste y velocidad de construcción.
12. Dependencia de terceros.
13. Riesgo legal y operativo.
14. Calidad del experimento.
15. Supuesto más débil.
16. Evidencia crítica que falta.
17. Alternativa mejor.
18. Motivo principal para continuar.
19. Motivo principal para rechazar.

Devuelve:

- recommendation:
  REJECT
  MORE_RESEARCH
  SMALL_EXPERIMENT
  PRIORITY_EXPERIMENT

- confidence: 0-100
- strongest_evidence
- weakest_assumption
- missing_evidence
- primary_risk
- suggested_improvement
- cheaper_experiment
- kill_condition
- final_reasoning_summary

No confundas una idea original con una oportunidad comercial."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sanitize_text(value: str, max_len: int = 5_000) -> str:
    """Elimina caracteres de control (excepto saltos de línea) y acota tamaño."""
    cleaned = "".join(ch for ch in value if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    return cleaned.strip()[:max_len]


class ReviewService:
    def __init__(self, settings: Settings, repos: Repos, engine=None, providers: ProviderManager | None = None) -> None:
        self.settings = settings
        self.repos = repos
        self.engine = engine
        self.providers = providers
        self.log = get_logger("reviews")
        self._dir: Path = settings.external_reviews_dir

    # ==================================================================
    # Cola de finalistas
    # ==================================================================
    def auto_queue(self, opportunity_id: str, *, note: str | None = None) -> dict | None:
        """Cola automática al aprobarse una oportunidad (silenciosa).

        Si se supera el máximo semanal o el umbral, NO lanza error: registra
        un learning record y devuelve None (el pipeline nunca debe romperse
        por la cola de revisión).
        """
        try:
            return self.queue_opportunity(opportunity_id, note=note, quiet=True)
        except (NotFoundError, ValidationError) as exc:
            self.repos.discovery.add_learning_record(
                kind="review_queue",
                pattern=f"finalista no entró en cola de revisión: {exc.message}",
                source="auto_queue",
            )
            return None

    def queue_opportunity(
        self, opportunity_id: str, *, note: str | None = None, quiet: bool = False, allow_demo: bool = False
    ) -> dict:
        """Coloca una finalista en la cola de revisión externa (determinista).

        ``allow_demo`` es una vía SOLO para la demostración sintética: fuerza la
        cola aunque la puntuación no alcance el umbral, con registro auditable.
        La ruta normal de la API nunca la usa.
        """
        opportunity = self.repos.opportunities.get(opportunity_id)
        if opportunity is None:
            raise NotFoundError("Oportunidad no encontrada.")
        evaluation = self.repos.evaluations.get(opportunity_id)
        if evaluation is None:
            raise ValidationError("La oportunidad no tiene evaluación interna; no puede entrar en revisión.")
        demo_override = allow_demo and opportunity.source == "demo-review"
        if evaluation.final_score < self.settings.review_min_internal_score and not demo_override:
            raise ValidationError(
                f"Puntuación interna {evaluation.final_score:.1f} por debajo del umbral "
                f"({self.settings.review_min_internal_score:.1f}) para revisión externa."
            )
        # Iteración 009: mínimo de GRUPOS de evidencia independientes.
        if not demo_override and self.settings.review_min_evidence_groups > 0:
            groups = int(getattr(evaluation, "independent_evidence_count", 0) or 0)
            if groups < self.settings.review_min_evidence_groups:
                raise ValidationError(
                    f"La oportunidad tiene {groups} grupo(s) de evidencia independiente(s); "
                    f"se requieren al menos {self.settings.review_min_evidence_groups} para el comité externo."
                )
        if self.repos.reviews.queue_item(opportunity_id):
            return self.repos.reviews.queue_item(opportunity_id)  # type: ignore[return-value]

        # Máximo de finalistas por semana (ventana deslizante de 7 días).
        week_ago = (_now_dt() - timedelta(days=7)).isoformat()
        queued_this_week = self.repos.reviews.count_queued_since(week_ago)
        if queued_this_week >= self.settings.review_max_finalists_per_week:
            if quiet:
                return None
            raise ValidationError(
                f"Máximo semanal de finalistas alcanzado ({self.settings.review_max_finalists_per_week}). "
                "Espera a la próxima ventana o prioriza manualmente."
            )

        deadline = (_now_dt() + timedelta(hours=self.settings.review_window_hours)).isoformat()
        review_required = self._review_required(evaluation)
        item = self.repos.reviews.enqueue(
            opportunity_id,
            internal_score=evaluation.final_score,
            window_deadline=deadline,
            review_required=review_required,
            note=note,
        )
        override_note = (
            f" | SOBRECEDIDA DEMO: puntuación {evaluation.final_score:.1f} < umbral "
            f"{self.settings.review_min_internal_score:g}; solo para la demostración sintética "
            "del comité de contraste. Esta vía no existe en la API normal."
            if demo_override
            else ""
        )
        self._log(
            agent="review_queue",
            opportunity_id=opportunity_id,
            summary=f"Finalista en cola de revisión externa (umbral {self.settings.review_min_internal_score:g}). "
                    f"Ventana: {self.settings.review_window_hours}h.{override_note}",
            decision="queued",
            model_or_method="deterministic rule",
        )
        return item

    def queue_status(self) -> dict:
        """Estado de la cola con información de oportunidad, revisiones y síntesis."""
        self._expire_pending()
        items = self.repos.reviews.list_queue()
        now = _now_dt()
        rows = []
        for item in items:
            opp = self.repos.opportunities.get(item["opportunity_id"])
            reviews = self.repos.reviews.reviews_for(item["opportunity_id"])
            synthesis = self.repos.reviews.get_synthesis(item["opportunity_id"])
            # Estado por proveedor visible en el panel (solo los 3 manuales + automáticos).
            per_provider: dict[str, str] = {}
            for r in reviews:
                prov = r["provider"] or "unknown"
                if prov not in per_provider:
                    per_provider[prov] = r["status"]
            # Ventana restante en horas (0 si caducó).
            window_remaining_hours: float | None = None
            if item.get("window_deadline"):
                try:
                    deadline = datetime.fromisoformat(item["window_deadline"])
                    remaining = (deadline - now).total_seconds() / 3600
                    window_remaining_hours = round(max(0.0, remaining), 1)
                except ValueError:
                    window_remaining_hours = None
            rows.append(
                {
                    **item,
                    "title": opp.title if opp else "—",
                    "status_label": opp.status.value if opp else "—",
                    "reviews_count": len(reviews),
                    "valid_reviews_count": sum(1 for r in reviews if r["status"] in ("valid", "partial")),
                    "recommendations": [r["recommendation"] for r in reviews if r["recommendation"]],
                    "synthesis": synthesis,
                    "per_provider": per_provider,
                    "window_remaining_hours": window_remaining_hours,
                    "committee_state": self._committee_state(item, reviews),
                }
            )
        return {
            "threshold": self.settings.review_min_internal_score,
            "max_per_week": self.settings.review_max_finalists_per_week,
            "window_hours": self.settings.review_window_hours,
            "continue_without_review": self.settings.review_continue_without_review,
            "min_evidence_groups": self.settings.review_min_evidence_groups,
            "packet_version": self.settings.review_packet_version,
            "items": rows,
            "count": len(rows),
        }

    @staticmethod
    def _committee_state(item: dict, reviews: list[dict]) -> str:
        """Etiqueta visual determinista: pendiente/importada/procesada/parcial/inválida/caducada/continuada."""
        status = item.get("status")
        if status == "continued":
            return "continuada_sin_revision"
        if status == "reviewed":
            return "revisada"
        if status == "pending" and item.get("window_deadline"):
            try:
                if item["window_deadline"] <= _now():
                    return "caducada"
            except (TypeError, ValueError):
                pass
        if not reviews:
            return "pendiente"
        valid = [r for r in reviews if r["status"] in ("valid", "partial")]
        invalid = [r for r in reviews if r["status"] == "invalid"]
        if not valid:
            return "invalida" if invalid else "pendiente"
        if any(r["status"] == "partial" for r in reviews):
            return "parcial"
        if any(r["status"] == "needs_validation" for r in reviews):
            return "pendiente_validacion"
        return "procesada"

    def _expire_pending(self) -> None:
        """Ventana caducada sin revisiones => continuación automática (neutral)."""
        now = _now()
        for item in self.repos.reviews.list_queue(status="pending"):
            if item["window_deadline"] <= now and self.settings.review_continue_without_review:
                self.repos.reviews.update_queue(
                    item["opportunity_id"], status="continued", reviewed_without_external=1
                )
                self._log(
                    agent="review_queue",
                    opportunity_id=item["opportunity_id"],
                    summary="Ventana de revisión externa caducada: se continúa con la evaluación interna (ausencia NEUTRAL, no aprobación).",
                    decision="continued_without_review",
                    model_or_method="deterministic rule",
                )

    @staticmethod
    def _review_required(evaluation) -> bool:
        """Actividades sensibles exigen revisión (riesgo legal/ToS/plataforma)."""
        for blocker in evaluation.blockers or []:
            low = blocker.lower()
            if any(w in low for w in ("legal", "regulad", "tos", "plataforma", "privacidad")):
                return True
        for risk in evaluation.risks or []:
            if risk.severity == "high" and risk.blocker:
                return True
        return False

    def continue_without_review(self, opportunity_id: str, *, note: str | None = None) -> dict:
        item = self.repos.reviews.queue_item(opportunity_id)
        if item is None:
            raise NotFoundError("La oportunidad no está en la cola de revisión.")
        if item["status"] != "pending":
            raise ConflictError(f"La cola ya no está pendiente (estado: {item['status']}).")
        self.repos.reviews.update_queue(
            opportunity_id, status="continued", reviewed_without_external=1, notes=note or item["notes"]
        )
        self._log(
            agent="review_queue",
            opportunity_id=opportunity_id,
            summary="Continuación sin revisión externa solicitada (ausencia NEUTRAL)." + (f" Nota: {note}" if note else ""),
            decision="continued_without_review",
            model_or_method="human",
        )
        return self.repos.reviews.queue_item(opportunity_id)  # type: ignore[return-value]

    def add_note(self, opportunity_id: str, note: str) -> dict:
        if not note or not note.strip():
            raise ValidationError("La nota no puede estar vacía.")
        item = self.repos.reviews.queue_item(opportunity_id)
        if item is None:
            raise NotFoundError("La oportunidad no está en la cola de revisión.")
        combined = f"{item['notes']}\n[{_now()}] {note.strip()}".strip()
        self.repos.reviews.update_queue(opportunity_id, notes=combined)
        return self.repos.reviews.queue_item(opportunity_id)  # type: ignore[return-value]

    # ==================================================================
    # Revisión automática (OPCIÓN A: OpenRouter SOLO para el comité)
    # ==================================================================
    def _circuit_breaker(self) -> dict:
        """Estado del circuit breaker (determinista, desde llm_call_log)."""
        since = (_now_dt() - timedelta(seconds=self.settings.openrouter_circuit_breaker_cooldown_seconds)).isoformat()
        failures = self.repos.llm_calls.failures_since(since, provider="openrouter")
        open_ = failures >= self.settings.openrouter_circuit_breaker_failures
        return {
            "open": open_,
            "failures_recent": failures,
            "threshold": self.settings.openrouter_circuit_breaker_failures,
            "cooldown_seconds": self.settings.openrouter_circuit_breaker_cooldown_seconds,
        }

    def auto_status(self) -> dict:
        """Estado del presupuesto de inferencia y del circuito (sin llamadas)."""
        today = _now_dt().date().isoformat()
        month_ago = (_now_dt() - timedelta(days=30)).isoformat()
        provider = self.providers.openrouter if self.providers is not None else None
        return {
            "configured": bool(provider and provider.available()),
            "review_model": provider.review_model if provider else self.settings.openrouter_review_model,
            "fallback_model": provider.fallback_model if provider else self.settings.openrouter_fallback_model,
            "circuit_breaker": self._circuit_breaker(),
            "usage_today": {
                "requests": self.repos.llm_calls.count_since(today, provider="openrouter"),
                "limit": self.settings.openrouter_daily_request_limit,
                "cost_usd": self.repos.llm_calls.cost_since(today, provider="openrouter"),
                "cost_limit_usd": self.settings.openrouter_daily_cost_limit_usd,
            },
            "usage_month": {
                "cost_usd": self.repos.llm_calls.cost_since(month_ago, provider="openrouter"),
                "cost_limit_usd": self.settings.openrouter_monthly_cost_limit_usd,
            },
            "max_reviews_per_opportunity": self.settings.openrouter_max_reviews_per_opportunity,
            "max_finalists_per_week": self.settings.review_max_finalists_per_week,
        }

    def _record_call(
        self,
        *,
        provider: str = "openrouter",
        opportunity_id: str | None,
        requested_model: str,
        actual_model: str | None,
        usage: dict | None,
        reported_cost: float | None,
        estimated_cost: float | None,
        cost_source: str,
        latency_ms: int | None,
        retry_count: int,
        fallback_used: bool,
        response_status: str,
        notes: str | None,
    ) -> dict:
        record = LLMCallRecord(
            provider=provider,
            action="external_review",
            opportunity_id=opportunity_id,
            requested_model=requested_model,
            actual_model=actual_model,
            prompt_tokens=usage.get("prompt_tokens") if usage else None,
            completion_tokens=usage.get("completion_tokens") if usage else None,
            total_tokens=usage.get("total_tokens") if usage else None,
            reported_cost=reported_cost,
            estimated_cost=estimated_cost,
            cost_source=cost_source,
            billing_verified=False,  # sin reconciliación con facturación en esta fase
            latency_ms=latency_ms,
            retry_count=retry_count,
            fallback_used=fallback_used,
            response_status=response_status,
            notes=notes,
        )
        return self.repos.llm_calls.create(record)

    def auto_review(self, opportunity_id: str) -> dict:
        """Una revisión de contraste automática vía OpenRouter (Opción A).

        Guardas deterministas en orden: límite por oportunidad, circuit breaker,
        límite diario de peticiones, límite diario/mensual de coste, clave
        configurada. Si algo falla o no hay clave: NUNCA se fabrica una revisión;
        se registra la llamada en ``llm_call_log`` y la ausencia es neutral.
        """
        if self.repos.opportunities.get(opportunity_id) is None:
            raise NotFoundError("Oportunidad no encontrada.")

        def _blocked(reason: str, detail: str = "") -> dict:
            self._log(
                agent="auto_review",
                opportunity_id=opportunity_id,
                summary=f"Revisión automática BLOQUEADA: {reason}. {detail}",
                decision="blocked",
                model_or_method="deterministic guard",
            )
            return {"status": "blocked", "reason": reason, "detail": detail, "review_created": False}

        # 1) Máximo de revisiones automáticas por oportunidad (fase actual: 1).
        already = self.repos.llm_calls.count_auto_reviews_for(opportunity_id)
        if already >= self.settings.openrouter_max_reviews_per_opportunity:
            return _blocked("max_reviews_per_opportunity", f"ya hay {already} revisión(es) automática(s).")

        # 2) Circuit breaker ante errores repetidos.
        breaker = self._circuit_breaker()
        if breaker["open"]:
            return _blocked(
                "circuit_breaker_open",
                f"{breaker['failures_recent']} fallos recientes en {breaker['cooldown_seconds']}s.",
            )

        # 3) Límite diario de peticiones.
        today = _now_dt().date().isoformat()
        requests_today = self.repos.llm_calls.count_since(today, provider="openrouter")
        if requests_today >= self.settings.openrouter_daily_request_limit:
            return _blocked("daily_request_limit", f"{requests_today}/{self.settings.openrouter_daily_request_limit}")

        # 4) Límites de coste diario y mensual (suma honesta reported/estimated).
        cost_today = self.repos.llm_calls.cost_since(today, provider="openrouter")
        if cost_today >= self.settings.openrouter_daily_cost_limit_usd:
            return _blocked("daily_cost_limit", f"{cost_today:.4f} >= {self.settings.openrouter_daily_cost_limit_usd} USD")
        month_ago = (_now_dt() - timedelta(days=30)).isoformat()
        cost_month = self.repos.llm_calls.cost_since(month_ago, provider="openrouter")
        if cost_month >= self.settings.openrouter_monthly_cost_limit_usd:
            return _blocked("monthly_cost_limit", f"{cost_month:.4f} >= {self.settings.openrouter_monthly_cost_limit_usd} USD")

        # 5) Proveedor configurado (sin clave => sin revisión, nunca mock fingido).
        if self.providers is None or not self.providers.openrouter.available():
            return {
                "status": "skipped",
                "reason": "provider_not_configured",
                "detail": "OPENROUTER_API_KEY no configurado: la ausencia de revisión es neutral.",
                "review_created": False,
            }

        # 6) Expediente IDÉNTICO al de los revisores manuales (comparabilidad).
        packet = self.generate_review_packet(opportunity_id)
        prompt = packet["content"]

        # 7) Llamada REAL directa al proveedor OpenRouter (NUNCA al manager:
        #    el manager podría resolver a mock según LLM_PROVIDER y fabricar
        #    una revisión falsa. Aquí el fallback a mock está prohibido).
        try:
            resp = self.providers.openrouter.generate(
                prompt,
                task="external_review",
                temperature=0.2,
            )
        except ProviderUnavailableError as exc:
            self._record_call(
                opportunity_id=opportunity_id,
                requested_model=self.settings.openrouter_review_model,
                actual_model=None,
                usage=None,
                reported_cost=None,
                estimated_cost=None,
                cost_source=CostSource.unknown.value,
                latency_ms=None,
                retry_count=0,
                fallback_used=False,
                response_status="error",
                notes=f"Llamada fallida antes de respuesta: {str(exc)[:400]}",
            )
            self._log(
                agent="auto_review",
                opportunity_id=opportunity_id,
                summary=f"Revisión automática FALLIDA (sin fabricar revisión): {str(exc)[:200]}",
                decision="failed_neutral",
                model_or_method="openrouter",
            )
            return {
                "status": "failed",
                "reason": "provider_error",
                "detail": str(exc)[:400],
                "review_created": False,
                "neutral": True,
            }
        except Exception as exc:  # cualquier otro fallo: sin fabricación
            self._record_call(
                opportunity_id=opportunity_id,
                requested_model=self.settings.openrouter_review_model,
                actual_model=None,
                usage=None,
                reported_cost=None,
                estimated_cost=None,
                cost_source=CostSource.unknown.value,
                latency_ms=None,
                retry_count=0,
                fallback_used=False,
                response_status="error",
                notes=f"Llamada fallida: {str(exc)[:400]}",
            )
            self._log(
                agent="auto_review",
                opportunity_id=opportunity_id,
                summary=f"Revisión automática FALLIDA (sin fabricar revisión): {str(exc)[:200]}",
                decision="failed_neutral",
                model_or_method="openrouter",
            )
            return {
                "status": "failed",
                "reason": "provider_error",
                "detail": str(exc)[:400],
                "review_created": False,
                "neutral": True,
            }

        # 8) NUNCA hay fallback a mock: si la respuesta no viene de OpenRouter,
        #    no se guarda ninguna revisión (regla de no fabricación).
        # 9) Parseo con allowlist (misma vía que las revisiones manuales).
        parsed, errors, status = self.parse_review_response(resp.text)
        actual_model = resp.actual_model or resp.model
        review = ExternalReview(
            opportunity_id=opportunity_id,
            provider="openrouter",
            model=_sanitize_text(actual_model, 200),
            model_version=_sanitize_text(resp.model, 100),  # solicitado (fijo)
            execution_mode="API_AUTOMATIC",
            raw_response=resp.text,
            parsed_response=parsed,
            recommendation=parsed.get("recommendation"),
            confidence=parsed.get("confidence"),
            strongest_evidence=parsed.get("strongest_evidence"),
            weakest_assumption=parsed.get("weakest_assumption"),
            missing_evidence=parsed.get("missing_evidence"),
            primary_risk=parsed.get("primary_risk"),
            suggested_improvement=parsed.get("suggested_improvement"),
            cheaper_experiment=parsed.get("cheaper_experiment"),
            kill_condition=parsed.get("kill_condition"),
            cost=resp.reported_cost if resp.reported_cost is not None else (resp.cost_estimate_usd or 0.0),
            status=status,
            parse_errors=errors,
            imported_by="auto-review",
            file_hash=_sha256(resp.text),
        )
        saved = self.repos.reviews.create_review(review)

        # 10) Registro de llamada con rastro completo y honesto de coste.
        call_record = self._record_call(
            opportunity_id=opportunity_id,
            requested_model=resp.model,
            actual_model=actual_model,
            usage=resp.usage,
            reported_cost=resp.reported_cost,
            estimated_cost=resp.cost_estimate_usd or None,
            cost_source=resp.cost_source,
            latency_ms=resp.latency_ms,
            retry_count=resp.retry_count,
            fallback_used=False,
            response_status="ok",
            notes=resp.notes,
        )
        self._log(
            agent="auto_review",
            opportunity_id=opportunity_id,
            summary=(
                f"Revisión automática OpenRouter ({actual_model}) guardada (estado {status}). "
                f"Coste: reported={resp.reported_cost} estimado={resp.cost_estimate_usd} "
                f"fuente={resp.cost_source} billing_verified=False."
            ),
            decision=review.recommendation or "no_recommendation",
            model_or_method=f"openrouter:{actual_model}",
            evidence_used=[str(review.file_hash)],
        )
        return {
            "status": "ok",
            "review_created": True,
            "review": saved,
            "call": call_record,
            "warnings": errors,
            "cost_source": resp.cost_source,
            "billing_verified": False,
        }

    def auto_review_omniroute(self, opportunity_id: str) -> dict:
        """Segundo revisor OPCIONAL vía OmniRoute (iteración 008, aislado).

        Mismas reglas que ``auto_review`` pero con el proveedor OmniRoute:
        - Solo si ``OMNIROUTE_ENABLED=true`` y la conexión está permitida.
        - Límites diario/mensual de peticiones y coste, máx. 1 revisión
          automática de OmniRoute por oportunidad, circuit breaker.
        - Si falla o no hay servicio: NO se fabrica revisión; la ausencia es
          neutral y el error se registra con los metadatos de routing.
        - Nunca sustituye al modelo fijo del comité OpenRouter.
        """
        from app.core.omniroute_allowlist import is_connection_allowed

        if self.repos.opportunities.get(opportunity_id) is None:
            raise NotFoundError("Oportunidad no encontrada.")
        provider = self.providers.omniroute if self.providers is not None else None

        def _blocked(reason: str, detail: str = "") -> dict:
            return {"status": "blocked", "reason": reason, "detail": detail, "review_created": False}

        if provider is None or not provider.available():
            return {
                "status": "skipped", "reason": "omniroute_disabled",
                "detail": "OMNIROUTE_ENABLED=false: OmniRoute no se usa (aislado, por defecto).",
                "review_created": False,
            }
        allowed, reason = is_connection_allowed("omniroute-gateway", production=False)
        if not allowed:
            return _blocked("connection_not_allowed", reason)
        already = sum(
            1 for r in self.repos.reviews.reviews_for(opportunity_id)
            if r["provider"] == "omniroute" and r["execution_mode"] == "API_AUTOMATIC"
        )
        if already >= 1:
            return _blocked("max_reviews_per_opportunity", "ya hay 1 revisión automática de OmniRoute.")
        breaker = self._circuit_breaker()
        if breaker["open"]:
            return _blocked("circuit_breaker_open", str(breaker["failures_recent"]))
        today = _now_dt().date().isoformat()
        if self.repos.llm_calls.count_since(today, provider="omniroute") >= self.settings.omniroute_daily_request_limit:
            return _blocked("daily_request_limit", "límite diario de peticiones OmniRoute.")
        cost_today = self.repos.llm_calls.cost_since(today, provider="omniroute")
        if self.settings.omniroute_daily_cost_limit_usd > 0 and cost_today >= self.settings.omniroute_daily_cost_limit_usd:
            return _blocked("daily_cost_limit", f"{cost_today:.4f} USD")

        packet = self.generate_review_packet(opportunity_id)
        try:
            resp = provider.generate(packet["content"], task="external_review", temperature=0.2)
        except ProviderUnavailableError as exc:
            self._record_call(
                provider="omniroute",
                opportunity_id=opportunity_id, requested_model=provider.review_model,
                actual_model=None, usage=None, reported_cost=None, estimated_cost=None,
                cost_source=CostSource.unknown.value, latency_ms=None, retry_count=0,
                fallback_used=False, response_status="error",
                notes=f"OmniRoute falló (sin fabricar revisión): {_sanitize_text(str(exc), 300)}",
            )
            self._log(agent="auto_review_omniroute", opportunity_id=opportunity_id,
                      summary=f"OmniRoute FALLÓ; ausencia neutral: {str(exc)[:150]}",
                      decision="failed_neutral", model_or_method="omniroute")
            return {"status": "failed", "reason": "provider_error", "review_created": False,
                    "neutral": True, "detail": str(exc)[:300]}
        except Exception as exc:
            self._record_call(
                provider="omniroute",
                opportunity_id=opportunity_id, requested_model=provider.review_model,
                actual_model=None, usage=None, reported_cost=None, estimated_cost=None,
                cost_source=CostSource.unknown.value, latency_ms=None, retry_count=0,
                fallback_used=False, response_status="error",
                notes=f"OmniRoute falló (sin fabricar revisión): {_sanitize_text(str(exc), 300)}",
            )
            return {"status": "failed", "reason": "provider_error", "review_created": False,
                    "neutral": True, "detail": str(exc)[:300]}

        actual_model = resp.actual_model or resp.model
        parsed, errors, status = self.parse_review_response(resp.text)
        review = ExternalReview(
            opportunity_id=opportunity_id,
            provider="omniroute",
            model=_sanitize_text(actual_model, 200),
            model_version=_sanitize_text(resp.model, 100),
            execution_mode="API_AUTOMATIC",
            raw_response=resp.text,
            parsed_response=parsed,
            recommendation=parsed.get("recommendation"),
            confidence=parsed.get("confidence"),
            strongest_evidence=parsed.get("strongest_evidence"),
            weakest_assumption=parsed.get("weakest_assumption"),
            missing_evidence=parsed.get("missing_evidence"),
            primary_risk=parsed.get("primary_risk"),
            suggested_improvement=parsed.get("suggested_improvement"),
            cheaper_experiment=parsed.get("cheaper_experiment"),
            kill_condition=parsed.get("kill_condition"),
            cost=resp.reported_cost if resp.reported_cost is not None else (resp.cost_estimate_usd or 0.0),
            status=status,
            parse_errors=errors,
            imported_by="auto-review-omniroute",
            file_hash=_sha256(resp.text),
        )
        saved = self.repos.reviews.create_review(review)
        self._record_call(
            provider="omniroute",
            opportunity_id=opportunity_id,
            requested_model=resp.model,
            actual_model=actual_model,
            usage=resp.usage,
            reported_cost=resp.reported_cost,
            estimated_cost=resp.cost_estimate_usd or None,
            cost_source=resp.cost_source,
            latency_ms=resp.latency_ms,
            retry_count=resp.retry_count,
            fallback_used=False,
            response_status="ok",
            notes=resp.notes,
        )
        self._log(agent="auto_review_omniroute", opportunity_id=opportunity_id,
                  summary=f"Revisión automática OmniRoute ({actual_model}) guardada; cost_source={resp.cost_source}.",
                  decision=review.recommendation or "no_recommendation",
                  model_or_method=f"omniroute:{actual_model}")
        return {"status": "ok", "review_created": True, "review": saved,
                "warnings": errors, "cost_source": resp.cost_source, "billing_verified": False}

    # ==================================================================
    # Expediente de revisión (idéntico para todos los revisores)
    # ==================================================================
    def packet_path(self, opportunity_id: str) -> Path:
        return self._dir / f"opportunity_{opportunity_id}" / "review_packet.md"

    def generate_review_packet(self, opportunity_id: str) -> dict:
        """Genera (o regenera idempotentemente) el expediente Markdown.

        Incluye un TOKEN no secreto (packet_id, packet_version, generated_at,
        content_hash) para validar que una respuesta importada corresponde a
        este expediente. El contenido base es IDÉNTICO para todos los
        revisores; solo la cabecera de copiado varía (ver review_packet_for_copy).
        """
        opportunity = self.repos.opportunities.get(opportunity_id)
        if opportunity is None:
            raise NotFoundError("Oportunidad no encontrada.")
        markdown = self._build_packet_markdown(opportunity_id, opportunity)
        path = self.packet_path(opportunity_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        content_hash = _sha256(markdown)
        # generated_at DETERMINISTA (creación de la oportunidad): el token del
        # expediente debe ser idéntico para los tres revisores; solo la
        # cabecera que identifica al revisor puede variar.
        return {
            "opportunity_id": opportunity_id,
            "packet_id": _sha256(opportunity_id)[:16],
            "packet_version": self.settings.review_packet_version,
            "content_hash": content_hash,
            "generated_at": opportunity.created_at,
            "path": str(path),
            "filename": path.name,
            "content": markdown,
            "byte_size": len(markdown.encode("utf-8")),
            "sha256": content_hash,
        }

    def review_packet_for_copy(self, opportunity_id: str, reviewer: str | None = None) -> dict:
        """Expediente listo para COPIAR en el portapapeles.

        Los tres botones (GPT/Grok/Gemini) usan EXACTAMENTE el mismo contenido
        base; solo varía una cabecera de metadatos que identifica al revisor.
        Nunca incluye claves ni instrucciones operativas del sistema.
        """
        packet = self.generate_review_packet(opportunity_id)
        base = packet["content"]
        header = ""
        if reviewer:
            key = str(reviewer).strip().lower()
            if key in REVIEWER_HEADERS:
                header = (
                    f"> {REVIEWER_HEADERS[key]}\n> \n"
                    f"> Token del expediente (no secreto): opportunity_id=`{opportunity_id}` · "
                    f"packet_id=`{packet['packet_id']}` · packet_version=`{packet['packet_version']}` · "
                    f"generated_at=`{packet['generated_at']}` · content_hash=`{packet['content_hash']}`\n\n"
                )
        return {
            "opportunity_id": opportunity_id,
            "reviewer": reviewer or "generic",
            "packet_id": packet["packet_id"],
            "packet_version": packet["packet_version"],
            "content_hash": packet["content_hash"],
            "generated_at": packet["generated_at"],
            "content": header + base,
            "byte_size": len((header + base).encode("utf-8")),
        }

    def _validate_packet_token(self, opportunity_id: str, packet_version: str | None, content_hash: str | None) -> list[str]:
        """Valida el token del expediente en una respuesta importada.

        Devuelve avisos (nunca errores fatales): una respuesta sin token puede
        seguir importándose como DATO, pero se marca como no vinculada al
        expediente actual.
        """
        warnings: list[str] = []
        if not packet_version and not content_hash:
            return warnings
        current = self.generate_review_packet(opportunity_id)
        if packet_version and packet_version != self.settings.review_packet_version:
            warnings.append(
                f"packet_version {packet_version!r} no coincide con la versión actual "
                f"{self.settings.review_packet_version!r}; el expediente pudo cambiar."
            )
        if content_hash and content_hash != current["content_hash"]:
            warnings.append("content_hash no coincide con el expediente actual; la respuesta puede corresponder a otra versión.")
        if not warnings:
            warnings.append("Token del expediente verificado (coincide con la versión actual).")
        return warnings

    def get_review_packet(self, opportunity_id: str) -> dict:
        path = self.packet_path(opportunity_id)
        if not path.exists():
            raise NotFoundError("Expediente no generado todavía. Ejecuta POST /api/reviews/opportunities/{id}/packet.")
        content = path.read_text(encoding="utf-8")
        return {
            "opportunity_id": opportunity_id,
            "path": str(path),
            "filename": path.name,
            "content": content,
            "byte_size": len(content.encode("utf-8")),
            "sha256": _sha256(content),
        }

    def _build_packet_markdown(self, opportunity_id: str, opportunity) -> str:
        detail = {
            "evidences": [e.model_dump() for e in self.repos.evidence.list_for(opportunity_id)],
            "competitors": [c.model_dump() for c in self.repos.competitors.list_for(opportunity_id)],
            "evaluation": self.repos.evaluations.get(opportunity_id).model_dump() if self.repos.evaluations.get(opportunity_id) else None,
            "experiment": self.repos.experiments.get_for(opportunity_id).model_dump() if self.repos.experiments.get_for(opportunity_id) else None,
        }
        ev = detail["evaluation"] or {}
        est = (ev.get("estimates") or {}) if ev else {}
        exp = detail["experiment"] or {}
        lines: list[str] = []
        lines.append("# Expediente de revisión externa (comité de contraste)")
        lines.append("")
        lines.append(f"- **Identificador**: {opportunity.id}")
        lines.append(f"- **Título**: {opportunity.title}")
        # Fecha determinista del expediente: la de creación de la oportunidad
        # (la regeneración produce el MISMO contenido para todos los revisores).
        lines.append(f"- **Fecha del expediente**: {opportunity.created_at}")
        lines.append(f"- **Sector**: {opportunity.sector or '—'}")
        lines.append("")
        lines.append("> Este expediente es IDÉNTICO para todos los revisores. No se adapta el texto para persuadir a ningún modelo.")
        lines.append("")
        lines.append("## 1. Problema observado")
        lines.append(opportunity.problem)
        lines.append("")
        lines.append("## 2. Cliente objetivo")
        lines.append(opportunity.target_customer or "DESCONOCIDO")
        lines.append("")
        lines.append("## 3. Solución propuesta")
        lines.append(opportunity.proposed_solution or "—")
        lines.append("")
        lines.append("## 4. Contexto y evidencias guardadas")
        if detail["evidences"]:
            for e in detail["evidences"]:
                lines.append(f"- **[{e['evidence_type']}]** {e['summary']}")
                lines.append(f"  - Fuente: {e.get('source_name') or '—'} {e.get('source_url') or ''}")
                lines.append(f"  - Fiabilidad: {e['reliability_score']} · Verificada: {'sí' if e['verified'] else 'no'} · Método: {e['method']}")
                if e.get("verification_notes"):
                    lines.append(f"  - Notas: {e['verification_notes']}")
        else:
            lines.append("- Sin evidencias guardadas (desconocido, no cero).")
        lines.append("")
        lines.append("## 5. Competidores, precios observados y alternativas actuales")
        if detail["competitors"]:
            for c in detail["competitors"]:
                lines.append(f"- **{c['name']}** — {c.get('offer') or '—'} · precio observado: {c.get('observed_price') if c.get('observed_price') is not None else 'desconocido'} USD")
                if c.get("strengths"):
                    lines.append(f"  - Fortalezas: {c['strengths']}")
                if c.get("weaknesses"):
                    lines.append(f"  - Debilidades: {c['weaknesses']}")
        else:
            lines.append("- Sin competidores identificados.")
        lines.append("")
        lines.append("## 6. Soluciones consideradas")
        lines.append("Las alternativas actuales del cliente (proceso manual, freelancer, plantilla gratuita, IA generalista) se reflejan en las evidencias y en la crítica interna.")
        lines.append("")
        lines.append("## 7. Diferenciación y canal de adquisición")
        lines.append(f"- Diferenciación estimada: {ev.get('differentiation_score', '—')}/100")
        lines.append(f"- Llegada a compradores: {est.get('reachability') or 'desconocida'}")
        lines.append(f"- Autonomía de automatización estimada: {est.get('automation_degree') if est.get('automation_degree') is not None else 'desconocida'}%")
        lines.append("")
        lines.append("## 8. Coste, modelo de ingresos y margen (ESTIMACIONES)")
        lines.append(f"- Coste de construcción (USD): {est.get('build_cost_low_usd') if est.get('build_cost_low_usd') is not None else 'desconocido'} – {est.get('build_cost_high_usd') if est.get('build_cost_high_usd') is not None else 'desconocido'}")
        lines.append(f"- Precio estimado (USD): {est.get('price_low_usd') if est.get('price_low_usd') is not None else 'desconocido'} – {est.get('price_high_usd') if est.get('price_high_usd') is not None else 'desconocido'}")
        lines.append(f"- Margen estimado (%): {est.get('margin_low_pct') if est.get('margin_low_pct') is not None else 'desconocido'} – {est.get('margin_high_pct') if est.get('margin_high_pct') is not None else 'desconocido'}")
        lines.append(f"- Recurrencia: {est.get('recurrence') or 'desconocida'}")
        lines.append(f"- Dependencias de plataforma: {', '.join(est.get('platform_dependencies') or []) or 'ninguna declarada'}")
        lines.append("> Las cifras sin fuente son ESTIMACIONES. Si no hay dato, se indica 'desconocido'.")
        lines.append("")
        lines.append("## 9. Datos desconocidos y suposiciones no verificadas")
        assumptions = ev.get("assumptions") or []
        lines.append(f"- Suposiciones sin verificar: {len(assumptions)}")
        for a in assumptions:
            lines.append(f"  - {a}")
        lines.append("")
        lines.append("## 10. Riesgos (Compliance) y crítica interna (Skeptic)")
        risks = ev.get("risks") or []
        if risks:
            for r in risks:
                lines.append(f"- [{r.get('severity')}] {r.get('category')}: {r.get('description')}")
                if r.get("mitigation"):
                    lines.append(f"  - Mitigación: {r['mitigation']}")
        else:
            lines.append("- Sin riesgos declarados.")
        lines.append("")
        if ev.get("skeptic_critique"):
            lines.append("### Crítica interna")
            lines.append(ev["skeptic_critique"])
        lines.append("")
        lines.append("## 11. Experimento propuesto")
        if exp:
            lines.append(f"- Hipótesis: {exp.get('hypothesis') or '—'}")
            lines.append(f"- Test más barato: {exp.get('cheapest_test') or '—'}")
            lines.append(f"- Presupuesto máximo: {exp.get('maximum_budget') if exp.get('maximum_budget') is not None else '—'} USD")
            lines.append(f"- Métrica de éxito: {exp.get('success_metric') or '—'} · umbral: {exp.get('success_threshold') or '—'}")
            lines.append(f"- Umbral de abandono: {exp.get('failure_threshold') or '—'}")
            lines.append(f"- Duración: {exp.get('duration') or '—'}")
        else:
            lines.append("- Sin experimento definido.")
        lines.append("")
        lines.append("## 12. Preguntas concretas para el revisor")
        for q in (
            "¿Qué supuesto, si fuera falso, destruiría la oportunidad?",
            "¿Qué evidencia externa concreta (URL + fecha + fragmento) falta y es imprescindible?",
            "¿Quién pagaría exactamente y de qué presupuesto saldría el pago?",
            "¿Cuál es la alternativa real del cliente hoy y qué le costaría no resolver el problema?",
            "¿Puede una IA generalista (ChatGPT/Gemini/Claude/DeepSeek) resolver el 80% del problema con un prompt?",
            "¿Cómo conseguiría los primeros 20 usuarios sin spam?",
            "¿Cuál es el experimento MÁS BARATO que probaría la hipótesis con señal real?",
            "¿Qué condición objetiva obligaría a abandonar?",
        ):
            lines.append(f"- {q}")
        lines.append("")
        lines.append("## 13. Prompt de revisión normalizado")
        lines.append("")
        lines.append(_NORMALIZED_REVIEW_PROMPT)
        return "\n".join(lines) + "\n"

    # ==================================================================
    # Importación de revisiones (TXT / Markdown)
    # ==================================================================
    def import_review(self, opportunity_id: str, payload: ReviewImportIn) -> dict:
        """Importa una revisión como DATO no confiable. Nunca se ejecuta."""
        if self.repos.opportunities.get(opportunity_id) is None:
            raise NotFoundError("Oportunidad no encontrada.")

        # Límite de tamaño (bytes del contenido UTF-8).
        size = len(payload.content.encode("utf-8"))
        if size > self.settings.review_max_file_bytes:
            raise PayloadTooLargeError(
                f"El archivo supera el límite de {self.settings.review_max_file_bytes} bytes.",
                details={"size_bytes": size, "max_bytes": self.settings.review_max_file_bytes},
            )
        validate_extension(payload.filename, self.settings.review_allowed_extensions)

        file_hash = _sha256(payload.content)
        existing = self.repos.reviews.find_by_hash(opportunity_id, file_hash)
        if existing:
            raise ConflictError(
                "Revisión duplicada: ya existe una revisión con el mismo hash de contenido para esta oportunidad.",
                details={"existing_review_id": existing["id"]},
            )

        parsed, errors, status = self.parse_review_response(payload.content)

        provider = _sanitize_text(payload.provider or "unknown", 100).lower()
        if provider not in KNOWN_PROVIDERS and provider != "unknown":
            errors.append(f"Proveedor '{provider}' no está en la lista de conocidos; se registra igualmente como dato.")

        review = ExternalReview(
            opportunity_id=opportunity_id,
            provider=provider,
            model=_sanitize_text(payload.model or "unknown", 200),
            model_version=_sanitize_text(payload.model_version or "", 100) or None,
            execution_mode=payload.execution_mode,
            raw_response=payload.content,
            parsed_response=parsed,
            recommendation=parsed.get("recommendation"),
            confidence=parsed.get("confidence"),
            strongest_evidence=parsed.get("strongest_evidence"),
            weakest_assumption=parsed.get("weakest_assumption"),
            missing_evidence=parsed.get("missing_evidence"),
            primary_risk=parsed.get("primary_risk"),
            suggested_improvement=parsed.get("suggested_improvement"),
            cheaper_experiment=parsed.get("cheaper_experiment"),
            kill_condition=parsed.get("kill_condition"),
            cost=payload.cost,
            status=status,
            parse_errors=errors,
            imported_by=_sanitize_text(payload.imported_by, 200) or "human",
            file_hash=file_hash,
        )
        saved = self.repos.reviews.create_review(review)
        self._log(
            agent="external_review",
            opportunity_id=opportunity_id,
            summary=f"Revisión externa importada ({provider}/{review.model}, modo {payload.execution_mode}, estado {status}).",
            decision=review.recommendation or "no_recommendation",
            model_or_method=f"{provider}:{review.model}",
            evidence_used=[str(file_hash)],
        )
        return {"review": saved, "warnings": errors, "status": status}

    # ------------------------------------------------------------------
    # Importación combinada (# GPT / # GROK / # GEMINI / # HUMAN_NOTE)
    # ------------------------------------------------------------------
    _COMBINED_SECTION_RE = re.compile(r"^\s*#{1,3}\s*\*{0,2}\s*([A-Z_]+)\s*\*{0,2}\s*$", re.MULTILINE)
    _COMBINED_MAPPING = {
        "GPT": "gpt",
        "GROK": "grok",
        "GEMINI": "gemini",
        "CLAUDE": "claude",
        "DEEPSEEK": "deepseek",
        "OPENROUTER": "openrouter",
        "OMNIROUTE": "omniroute",
        "HUMAN_NOTE": "human",
        "HUMAN": "human",
    }

    def _split_combined_sections(self, content: str) -> dict[str, str]:
        """Divide el contenido en secciones por cabecera. Sin sección => vacío."""
        markers = [m for m in self._COMBINED_SECTION_RE.finditer(content)]
        sections: dict[str, str] = {}
        for i, m in enumerate(markers):
            name = m.group(1).strip().upper()
            provider = self._COMBINED_MAPPING.get(name)
            if not provider:
                continue
            start = m.end()
            end = markers[i + 1].start() if i + 1 < len(markers) else len(content)
            body = content[start:end].strip()
            if body:
                sections[provider] = body
        return sections

    def import_combined_review(self, opportunity_id: str, payload: CombinedReviewImportIn) -> dict:
        """Importa un único archivo con secciones por revisor.

        Separa las secciones y asocia cada una con el expediente. Si falta una
        sección, importa las restantes. HUMAN_NOTE se guarda como nota de la
        cola (nunca como opinión de modelo).
        """
        if self.repos.opportunities.get(opportunity_id) is None:
            raise NotFoundError("Oportunidad no encontrada.")
        size = len(payload.content.encode("utf-8"))
        if size > self.settings.review_max_file_bytes * 4:
            raise PayloadTooLargeError(
                f"El archivo combinado supera el límite de {self.settings.review_max_file_bytes * 4} bytes.",
                details={"size_bytes": size},
            )
        validate_extension(payload.filename, self.settings.review_allowed_extensions)

        sections = self._split_combined_sections(payload.content)
        if not sections:
            raise ValidationError(
                "No se encontró ninguna sección válida (# GPT / # GROK / # GEMINI / # HUMAN_NOTE)."
            )

        imported: list[dict] = []
        skipped: list[dict] = []
        human_notes: list[str] = []
        for provider, body in sections.items():
            if provider == "human":
                human_notes.append(body)
                continue
            sub = ReviewImportIn(
                filename=f"combined_{provider}.md",
                content=body,
                provider=provider,
                model=payload.default_model,
                execution_mode=payload.execution_mode,
                imported_by=payload.imported_by,
            )
            try:
                result = self.import_review(opportunity_id, sub)
                imported.append({**result, "provider": provider})
            except ConflictError as exc:
                skipped.append({"provider": provider, "reason": exc.message})

        if human_notes:
            try:
                self.add_note(opportunity_id, "\n\n".join(human_notes))
            except (NotFoundError, ValidationError) as exc:
                skipped.append({"provider": "human", "reason": exc.message})

        if not imported:
            raise ConflictError(
                "Ninguna sección se importó como revisión nueva (todas duplicadas o sin sección válida).",
                details={"skipped": skipped},
            )

        self._log(
            agent="external_review",
            opportunity_id=opportunity_id,
            summary=f"Importación combinada: {len(imported)} revisión(es) importada(s), {len(skipped)} omitida(s).",
            decision="imported_combined",
            model_or_method="manual_import",
        )
        return {"imported": imported, "skipped": skipped, "count": len(imported)}

    def parse_review_response(self, text: str) -> tuple[dict, list[str], str]:
        """Parsing tolerante y con allowlist. Devuelve (parsed, errors, status)."""
        errors: list[str] = []
        parsed: dict = {}

        # --- 1) Bloque JSON (```json ... ``` o cualquier objeto con 'recommendation')
        json_obj = None
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                json_obj = json.loads(match.group(1))
            except json.JSONDecodeError:
                errors.append("Bloque JSON presente pero inválido.")
        if json_obj is None:
            for candidate in re.findall(r"\{[^{}\n]*\}", text):
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict) and "recommendation" in obj:
                        json_obj = obj
                        break
                except json.JSONDecodeError:
                    continue
        if isinstance(json_obj, dict):
            for key in PARSED_FIELDS:
                if key in json_obj and json_obj[key] is not None:
                    parsed[key] = json_obj[key]

        # --- 2) Líneas "clave: valor" (rellenan huecos, nunca sobrescriben JSON)
        for raw_line in text.splitlines():
            line = raw_line.strip().lstrip("-*").strip()
            low = line.lower()
            for key in PARSED_FIELDS:
                if key in parsed:
                    continue
                for prefix in (f"**{key}**:", f"{key}:", f"{key} :"):
                    if low.startswith(prefix.lower()):
                        value = line[len(prefix):].strip()
                        if value:
                            parsed[key] = value
                        break

        # --- 3) Validación de recomendación
        rec = parsed.get("recommendation")
        if rec is None or str(rec).strip() == "":
            errors.append("No se encontró una recomendación (REJECT | MORE_RESEARCH | SMALL_EXPERIMENT | PRIORITY_EXPERIMENT).")
            parsed.pop("recommendation", None)
        else:
            rec_up = str(rec).strip().upper()
            if rec_up in VALID_RECOMMENDATIONS:
                parsed["recommendation"] = rec_up
            else:
                errors.append(f"Recomendación no reconocida: {str(rec)[:80]!r}.")
                parsed.pop("recommendation", None)

        # --- 4) Validación de confianza (0-100)
        conf = parsed.get("confidence")
        if conf is not None:
            try:
                conf_f = float(conf)
                if 0 <= conf_f <= 100:
                    parsed["confidence"] = round(conf_f, 1)
                else:
                    errors.append(f"confidence fuera de rango 0-100: {conf!r}.")
                    parsed.pop("confidence", None)
            except (TypeError, ValueError):
                errors.append(f"confidence no numérico: {str(conf)[:40]!r}.")
                parsed.pop("confidence", None)

        # --- 5) Textos largos: sanitizar y acotar
        for key in PARSED_FIELDS:
            if key in parsed and isinstance(parsed[key], str):
                parsed[key] = _sanitize_text(parsed[key], 5_000)

        # --- 6) Posible prompt injection: se SEÑALA, nunca se ejecuta
        low_text = text.lower()
        flags = [p for p in _INJECTION_PHRASES if p in low_text]
        if flags:
            errors.append(
                "Posible prompt injection en el contenido (NO ejecutado, guardado como dato): " + ", ".join(flags)
            )

        # --- 7) Estado
        if "recommendation" in parsed and "confidence" in parsed:
            status = "valid"
        elif "recommendation" in parsed:
            status = "partial"
        else:
            status = "needs_validation"
        return parsed, errors, status

    # ==================================================================
    # Síntesis
    # ==================================================================
    def synthesize(self, opportunity_id: str) -> dict:
        """Agrega revisiones válidas en una síntesis. Determinista y sin LLM."""
        if self.repos.opportunities.get(opportunity_id) is None:
            raise NotFoundError("Oportunidad no encontrada.")
        reviews = self.repos.reviews.reviews_for(opportunity_id)
        valid = [r for r in reviews if r["status"] in ("valid", "partial")]
        evaluation = self.repos.evaluations.get(opportunity_id)

        distribution: dict[str, int] = {}
        for r in valid:
            rec = r["recommendation"]
            if rec:
                distribution[rec] = distribution.get(rec, 0) + 1

        confidences = [r["confidence"] for r in valid if r["confidence"] is not None]
        avg_conf = round(sum(confidences) / len(confidences), 1) if confidences else None

        risks: list[str] = []
        missing: list[str] = []
        for r in valid:
            if r["primary_risk"]:
                risks.append(_sanitize_text(r["primary_risk"], 2_000))
            if r["missing_evidence"]:
                missing.append(_sanitize_text(r["missing_evidence"], 2_000))
        repeated = sorted({r for r in risks if risks.count(r) > 1})
        unique = sorted({r for r in risks if risks.count(r) == 1})
        missing_uniq = sorted(set(missing))

        # Consenso: mayoría de recomendaciones + referencia a evidencia.
        total = len(valid)
        consensus = "NONE"
        next_action: str | None = None
        if total:
            top_rec = max(distribution, key=distribution.get) if distribution else None
            ratio = distribution.get(top_rec, 0) / total if top_rec else 0.0
            evidence_ref_ratio = sum(1 for r in valid if _URL_RE.search(r["raw_response"] or "")) / total
            if ratio >= 0.6:
                consensus = "HIGH" if evidence_ref_ratio >= 0.6 else "OPINION_CONSENSUS"
            elif ratio >= 0.4:
                consensus = "MEDIUM"
            else:
                consensus = "LOW"

            p = distribution.get("PRIORITY_EXPERIMENT", 0) / total
            s = distribution.get("SMALL_EXPERIMENT", 0) / total
            m = distribution.get("MORE_RESEARCH", 0) / total
            rej = distribution.get("REJECT", 0) / total
            if rej >= 0.5:
                next_action = "REJECT"
            elif m >= 0.5:
                next_action = "MORE_RESEARCH"
            elif p >= 0.5:
                next_action = "PRIORITY_EXPERIMENT"
            elif p + s >= 0.6:
                next_action = "SMALL_EXPERIMENT"
            else:
                next_action = "MORE_REVIEW"

        internal_before = evaluation.final_score if evaluation else None
        synthesis = ReviewSynthesis(
            opportunity_id=opportunity_id,
            reviews_count=len(reviews),
            valid_reviews_count=total,
            consensus_level=consensus,
            recommendation_distribution={k: distribution.get(k, 0) for k in VALID_RECOMMENDATIONS},
            average_confidence=avg_conf,
            agreements=[],
            disagreements=[],
            unique_risks=unique,
            repeated_risks=repeated,
            missing_evidence=missing_uniq,
            recommended_next_action=next_action,
            internal_score_before=internal_before,
            internal_score_after=internal_before,
            score_change_reason=(
                "Las revisiones externas son OPINIÓN y no modifican la puntuación interna: "
                "solo informan prioridad, riesgo y diseño del experimento. La evidencia de demanda "
                "solo puede venir de fuentes verificadas (URL + fecha + fragmento)."
            ),
        )
        saved = self.repos.reviews.save_synthesis(synthesis)
        self._log(
            agent="review_synthesis",
            opportunity_id=opportunity_id,
            summary=f"Síntesis generada: {total} revisiones válidas, consenso {consensus}, acción recomendada {next_action or '—'}.",
            decision=next_action or "no_action",
            model_or_method="deterministic aggregation",
        )
        return saved

    # ==================================================================
    # Decisión autónoma determinista (iteración 009)
    # ==================================================================
    def committee_decision(self, opportunity_id: str) -> dict:
        """Decisión autónoma por reglas deterministas (sin LLM, sin votos del
        propietario). Combina puntuación interna, evidencias, riesgos, estado
        del presupuesto, recomendaciones externas y calidad del expediente.

        Las revisiones pueden modificar PRIORIDAD y CONFIANZA (de forma
        limitada), pero NUNCA pueden: autorizar producción, aumentar
        presupuesto, mover dinero, eliminar bloqueadores, registrar ingresos
        ni convertirse en evidencia de demanda.
        """
        if self.repos.opportunities.get(opportunity_id) is None:
            raise NotFoundError("Oportunidad no encontrada.")
        item = self.repos.reviews.queue_item(opportunity_id)
        if item is None:
            raise NotFoundError("La oportunidad no está en la cola del comité.")
        evaluation = self.repos.evaluations.get(opportunity_id)
        reviews = self.repos.reviews.reviews_for(opportunity_id)
        synthesis = self.repos.reviews.get_synthesis(opportunity_id)
        packet = None
        packet_ok = False
        if self.packet_path(opportunity_id).exists():
            packet = self.get_review_packet(opportunity_id)
            packet_ok = True

        # 1) Bloqueadores críticos internos: NUNCA eliminables por opiniones.
        blockers = list(evaluation.blockers or []) if evaluation else []
        critical_risks = [
            r.description for r in (evaluation.risks or [])
            if r.severity == "high" and r.blocker
        ] if evaluation else []
        if blockers or critical_risks:
            result = {
                "opportunity_id": opportunity_id,
                "decision": "REJECT",
                "recommended_next_action": "REJECT",
                "rationale": "Bloqueadores internos críticos activos; las revisiones externas no pueden eliminarlos.",
                "reasons": ["internal_blockers", "reviews_cannot_remove_blockers"],
                "confidence_delta": -5.0,
            }
            self._log_committee_decision(opportunity_id, result, reviews)
            return result

        valid = [r for r in reviews if r["status"] in ("valid", "partial")]
        window_open = bool(item.get("window_deadline") and item["window_deadline"] > _now())
        state = item.get("status")

        # 2) Sin revisiones válidas: ausencia NEUTRAL (no bloquea, no aprueba).
        if not valid:
            if state == "continued":
                result = self._base_decision(
                    opportunity_id, item, evaluation, packet_ok,
                    extra_reason="Continuó sin revisión externa (ausencia neutral); decisión basada solo en la evaluación interna.",
                    confidence_delta=0.0,
                )
            elif window_open:
                result = {
                    "opportunity_id": opportunity_id,
                    "decision": "AWAITING_REVIEW",
                    "recommended_next_action": "AWAITING_REVIEW",
                    "rationale": "Ventana de revisión abierta sin revisiones importadas; se espera (opcional) o se puede continuar sin revisión.",
                    "reasons": ["window_open", "no_reviews"],
                    "confidence_delta": 0.0,
                }
            else:
                # Ventana caducada: _expire_pending ya debería haberlo marcado.
                result = self._base_decision(
                    opportunity_id, item, evaluation, packet_ok,
                    extra_reason="Ventana de revisión caducada sin revisiones; ausencia neutral.",
                    confidence_delta=0.0,
                )
            self._log_committee_decision(opportunity_id, result, reviews)
            return result

        # 3) Con revisiones válidas: la síntesis ajusta prioridad y confianza.
        syn = synthesis or self.synthesize(opportunity_id)
        distribution = syn.get("recommendation_distribution") or {}
        total = max(1, syn.get("valid_reviews_count") or len(valid))
        rej = distribution.get("REJECT", 0) / total
        pri = distribution.get("PRIORITY_EXPERIMENT", 0) / total
        small = distribution.get("SMALL_EXPERIMENT", 0) / total
        research = distribution.get("MORE_RESEARCH", 0) / total
        consensus = syn.get("consensus_level") or "NONE"

        # Ajuste de confianza LIMITADO (±5). El consenso de opinión sube poco;
        # el desacuerdo o el rechazo bajan; nunca modifica la puntuación interna.
        if rej >= 0.5:
            decision = "REJECT"
            delta = -5.0
            reason = "Mayoría de revisores externos recomienda REJECT (opinión; no evidencia, pero prioriza el rechazo)."
        elif consensus == "OPINION_CONSENSUS":
            decision = "MORE_RESEARCH" if research >= 0.5 else "SMALL_EXPERIMENT"
            delta = +1.0
            reason = "Consenso de opinión sin referencias de evidencia: no eleva la confianza; se recomienda más investigación antes de gastar."
        elif pri >= 0.5:
            decision = "PRIORITY_EXPERIMENT"
            delta = +3.0 if consensus == "HIGH" else +1.0
            reason = "Mayoría prioriza experimento con referencias de evidencia en las respuestas." if consensus == "HIGH" else "Mayoría prioriza experimento (consenso de opinión)."
        elif pri + small >= 0.6:
            decision = "SMALL_EXPERIMENT"
            delta = +2.0 if consensus == "HIGH" else +1.0
            reason = "Mayoría apoya un experimento pequeño."
        elif research >= 0.5:
            decision = "MORE_RESEARCH"
            delta = -2.0
            reason = "Mayoría pide más investigación; se frena el gasto hasta nueva evidencia."
        else:
            decision = "MORE_RESEARCH"
            delta = -1.0
            reason = "Sin mayoría clara entre revisores; se recomienda prudencia."

        # La decisión nunca sube de categoría sin condiciones internas mínimas.
        if decision in ("PRIORITY_EXPERIMENT", "SMALL_EXPERIMENT") and (evaluation is None or evaluation.final_score < self.settings.review_min_internal_score):
            decision = "MORE_RESEARCH"
            delta = min(delta, -1.0)
            reason += " Puntuación interna por debajo del umbral: no se avanza a experimento."

        result = {
            "opportunity_id": opportunity_id,
            "decision": decision,
            "recommended_next_action": decision,
            "rationale": reason,
            "reasons": [f"consensus={consensus}", f"distribution={distribution}", "deterministic_rule"],
            "confidence_delta": delta,
            "internal_score_unchanged": True,
            "blockers_untouched": True,
            "packet_valid": packet_ok,
        }
        self._log_committee_decision(opportunity_id, result, reviews)
        return result

    # ==================================================================
    # Operación compuesta idempotente (iteración 023)
    # ==================================================================
    def synthesize_and_decide(self, opportunity_id: str) -> dict:
        """Valida revisiones → sintetiza → decide, en UNA operación.

        Determinista, sin llamadas LLM, sin modificar evidencia y reutilizable:
        si la síntesis persistida corresponde al MISMO conjunto de revisiones,
        se reutiliza (no se duplica). El `operation_id` deriva del estado
        persistido: un reintento o una recarga de página obtiene el mismo id
        para el mismo estado. Nunca autoriza producción, gasto ni ingresos.
        """
        if self.repos.opportunities.get(opportunity_id) is None:
            raise NotFoundError("Oportunidad no encontrada.")
        reviews = self.repos.reviews.reviews_for(opportunity_id)
        valid = [r for r in reviews if r["status"] in ("valid", "partial")]
        invalid = [
            {
                "id": str(r["id"])[:8],
                "provider": r["provider"],
                "status": r["status"],
                "reason": "; ".join(r.get("parse_errors") or []) or "sin recomendación válida",
            }
            for r in reviews
            if r["status"] not in ("valid", "partial")
        ]

        # Reutilización idempotente de la síntesis previa SOLO si sigue vigente
        # para el mismo conjunto; si cambió (nueva importación), se regenera.
        synthesis = self.repos.reviews.get_synthesis(opportunity_id)
        reused = bool(synthesis) and int(synthesis.get("valid_reviews_count") or 0) == len(valid) and (
            int(synthesis.get("reviews_count") or 0) == len(reviews)
        )
        if not reused:
            synthesis = self.synthesize(opportunity_id)

        decision = self.committee_decision(opportunity_id)
        decision_value = decision.get("decision") or "MORE_RESEARCH"

        # Avance legítimo automático según la decisión.
        followup: dict = {"kind": "none"}
        if decision_value == "MORE_RESEARCH":
            mission = self._ensure_more_research_mission(opportunity_id)
            if mission:
                followup = {
                    "kind": "SPECIFIC_MISSION_CREATED",
                    "mission_id": (mission or {}).get("mission_id"),
                    "note": "Una única misión específica DEMAND_REALITY_CHECK (no se repiten las 18); indica exactamente la evidencia que falta.",
                }
            else:
                followup = {
                    "kind": "MISSION_EXISTS_OR_SKIPPED",
                    "note": "Ya existe una misión específica pendiente o el servicio de misiones no está disponible.",
                }
        elif decision_value == "REJECT":
            others = [
                {"opportunity_id": q["opportunity_id"], "internal_score": q.get("internal_score")}
                for q in self.repos.reviews.list_queue()
                if q["opportunity_id"] != opportunity_id and q.get("status") == "pending"
            ]
            followup = {
                "kind": "EVALUATE_SECOND_CANDIDATE",
                "alternatives": others[:3],
                "note": "Se conservan las candidatas investigadas reales; no se inventa sustituta.",
            }
        elif decision_value in ("SMALL_EXPERIMENT", "PRIORITY_EXPERIMENT"):
            followup = {
                "kind": "CONNECT_SERVICES_ENABLED",
                "note": "Paso CONECTAR SERVICIOS habilitado visualmente; nada se conecta automáticamente.",
            }

        # operation_id determinista a partir del estado persistido.
        fingerprint = json.dumps(
            [sorted(str(r["id"]) for r in reviews), len(valid), synthesis.get("generated_at"), decision_value],
            ensure_ascii=False,
        )
        operation_id = f"syndec-{hashlib.sha256(fingerprint.encode()).hexdigest()[:16]}"

        return {
            "model_opinion_not_evidence": True,
            "real_money_moved": False,
            "authorizes_production": False,
            "operation_id": operation_id,
            "status": "completed",
            "opportunity_id": opportunity_id,
            "reviews": {"total": len(reviews), "valid": len(valid), "invalid_or_absent": invalid},
            "synthesis": synthesis,
            "synthesis_reused": reused,
            "decision": decision,
            "winner_continues": decision_value in ("SMALL_EXPERIMENT", "PRIORITY_EXPERIMENT"),
            "followup": followup,
            "next_step_exact": self._next_step_label(decision_value),
        }

    @staticmethod
    def _next_step_label(decision_value: str) -> str:
        return {
            "SMALL_EXPERIMENT": "CONECTAR SERVICIOS (asistente gráfico; nada conectado automáticamente).",
            "PRIORITY_EXPERIMENT": "CONECTAR SERVICIOS (asistente gráfico; nada conectado automáticamente).",
            "MORE_RESEARCH": "Realizar la misión específica generada e importar su resultado en Mission Control.",
            "REJECT": "Evaluar la segunda candidata con el mismo asistente; no se inventa sustituta.",
            "AWAITING_REVIEW": "Opcional: esperar más revisiones o continuar sin revisión (ausencia neutral).",
        }.get(decision_value, "Revisar el estado del comité.")

    def _ensure_more_research_mission(self, opportunity_id: str) -> dict | None:
        """Garantiza UNA misión específica para la evidencia que falta.

        Idempotente: si ya existe una misión DEMAND_REALITY_CHECK activa
        (exported) para esta oportunidad, la devuelve sin duplicar. Nunca abre
        campaña nueva ni regenera las misiones de Fase 1.
        """
        discovery = getattr(self, "discovery", None)
        if discovery is None:
            return None
        for m in self.repos.discovery.list_missions():
            target = m.get("target") or {}
            if (
                target.get("opportunity_id") == opportunity_id
                and m.get("kind") == "DEMAND_REALITY_CHECK"
                and m.get("status") == "exported"
            ):
                return m
        try:
            mission = discovery.create_mission(kind="DEMAND_REALITY_CHECK", opportunity_id=opportunity_id)
            syn = self.repos.reviews.get_synthesis(opportunity_id) or {}
            missing = list(syn.get("missing_evidence") or [])[:5]
            target = dict(mission.target)
            if missing:
                target["missing_evidence_noted_by_committee"] = missing
            self.repos.discovery.update_mission_target(mission.mission_id, target)
            self._log(
                agent="committee_followup",
                opportunity_id=opportunity_id,
                summary=(
                    f"MORE_RESEARCH: misión específica creada ({str(mission.mission_id)[:8]}), "
                    "evidencia demandada explícita; no se abren campañas nuevas."
                ),
                decision="mission_created",
                model_or_method="deterministic_rule",
            )
            saved = self.repos.discovery.get_mission(mission.mission_id)
            return saved or {"mission_id": mission.mission_id}
        except Exception as exc:  # nunca romper la decisión por el follow-up
            self.log.warning("No se pudo crear la misión específica: %s", exc)
            return None

    def _base_decision(
        self, opportunity_id: str, item: dict, evaluation, packet_ok: bool, *, extra_reason: str, confidence_delta: float
    ) -> dict:
        """Decisión sin revisiones: solo evaluación interna (ausencia neutral)."""
        score = evaluation.final_score if evaluation else 0.0
        if score >= 80 and packet_ok:
            decision = "SMALL_EXPERIMENT"
        elif score >= self.settings.review_min_internal_score:
            decision = "MORE_RESEARCH"
        else:
            decision = "MORE_RESEARCH"
        return {
            "opportunity_id": opportunity_id,
            "decision": decision,
            "recommended_next_action": decision,
            "rationale": extra_reason + f" Puntuación interna: {score:.1f}.",
            "reasons": ["no_external_reviews", "neutral_absence"],
            "confidence_delta": confidence_delta,
            "internal_score_unchanged": True,
            "blockers_untouched": True,
            "packet_valid": packet_ok,
        }

    def _log_committee_decision(self, opportunity_id: str, result: dict, reviews: list[dict]) -> None:
        """Registra la decisión en decision_log con las garantías explícitas."""
        guarantees = {
            "authorizes_production": False,
            "raises_budget": False,
            "moves_money": False,
            "removes_blockers": False,
            "records_income": False,
            "opinion_is_evidence": False,
        }
        self._log(
            agent="committee_decision",
            opportunity_id=opportunity_id,
            summary=(
                f"Decisión autónoma: {result['decision']} (Δconfianza {result.get('confidence_delta', 0):+.1f}). "
                f"Garantías: {guarantees}. Revisiones consideradas: {len(reviews)}."
            ),
            decision=result["decision"],
            model_or_method="deterministic_rule",
        )

    def invalidate_review(self, review_id: str, *, reason: str | None = None) -> dict:
        review = self.repos.reviews.get_review(review_id)
        if review is None:
            raise NotFoundError("Revisión no encontrada.")
        if review["status"] == "invalid":
            raise ConflictError("La revisión ya está marcada como inválida.")
        updated = self.repos.reviews.update_review(review_id, status="invalid")
        self._log(
            agent="review_synthesis",
            opportunity_id=review["opportunity_id"],
            summary=f"Revisión {review_id[:8]} marcada como inválida. Motivo: {reason or 'no especificado'}.",
            decision="invalidated",
            model_or_method="human",
        )
        return updated  # type: ignore[return-value]

    # ==================================================================
    # Demostración sintética del comité de contraste
    # ==================================================================
    def run_review_demo(self, pipeline) -> dict:
        """Crea una finalista SINTÉTICA y demuestra el flujo completo.

        Todo está etiquetado como demo: la oportunidad (source=demo-review), las
        evidencias (verified=false, method=demo), las revisiones (MOCK) y la
        sobrecédula del umbral (auditable). No se inventa demanda real.
        """
        from app.models.evidence import Competitor, Evidence
        from app.models.opportunity import Opportunity

        title = "Conciliación de inventario físico-online para pequeños comercios"
        existing = self.repos.opportunities.find_similar_title(title)
        if existing:
            opportunity = self.repos.opportunities.get(existing[0].id)
        else:
            opportunity = Opportunity(
                title=title,
                problem=(
                    "Los pequeños comercios con tienda física y online pierden ventas y margen porque el "
                    "stock no coincide entre canales: venden lo que no tienen, cancelan pedidos y pasan "
                    "horas reconciliando hojas de cálculo a mano."
                ),
                proposed_solution=(
                    "Servicio de conciliación automática de inventario entre canales: integración ligera, "
                    "detección de discrepancias, alertas accionables e informe semanal. Análisis de datos, "
                    "sin prometer resultados de venta."
                ),
                target_customer=(
                    "Comercios minoristas con menos de 50 empleados que venden en tienda física y online "
                    "(p. ej. tiendas de moda o ferretería con Shopify + caja registradora)."
                ),
                sector="retail",
                source="demo-review",
            )
            self.repos.opportunities.create(opportunity)

            demo_evidence = [
                {
                    "evidence_type": "demand_signal",
                    "source_name": "(dato sintético de demostración)",
                    "summary": "DEMO: comerciantes consultados en foros de retail mencionan cancelaciones por falta de stock entre canales. Dato sintético, NO evidencia real de mercado.",
                    "reliability_score": 0.5,
                    "independence_group": "demo-a",
                    "verification_notes": "Material de demostración; no existe URL verificable real.",
                },
                {
                    "evidence_type": "customer_profile",
                    "source_name": "(dato sintético de demostración)",
                    "summary": "DEMO: perfiles hipotéticos de comercios mixtos físico+online con 1-50 empleados. Dato sintético, NO evidencia real.",
                    "reliability_score": 0.5,
                    "independence_group": "demo-b",
                    "verification_notes": "Material de demostración; no existe URL verificable real.",
                },
                {
                    "evidence_type": "technical",
                    "source_name": "(dato sintético de demostración)",
                    "summary": "DEMO: Shopify y cajas registradoras exponen APIs de inventario; la conciliación es técnicamente viable. Dato sintético, NO evidencia real.",
                    "reliability_score": 0.4,
                    "independence_group": "demo-c",
                    "verification_notes": "Material de demostración; no existe URL verificable real.",
                },
            ]
            for raw in demo_evidence:
                self.repos.evidence.create(
                    Evidence(
                        opportunity_id=opportunity.id,
                        captured_at=_now(),
                        collected_by="demo-review",
                        method="demo",
                        verified=False,
                        **raw,
                    )
                )
            self.repos.competitors.create(
                Competitor(
                    opportunity_id=opportunity.id,
                    name="(competidor sintético) app de inventario genérica",
                    offer="Herramienta genérica de inventario sin conciliación entre canales.",
                    strengths="Marca conocida, base instalada.",
                    weaknesses="No detecta discrepancias físico-online; configuración compleja; sin informe accionable.",
                )
            )

        evaluation = self.repos.evaluations.get(opportunity.id)
        if evaluation is None or self.repos.reviews.queue_item(opportunity.id) is None:
            if evaluation is None:
                evaluation = pipeline.evaluate(opportunity.id, clear_existing=False)
            self.queue_opportunity(opportunity.id, allow_demo=True, quiet=False)
            self.generate_review_packet(opportunity.id)

        # Tres revisiones MOCK claramente etiquetadas, con DESACUERDO.
        self._import_demo_review(
            opportunity.id,
            filename="revision_gpt-4o.txt",
            provider="gpt",
            model="gpt-4o",
            content=(
                "Revisión DEMO (mock) — revisión de contraste\n\n"
                "recommendation: PRIORITY_EXPERIMENT\nconfidence: 70\n"
                "strongest_evidence: El dolor de cancelaciones por stock es concreto y medible.\n"
                "weakest_assumption: Que los comercios paguen por una herramienta más.\n"
                "missing_evidence: Ninguna fuente externa verificada de demanda.\n"
                "primary_risk: Competencia de las propias plataformas (Shopify) incorporando la función.\n"
                "suggested_improvement: Empezar por un servicio concierge manual con 3 comercios.\n"
                "cheaper_experiment: Auditoría manual de stock de 2 comercios durante una semana.\n"
                "kill_condition: 0 comercios dispuestos a pagar por la auditoría manual.\n"
                "final_reasoning_summary: Dolor real pero evidencia de pago pendiente; el experimento manual es barato."
            ),
        )
        self._import_demo_review(
            opportunity.id,
            filename="revision_grok-3.txt",
            provider="grok",
            model="grok-3",
            content=(
                "Revisión DEMO (mock) — revisión de contraste\n\n"
                "recommendation: MORE_RESEARCH\nconfidence: 60\n"
                "strongest_evidence: Problema plausible en comercios mixtos.\n"
                "weakest_assumption: Que la conciliación manual sea realmente un dolor con presupuesto.\n"
                "missing_evidence: Sin evidencia de demanda externa verificada.\n"
                "primary_risk: Mercado pequeño y fragmentado; coste de adquisición alto.\n"
                "suggested_improvement: Validar primero el canal de llegada (asociaciones de comercio).\n"
                "cheaper_experiment: Página de aterrizaje con lista de espera en foros de retail.\n"
                "kill_condition: Menos de 10 inscritos en 30 días.\n"
                "final_reasoning_summary: No hay suficiente evidencia para gastar; investigar antes."
            ),
        )
        self._import_demo_review(
            opportunity.id,
            filename="revision_gemini-flash.txt",
            provider="gemini",
            model="gemini-2.0-flash",
            content=(
                "Revisión DEMO (mock) — revisión de contraste\n\n"
                "recommendation: SMALL_EXPERIMENT\nconfidence: 65\n"
                "strongest_evidence: El tiempo dedicado a hojas de cálculo es verificable en campo.\n"
                "weakest_assumption: La disposición a pagar recurrente.\n"
                "missing_evidence: Precios de alternativas actuales.\n"
                "primary_risk: Dependencia de APIs de terceros (caja registradora).\n"
                "suggested_improvement: Limitar el MVP a una integración (Shopify + una caja).\n"
                "cheaper_experiment: Informe semanal manual de discrepancias para 2 comercios piloto.\n"
                "kill_condition: Ningún comercio repite la segunda semana.\n"
                "final_reasoning_summary: Prueba acotada y barata; no justifica construir antes."
            ),
        )
        synthesis = self.synthesize(opportunity.id)
        return {
            "opportunity_id": opportunity.id,
            "title": opportunity.title,
            "internal_score": evaluation.final_score if evaluation else None,
            "threshold": self.settings.review_min_internal_score,
            "packet": self.get_review_packet(opportunity.id),
            "reviews": [r["id"] for r in self.repos.reviews.reviews_for(opportunity.id)],
            "synthesis": synthesis,
            "note": "Demostración SINTÉTICA: no representa evidencia real de mercado ni dinero real.",
        }

    def _import_demo_review(self, opportunity_id: str, *, filename: str, provider: str, model: str, content: str) -> dict:
        payload = ReviewImportIn(
            filename=filename,
            content=content,
            provider=provider,
            model=model,
            execution_mode="MOCK",
            imported_by="demo",
        )
        try:
            return self.import_review(opportunity_id, payload)
        except ConflictError:
            return {"duplicate": True}  # demo idempotente

    # ==================================================================
    # Utilidades
    # ==================================================================
    def _log(
        self,
        *,
        agent: str,
        opportunity_id: str,
        summary: str,
        decision: str | None = None,
        model_or_method: str = "review-service",
        evidence_used: list[str] | None = None,
    ) -> None:
        try:
            self.repos.decision_log.add(
                DecisionLog(
                    agent=agent,
                    opportunity_id=opportunity_id,
                    input_summary=summary[:1_000],
                    output_summary=summary[:5_000],
                    evidence_used=evidence_used or [],
                    decision=decision,
                    model_or_method=model_or_method,
                )
            )
        except Exception:
            self.log.exception("No se pudo registrar la decisión del comité de contraste")
        if self.engine is not None:
            try:
                self.engine.record_event(
                    event_type=f"review:{agent}",
                    summary=summary,
                    opportunity_id=opportunity_id,
                )
            except Exception:
                pass
