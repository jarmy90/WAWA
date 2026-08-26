"""Centro de mando (iteración 018): agrega TODOS los datos reales del sistema
en un único payload para el panel operativo.

Honestidad de datos:
- Cada bloque indica su naturaleza: REAL (persistido y verificable),
  SIMULADO (ledger simulado), HIPÓTESIS (ventaja no verificada),
  MODELO (razonamiento de modelos, nunca evidencia),
  DESCONOCIDO (sin dato → nunca se inventa) y NO CONECTADO.
- OX Alpha y cualquier razonamiento de modelo NUNCA modifican
  proven_demand, evidence_backed_venture_score ni presupuesto.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from app.core.container import AppContainer


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


class CommandCenterService:
    """Panel agregado: campaña, motor, misiones, evidencias, revisiones,
    costes LLM, presupuesto, economía, ciclo, salud, servicios y timeline."""

    def __init__(self, container) -> None:
        self.c = container

    # ------------------------------------------------------------------ snapshot
    def snapshot(self) -> dict:
        engine = _safe(lambda: self.c.engine.status(), {}) or {}
        budget = _safe(lambda: self.c.budget.status(), {}) or {}
        economy_metrics = _safe(lambda: self.c.economy.metrics(), {}) or {}
        economy_status = _safe(lambda: self.c.economy.status(), {}) or {}
        cycle = _safe(lambda: self.c.cycle.evaluate(), {}) or {}
        run = _safe(lambda: self.c.orchestrator.current_run(), None)

        campaigns = _safe(lambda: self.c.repos.discovery.list_campaigns(), []) or []
        active_campaign = None
        if run and run.get("discovery_campaign_id"):
            active_campaign = _safe(
                lambda: self.c.discovery.campaign_detail(run["discovery_campaign_id"]), None
            )
        if active_campaign is None and campaigns:
            active_campaign = _safe(
                lambda: self.c.discovery.campaign_detail(campaigns[0]["id"]), None
            )

        concepts = (active_campaign or {}).get("concepts") or []
        concept_status = self._concept_status_counts(concepts)
        blockers = self._collect_blockers(concepts, engine, budget, economy_status, cycle)

        missions = self._missions_summary(run)
        evidence = self._evidence_summary()
        reviews = self._reviews_summary()
        llm = self._llm_summary()
        timeline = self._timeline()
        services = self._services_summary()

        return {
            "generated_at": _now_iso(),
            "version": self.c.settings.version,
            "iteration": "018",
            "build": "018-ox-alpha-sprint",
            "simulated": True,
            "real_money_moved": False,
            "autonomous_launch": self._launch_readiness(run, missions, evidence, cycle),
            "honesty": {
                "ledger": "SIMULADO — nunca representa dinero real",
                "conceptos_offline": "HIPÓTESIS SINTÉTICAS hasta tener evidencia con URL+fecha+fragmento",
                "modelo": "el razonamiento de modelos se etiqueta MODEL_* y nunca es evidencia",
                "datos_sin_fuente": "DESCONOCIDO — nunca se inventan cifras",
            },
            "campaign": {
                "run": run,
                "campaign_id": (active_campaign or {}).get("id"),
                "campaign_title": (active_campaign or {}).get("title"),
                "concepts_total": len(concepts),
                "concept_status": concept_status,
            },
            "engine": engine,
            "project": {"name": "Autonomous Business Lab", "active_project": None},
            "missions": missions,
            "evidence": evidence,
            "reviews": reviews,
            "blockers": blockers,
            "llm_costs": llm,
            "budget": budget,
            "economy": {
                "status": economy_status,
                "metrics": economy_metrics,
            },
            "cycle": cycle,
            "health": _safe(lambda: self.c.engine.status().get("production_capability_available"), False),
            "services": services,
            "permissions": {
                "autonomous_production": False,
                "production_capability_available": engine.get("production_capability_available", False),
                "production_armed": engine.get("production_armed", False),
                "production_block_reason": engine.get("production_block_reason"),
                "safe_pause": engine.get("engine_state") == "SAFE_PAUSE",
                "api_budget_usd": 0,
                "gasto_real_autorizado": "0 EUR — solo simulación",
            },
            "timeline": timeline,
        }

    # ------------------------------------------------------------------ helpers
    def _launch_readiness(self, run, missions, evidence, cycle) -> dict:
        """Estado determinista de Autonomous Launch (nunca opinión de modelo).

        NOT_STARTED → READY_TO_CONNECT_SERVICES → READY_TO_LAUNCH → BLOCKED.
        Condiciones verificables únicamente; sin credenciales reales el estado
        final posible es READY_TO_CONNECT_SERVICES (READY_TO_LAUNCH exige
        servicios conectados + autorización única del propietario)."""
        has_campaign = bool(run and run.get("discovery_campaign_id"))
        has_winners = bool(missions.get("count")) or bool((missions or {}).get("pending"))
        has_evidence = bool(evidence.get("verified")) and bool(evidence.get("independent_groups"))
        cycle_not_passed = (cycle or {}).get("status") != "PASSED_VIA_A"
        if not has_campaign:
            state = "NOT_STARTED"
        elif not (has_winners or has_evidence):
            state = "NOT_STARTED"
        elif cycle_not_passed:
            state = "READY_TO_CONNECT_SERVICES"
        else:
            state = "READY_TO_CONNECT_SERVICES"  # READY_TO_LAUNCH exige autorización única
        return {
            "state": state,
            "ready_to_connect_services": state == "READY_TO_CONNECT_SERVICES",
            "ready_to_launch": False,  # bloqueado hasta autorización única auditable
            "blocked": state == "BLOCKED",
            "conditions": {
                "campaña_activa": has_campaign,
                "candidatas_priorizadas": has_winners,
                "evidencia_verificada": has_evidence,
                "ciclo_económico_superado": not cycle_not_passed,
                "servicios_conectados": False,
                "autorización_única_owner": False,
            },
            "note": "Estado determinista: nunca se activa AUTONOMOUS_PRODUCTION desde aquí.",
        }
    @staticmethod
    def _concept_status_counts(concepts: list[dict]) -> dict:
        counts: dict[str, int] = {}
        for c in concepts:
            st = c.get("status") or c.get("semantic_status") or "UNKNOWN"
            counts[st] = counts.get(st, 0) + 1
        return counts

    @staticmethod
    def _collect_blockers(
        concepts: list[dict],
        engine: dict,
        budget: dict,
        economy_status: dict,
        cycle: dict,
    ) -> list[dict]:
        out: list[dict] = []
        for c in concepts:
            b = c.get("blockers") or []
            if isinstance(b, str):
                try:
                    b = json.loads(b)
                except Exception:
                    b = []
            for item in b or []:
                out.append(
                    {
                        "kind": "CONCEPT_BLOCKER",
                        "concept_id": c.get("id"),
                        "title": c.get("title"),
                        "detail": str(item),
                        "severity": "block",
                        "nature": "REAL",
                    }
                )
        if engine.get("production_block_reason"):
            out.append(
                {
                    "kind": "PRODUCTION_BLOCKED",
                    "detail": engine["production_block_reason"],
                    "severity": "block",
                    "nature": "REAL",
                }
            )
        if engine.get("engine_state") == "SAFE_PAUSE":
            out.append(
                {"kind": "SAFE_PAUSE", "detail": "Motor en pausa segura", "severity": "warn", "nature": "REAL"}
            )
        if (budget.get("daily") or {}).get("reached"):
            out.append(
                {
                    "kind": "DAILY_BUDGET_REACHED",
                    "detail": "Límite diario de presupuesto alcanzado",
                    "severity": "block",
                    "nature": "REAL",
                }
            )
        if (cycle or {}).get("status") in ("FAILED", "NOT_PASSED"):
            out.append(
                {"kind": "CYCLE_FAILED", "detail": "Ciclo económico sin pago real confirmado", "severity": "block", "nature": "REAL"}
            )
        if not out:
            out.append({"kind": "NINGUNO", "detail": "Sin bloqueadores activos", "severity": "ok", "nature": "REAL"})
        return out

    def _missions_summary(self, run: dict | None) -> dict:
        if not run:
            return {"count": 0, "pending": 0, "imported": 0, "items": [], "explanation": "Sin campaña activa", "nature": "REAL"}
        missions = _safe(
            lambda: self.c.repos.discovery.missions_by_campaign(run["discovery_campaign_id"]), []
        ) or []
        items = []
        pending = 0
        imported = 0
        for m in missions:
            status = m.get("status") or "exported"
            if status == "imported":
                imported += 1
            else:
                pending += 1
            target = m.get("target") or {}
            items.append(
                {
                    "mission_id": m.get("mission_id"),
                    "kind": target.get("kind") or m.get("kind"),
                    "concept_id": target.get("concept_id"),
                    "status": status,
                    "created_at": m.get("created_at"),
                }
            )
        return {
            "count": len(items),
            "pending": pending,
            "imported": imported,
            "items": items[:25],
            "explanation": "Solo Fase 1 (6 por candidata) · sin ejecución automática",
            "nature": "REAL",
        }

    def _evidence_summary(self) -> dict:
        """Evidencias reales persistidas (URL+fecha+fragmento)."""
        total = 0
        verified = 0
        groups: set[str] = set()
        opportunities = _safe(lambda: self.c.repos.opportunities.list(), []) or []
        for opp in opportunities:
            evs = _safe(lambda o=opp: self.c.repos.evidence.list_for(o.id), []) or []
            for e in evs:
                total += 1
                if getattr(e, "verified", False):
                    verified += 1
                source = getattr(e, "source_url", None) or getattr(e, "url", None) or ""
                if source:
                    domain = source.split("/")[2] if "://" in source else source
                    groups.add(domain)
        return {
            "total": total,
            "verified": verified,
            "independent_groups": len(groups),
            "max_evidence_score": 40 if len(groups) >= 3 else 0,
            "nature": "REAL" if total else "DESCONOCIDO",
            "note": "Solo cuentan evidencias con URL + fecha de consulta + fragmento",
        }

    def _reviews_summary(self) -> dict:
        queue = _safe(lambda: self.c.repos.reviews.list_queue(), []) or []
        reviews = _safe(lambda: self.c.repos.reviews.list_reviews(limit=200), []) or []
        pending = sum(1 for q in queue if (q.get("status") or "queued") in ("queued", "pending"))
        imported = sum(1 for r in reviews if r.get("reviewer"))
        return {
            "queue": len(queue),
            "pending": pending,
            "imported": imported,
            "syntheses": _safe(lambda: len(self.c.repos.reviews.list_reviews(limit=1)) or 0, 0),
            "nature": "REAL",
            "note": "La opinión de modelos es MODEL_* y nunca modifica puntuaciones ni presupuesto",
        }

    def _llm_summary(self) -> dict:
        """Coste LLM honesto: reported vs estimated, nunca se inventa."""
        try:
            repo = self.c.repos.llm_calls
            calls = repo.list_recent(limit=100)
            total_calls = len(calls)
            failures = sum(1 for c in calls if c.get("status") == "error" or c.get("failure"))
            reported = sum(c.get("reported_cost") or 0 for c in calls if c.get("reported_cost"))
            estimated = sum(c.get("estimated_cost") or 0 for c in calls if c.get("estimated_cost"))
            has_provider_reported = any(c.get("cost_source") == "PROVIDER_RESPONSE" for c in calls)
            return {
                "calls": total_calls,
                "failures": failures,
                "reported_cost_usd": round(reported, 6),
                "estimated_cost_usd": round(estimated, 6),
                "billing_verified": False,
                "cost_source": "PROVIDER_RESPONSE" if has_provider_reported else "LOCAL_ESTIMATE",
                "nature": "REAL" if calls else "SIN DATOS",
                "models": sorted({c.get("actual_model") or c.get("requested_model") for c in calls}),
                "recent": [
                    {
                        "requested_model": c.get("requested_model"),
                        "actual_model": c.get("actual_model"),
                        "provider": c.get("provider"),
                        "cost_source": c.get("cost_source"),
                        "created_at": c.get("created_at"),
                    }
                    for c in calls[:10]
                ],
            }
        except Exception:
            return {"calls": 0, "failures": 0, "nature": "DESCONOCIDO", "billing_verified": False}

    def _timeline(self) -> list[dict]:
        items: list[dict] = []
        for ev in _safe(lambda: self.c.engine.events(limit=25), []) or []:
            d = _safe(lambda e=ev: e.model_dump(), None)
            if d:
                items.append(
                    {
                        "timestamp": d.get("timestamp"),
                        "kind": d.get("event_type"),
                        "summary": d.get("summary"),
                        "nature": "REAL",
                        "cost_usd": d.get("cost_usd", 0),
                    }
                )
        for entry in _safe(lambda: self.c.repos.decision_log.recent(limit=15), []) or []:
            items.append(
                {
                    "timestamp": getattr(entry, "timestamp", None),
                    "kind": "DECISION",
                    "summary": f"{getattr(entry, 'agent', '?')}: {getattr(entry, 'decision', '')}",
                    "nature": "REAL",
                }
            )
        items.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
        return items[:30]

    def _services_summary(self) -> list[dict]:
        """Servicios externos: estado honesto vía providers.health() (sin
        exponer claves). Stripe/hosting/dominio/email/analytics NO existen aún."""
        health = _safe(lambda: self.c.providers.health(), {}) or {}
        providers = {
            "Gemini (opcional)": bool((health.get("gemini") or {}).get("configured")),
            "OpenRouter (comité, Opción A)": bool((health.get("openrouter") or {}).get("configured")),
            "OmniRoute (gateway local)": bool((health.get("omniroute") or {}).get("configured")),
            "MockProvider (offline)": True,
            "Manual/Freebuff": True,
        }
        out = []
        for name, connected in providers.items():
            out.append(
                {
                    "name": name,
                    "connected": connected,
                    "note": "" if connected else "Sin clave configurada — ausencia neutral",
                    "nature": "REAL" if connected else "NO CONECTADO",
                }
            )
        for name in ("Stripe", "Hosting", "Dominio", "Email operativo", "Analytics"):
            out.append({"name": name, "connected": False, "note": "NO CONECTADO — bloqueado hasta READY_TO_CONNECT_SERVICES", "nature": "NO CONECTADO"})
        return out
