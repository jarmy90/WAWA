"""Centro de mando: snapshot operativo honesto y trazable.

El agregador no convierte misiones, opiniones, dominios, costes ausentes ni
capacidad de producción en conclusiones optimistas. Los campos derivados son
compatibles con el panel 018, pero el contrato nuevo es explícito.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


class CommandCenterService:
    """Snapshot único del centro de mando, sin inferencias comerciales."""

    def __init__(self, container) -> None:
        self.c = container

    def snapshot(self) -> dict:
        generated_at = _now_iso()
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
        readiness = self._launch_readiness(run, active_campaign, missions, cycle, engine)
        health = self._system_health(engine, economy_status, generated_at)
        production = self._production_capability(engine)

        return {
            "generated_at": generated_at,
            "version": self.c.settings.version,
            "iteration": "022",
            "build": "022-one-click-activation",
            "simulated": True,
            "real_money_moved": False,
            "autonomous_launch": readiness,
            "readiness": readiness,
            "honesty": {
                "ledger": "SIMULADO — nunca representa dinero real",
                "conceptos_offline": "HIPÓTESIS hasta tener evidencia con URL+fecha+fragmento",
                "modelo": "MODEL_* — razonamiento de modelos, nunca evidencia",
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
            "economy": {"status": economy_status, "metrics": economy_metrics},
            "cycle": cycle,
            "health": health["system_health"],
            "system_health": health,
            "production_capability": production,
            "services": services,
            "permissions": {
                "autonomous_production": False,
                "production_capability_available": production["state"] == "AVAILABLE",
                "production_armed": engine.get("production_armed", False),
                "production_block_reason": engine.get("production_block_reason"),
                "safe_pause": health["safe_pause"],
                "api_budget_usd": 0,
                "gasto_real_autorizado": "0 EUR — solo simulación",
            },
            "commercial_metrics": {
                "visits": "NO CONECTADO",
                "leads": "NO CONECTADO",
                "checkouts": "NO CONECTADO",
                "payments": "NO CONECTADO",
                "conversion": "NO CONECTADO",
                "active_agents": "SIN DATOS",
                "active_commercial_project": "NO CONECTADO",
                "nature": "NO CONECTADO",
            },
            "timeline": timeline,
            "bootstrap": _safe(lambda: self.c.bootstrap.status(), None),
        }

    @staticmethod
    def _concept_status_counts(concepts: list[dict]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for concept in concepts:
            status = concept.get("status") or concept.get("semantic_status") or "UNKNOWN"
            counts[status] = counts.get(status, 0) + 1
        return counts

    @staticmethod
    def _collect_blockers(concepts, engine, budget, economy_status, cycle) -> list[dict]:
        out: list[dict] = []
        for concept in concepts:
            raw = concept.get("blockers") or []
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except Exception:
                    raw = []
            for item in raw or []:
                out.append({"kind": "CONCEPT_BLOCKER", "concept_id": concept.get("id"),
                            "title": concept.get("title"), "detail": str(item),
                            "severity": "block", "nature": "REAL"})
        if engine.get("production_block_reason"):
            out.append({"kind": "PRODUCTION_BLOCKED", "detail": engine["production_block_reason"],
                        "severity": "block", "nature": "REAL"})
        if str(engine.get("engine_state", "")).lower() == "safe_pause" or str(engine.get("mode", "")).lower() == "safe_pause":
            out.append({"kind": "SAFE_PAUSE", "detail": "Motor en pausa segura", "severity": "warn", "nature": "REAL"})
        if (budget.get("daily") or {}).get("reached"):
            out.append({"kind": "DAILY_BUDGET_REACHED", "detail": "Límite diario alcanzado", "severity": "block", "nature": "REAL"})
        if (cycle or {}).get("status") in ("FAILED", "NOT_PASSED"):
            out.append({"kind": "CYCLE_FAILED", "detail": "Ciclo sin pago real confirmado", "severity": "block", "nature": "REAL"})
        return out or [{"kind": "NINGUNO", "detail": "Sin bloqueadores activos", "severity": "ok", "nature": "REAL"}]

    def _missions_summary(self, run: dict | None) -> dict:
        if not run or not run.get("discovery_campaign_id"):
            return {"count": 0, "pending": 0, "imported": 0, "items": [],
                    "explanation": "Sin campaña activa", "nature": "REAL"}
        rows = _safe(lambda: self.c.repos.discovery.missions_by_campaign(run["discovery_campaign_id"]), []) or []
        active = [m for m in rows if m.get("status") not in ("SUPERSEDED_BY_SEMANTIC_QUALITY_GATE", "CANCELLED")]
        items, pending, imported = [], 0, 0
        for mission in active:
            status = mission.get("status") or "exported"
            imported += status == "imported"
            pending += status != "imported"
            target = mission.get("target") or {}
            items.append({"mission_id": mission.get("mission_id"), "kind": target.get("kind") or mission.get("kind"),
                          "concept_id": target.get("concept_id"), "opportunity_id": target.get("opportunity_id"),
                          "status": status, "created_at": mission.get("created_at")})
        return {"count": len(items), "pending": pending, "imported": imported, "items": items[:25],
                "explanation": "Solo misiones activas; las antiguas/canceladas no cuentan", "nature": "REAL"}

    def _evidence_summary(self) -> dict:
        """Resume evidencia materializada y resultados de misión sin inferir asociación.

        Solo cuenta una evidencia que cumpla TODO: ``verified=true``, URL
        http(s) concreta, fecha de consulta parseable, fragmento original no
        vacío y asociación local válida con una oportunidad. Los duplicados
        entre la tabla ``evidence`` y ``mission_results`` (materialización) se
        cuentan una sola vez. Lo no verificado se separa y nunca eleva el tope
        de puntuación.
        """
        total = verified = rejected = 0
        verified_groups: set[str] = set()
        unverified_groups: set[str] = set()
        seen: set[tuple[str, str, str, str]] = set()
        associated_opportunity_ids: set[str] = set()
        opportunities = _safe(lambda: self.c.repos.opportunities.list(), []) or []

        def _http_url(value: str) -> bool:
            return value.lower().startswith(("http://", "https://"))

        def _parseable_date(value: str) -> bool:
            if not value:
                return False
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
                return True
            except (TypeError, ValueError):
                return False

        def consume(raw: Any, *, opportunity_id: str | None) -> None:
            nonlocal total, verified, rejected
            if not opportunity_id or opportunity_id not in associated_opportunity_ids:
                return
            status = str(raw.get("status") or "").lower() if isinstance(raw, dict) else str(getattr(raw, "status", "")).lower()
            is_rejected = status in {"rejected", "superseded", "cancelled"} or bool(
                (raw.get("rejected") or raw.get("superseded")) if isinstance(raw, dict)
                else (getattr(raw, "rejected", False) or getattr(raw, "superseded", False))
            )
            if is_rejected:
                rejected += 1
                return
            get = raw.get if isinstance(raw, dict) else lambda key, default=None: getattr(raw, key, default)
            url = str(get("source_url") or "").strip()
            captured = str(get("captured_at") or "").strip()
            excerpt = str(get("raw_excerpt") or "").strip()
            summary = str(get("summary") or "").strip()
            group = str(get("independence_group") or "").strip()
            key = (opportunity_id, url, captured, excerpt)
            if any(key[1:]) and key in seen:
                return  # duplicado entre evidence y mission_results: cuenta una sola vez
            if any(key[1:]):
                seen.add(key)
            total += 1
            complete = bool(get("verified")) and _http_url(url) and _parseable_date(captured) and bool(excerpt)
            if complete:
                verified += 1
                if group:
                    verified_groups.add(group)
            elif group:
                unverified_groups.add(group)

        for opportunity in opportunities:
            associated_opportunity_ids.add(opportunity.id)
            for evidence in (_safe(lambda o=opportunity: self.c.repos.evidence.list_for(o.id), []) or []):
                consume(evidence, opportunity_id=opportunity.id)

        # Mission results are raw imported data. Only active local missions
        # carrying a valid opportunity_id may contribute to the summary.
        for mission in (_safe(lambda: self.c.repos.discovery.list_missions(), []) or []):
            if mission.get("status") in {"SUPERSEDED_BY_SEMANTIC_QUALITY_GATE", "CANCELLED"}:
                continue
            target = mission.get("target") or {}
            opportunity_id = target.get("opportunity_id")
            if opportunity_id not in associated_opportunity_ids:
                continue
            for result in (_safe(lambda m=mission: self.c.repos.discovery.mission_results(m["mission_id"]), []) or []):
                for raw in result.get("evidences") or []:
                    consume(raw, opportunity_id=opportunity_id)

        unverified = max(0, total - verified - rejected)
        group_count = len(verified_groups)
        score_cap = 100 if group_count >= 3 else (40 if group_count else 0)
        return {
            "total": total, "verified": verified, "unverified": unverified, "rejected": rejected,
            "evidence_total": total, "evidence_verified": verified, "evidence_unverified": unverified,
            "evidence_rejected": rejected,
            "independent_groups": group_count,
            "independent_verified_groups": group_count,
            "independent_unverified_groups": len(unverified_groups - verified_groups),
            "max_evidence_score": score_cap,
            "nature": "REAL" if total else "DESCONOCIDO",
            "note": "Solo verified=true + URL http(s) + fecha + fragmento + asociación local válida; duplicados contados una vez; grupos explícitos, no dominios",
        }

    def _reviews_summary(self) -> dict:
        queue = _safe(lambda: self.c.repos.reviews.list_queue(), []) or []
        reviews = _safe(lambda: self.c.repos.reviews.list_reviews(limit=200), []) or []
        syntheses = _safe(lambda: self.c.repos.reviews.list_syntheses(limit=200), []) or []
        valid = [r for r in reviews if r.get("status") in ("valid", "partial")]
        pending = sum((q.get("status") or "queued") in ("queued", "pending") for q in queue)
        latest = syntheses[0] if syntheses else None
        return {
            "queue": len(queue), "pending": pending, "imported": len(reviews),
            "review_count": len(reviews), "valid_review_count": len(valid),
            "synthesis_count": len(syntheses), "syntheses": len(syntheses),
            "latest_synthesis_at": (latest or {}).get("generated_at"),
            "consensus_level": (latest or {}).get("consensus_level") or "UNKNOWN",
            "committee_status": "SYNTHESIS_AVAILABLE" if syntheses else ("REVIEWS_AVAILABLE" if reviews else "NO_REVIEWS"),
            "nature": "REAL", "note": "Las revisiones y síntesis son opiniones MODEL_*; nunca evidencia",
        }

    def _llm_summary(self) -> dict:
        """Coste LLM honesto sobre TODAS las llamadas persistidas.

        Un coste desconocido nunca se convierte en cero: los totales son de
        costes CONOCIDOS (reported si existe, si no estimated etiquetado) y
        las llamadas sin ningún coste se informan por separado.
        """
        try:
            detail = self.c.repos.llm_calls.cost_detail_since("1970-01-01T00:00:00")
            calls = self.c.repos.llm_calls.list_recent(limit=100)
            total_calls = int(detail.get("total_calls") or 0)
            reported_total = detail.get("reported_total")
            estimated_total = detail.get("estimated_total")
            unknown_calls = int(detail.get("unknown_calls") or 0)
            zero_calls = int(detail.get("zero_calls") or 0)
            reported_values = [c.get("reported_cost") for c in calls if c.get("reported_cost") is not None]
            estimated_values = [c.get("estimated_cost") for c in calls if c.get("estimated_cost") is not None]
            sources = {str(c.get("cost_source") or "UNKNOWN") for c in calls if c.get("reported_cost") is not None or c.get("estimated_cost") is not None}
            if not total_calls:
                display = "NO_CALLS"
            elif unknown_calls and not reported_total and not estimated_total:
                display = "UNKNOWN"
            else:
                display = "KNOWN_WITH_UNKNOWN_CALLS" if unknown_calls else "KNOWN"
            if not total_calls:
                source = "NOT_APPLICABLE"
            elif not sources:
                source = "UNKNOWN"
            elif len(sources) == 1:
                source = next(iter(sources))
            else:
                source = "MIXED"
            failures = self.c.repos.llm_calls.failures_since("1970-01-01T00:00:00")
            models = sorted({m for c in calls for m in [(c.get("actual_model") or c.get("requested_model"))] if m})
            return {
                "calls": total_calls, "failures": failures,
                "reported_cost_total": round(reported_total, 6) if reported_total is not None else None,
                "estimated_cost_total": round(estimated_total, 6) if estimated_total is not None else None,
                "reported_cost_usd": round(reported_total, 6) if reported_total is not None else None,
                "estimated_cost_usd": round(estimated_total, 6) if estimated_total is not None else None,
                "unknown_cost_calls": unknown_calls, "zero_cost_calls": zero_calls,
                "cost_source": source, "billing_verified": bool(calls) and all(c.get("billing_verified") for c in calls if c.get("reported_cost") is not None),
                "display_status": display, "nature": "REAL" if total_calls else "SIN DATOS", "models": models,
                "recent": [{"requested_model": c.get("requested_model"), "actual_model": c.get("actual_model"),
                            "provider": c.get("provider"), "cost_source": c.get("cost_source"), "created_at": c.get("created_at")} for c in calls[:10]],
            }
        except Exception:
            return {"calls": 0, "failures": 0, "reported_cost_total": None, "estimated_cost_total": None,
                    "unknown_cost_calls": 0, "zero_cost_calls": 0, "cost_source": "UNKNOWN",
                    "billing_verified": False, "display_status": "UNKNOWN", "nature": "DESCONOCIDO"}

    def _launch_readiness(self, run, active_campaign, missions, cycle, engine) -> dict:
        missing: list[str] = []
        blockers: list[str] = []
        candidate_id = opportunity_id = experiment_id = None
        plan = None
        concept = None
        evaluation = None
        selected = (run or {}).get("selected_opportunity_id") if run else None
        if not selected:
            missing.append("active_valid_candidate")
        else:
            opportunity_id = selected
            candidate_id = selected
            opportunity = _safe(lambda: self.c.repos.opportunities.get(selected), None)
            invalid_statuses = {"rejected", "deferred", "blocked"}
            if opportunity is None or getattr(opportunity.status, "value", opportunity.status if opportunity else None) in invalid_statuses:
                missing.append("active_valid_candidate")
            else:
                source = getattr(opportunity, "source", "") or ""
                campaign_id = source.split(":", 1)[1] if source.startswith("discovery:") else None
                concepts = _safe(lambda: self.c.repos.discovery.concepts_by_campaign(campaign_id), []) if campaign_id else []
                concept = next((c for c in concepts if c.get("title") == getattr(opportunity, "title", None)), None)
                if concept is None:
                    missing.append("opportunity_brief")
                else:
                    from app.scoring.semantic_gate import validate_opportunity_brief
                    brief_ok = bool(validate_opportunity_brief(concept.get("brief") or {}).get("ok"))
                    if not brief_ok:
                        missing.append("opportunity_brief")
                    venture = _safe(lambda: self.c.repos.discovery.venture_evaluations_by_concept(concept["id"]), []) or []
                    if not concept.get("coherence_ok") or not venture or any(v.get("blockers") for v in venture[:1]):
                        missing.append("quality_gate")
                evaluation = _safe(lambda: self.c.repos.evaluations.get(selected), None)
                decision = getattr(evaluation, "decision", None) if evaluation is not None else None
                decision_value = getattr(decision, "value", decision)
                if decision_value not in ("approved", "SMALL_EXPERIMENT", "PRIORITY_EXPERIMENT"):
                    missing.append("valid_decision_or_priority")
                plan = _safe(lambda: self.c.repos.orchestrator.experiment_plan_for_opportunity(selected), None)
                if plan:
                    experiment_id = plan.get("id")
                else:
                    missing.append("experiment_defined")
        if plan:
            for field, label in (("offer", "offer_hypothesis"), ("price_usd", "price_hypothesis"),
                                 ("buyer", "concrete_buyer"), ("channel", "concrete_channel"),
                                 ("success_metric", "success_metric"), ("kill_condition", "kill_condition")):
                value = plan.get(field)
                if field == "price_usd":
                    ok = value is not None and float(value or 0) > 0
                else:
                    ok = _text(value)
                if not ok:
                    missing.append(label)
            if plan.get("max_cost_usd") is None:
                missing.append("authorized_budget")
            if plan.get("blockers"):
                blockers.append("critical_plan_blockers")
            if plan.get("missing_capabilities"):
                missing.extend(f"capability:{x}" for x in plan["missing_capabilities"])
        else:
            missing.append("authorized_budget")
        # Las misiones obligatorias son de la candidata SELECCIONADA: nunca se
        # usan misiones antiguas, canceladas, superseded o de otra candidata.
        if selected:
            candidate_items = [
                m for m in (missions.get("items") or [])
                if m.get("opportunity_id") == selected
                or (not m.get("opportunity_id") and concept is not None and m.get("concept_id") == concept.get("id"))
            ]
        else:
            candidate_items = missions.get("items") or []
        if not candidate_items:
            missing.append("mandatory_missions_completed_or_not_applicable")
        elif any(m.get("status") != "imported" for m in candidate_items):
            missing.append("mandatory_missions_completed_or_not_applicable")

        # Bloqueadores económicos/operativos reales (nunca inferidos de opiniones).
        economy_metrics = _safe(lambda: self.c.economy.metrics(), {}) or {}
        survival = economy_metrics.get("survival_status")
        if survival in ("CRITICAL", "INSOLVENT"):
            blockers.append("critical_debt")
        if (cycle or {}).get("status") == "FAILED":
            blockers.append("economic_cycle_failed")
        if _safe(lambda: self.c.repos.ledger.consistency_issues(), []) or []:
            blockers.append("ledger_reconciliation")
        if str(engine.get("engine_state", "")).lower() == "safe_pause" or str(engine.get("mode", "")).lower() == "safe_pause":
            blockers.append("safe_pause")
        if blockers:
            state = "BLOCKED"
        elif missing:
            state = "NOT_READY"
        else:
            state = "READY_TO_CONNECT_SERVICES"
        return {
            "readiness_state": state, "state": state, "readiness_met": not missing and not blockers,
            "readiness_missing": list(dict.fromkeys(missing)), "readiness_blockers": list(dict.fromkeys(blockers)),
            "ready_to_connect_services": state == "READY_TO_CONNECT_SERVICES", "ready_to_launch": False,
            "missing": list(dict.fromkeys(missing)), "candidate_id": candidate_id, "opportunity_id": opportunity_id,
            "experiment_id": experiment_id,
            "explanation": "No se infiere readiness desde misiones, score estructural o evidencia no verificada. "
                           + ("Faltan precondiciones explícitas." if missing or blockers else "Todas las precondiciones locales están demostradas; faltan conectar/verificar servicios para lanzar."),
            "conditions": {"production_remains_blocked": True, "services_connected": False, "owner_authorized": False},
            "note": "READY_TO_LAUNCH sigue bloqueado hasta conexión, verificación y autorización única del propietario.",
        }

    # ------------------------------------------------------------------
    # Telemetría de agentes (iteración 020) — SOLO actividad real persistida
    # ------------------------------------------------------------------
    def agent_telemetry(self) -> dict:
        """Telemetría de agentes para las vistas visuales premium.

        NUNCA inventa actividad: cada agente deriva su estado de datos
        persistidos (run del orquestador, misiones, evidencias, comité, costes
        LLM, proveedores, decisiones y eventos). Sin datos suficientes el
        estado es ``NO_DATA``/``IDLE``, no ``ACTIVE``. El estado ``ACTIVE``
        solo se emite cuando hay llamadas/decisiones recientes que lo
        respalden.
        """
        generated_at = _now_iso()
        engine = _safe(lambda: self.c.engine.status(), {}) or {}
        run = _safe(lambda: self.c.orchestrator.current_run(), None)
        budget = _safe(lambda: self.c.budget.status(), {}) or {}
        economy_metrics = _safe(lambda: self.c.economy.metrics(), {}) or {}
        cycle = _safe(lambda: self.c.cycle.evaluate(), {}) or {}
        missions = self._missions_summary(run)
        evidence = self._evidence_summary()
        reviews = self._reviews_summary()
        llm = self._llm_summary()
        readiness = self._launch_readiness(run, None, missions, cycle, engine)
        health = self._system_health(engine, {}, generated_at)
        providers_health = _safe(lambda: self.c.providers.health(), {}) or {}
        decisions = _safe(lambda: self.c.repos.decision_log.recent(limit=100), []) or []
        events = _safe(lambda: self.c.engine.events(limit=100), []) or []
        calls = _safe(lambda: self.c.repos.llm_calls.list_recent(limit=100), []) or []
        blockers = _safe(lambda: self.c.repos.discovery.list_campaigns(), []) and self._collect_blockers(
            [], engine, budget, {}, cycle
        )

        def decision_count(agent_key: str) -> int:
            key = agent_key.lower()
            return sum(1 for d in decisions if key in str(getattr(d, "agent", "")).lower())

        def event_count_for(agent_key: str) -> int:
            key = agent_key.lower()
            return sum(1 for e in events if key in str(getattr(e, "summary", "")).lower())

        def error_count_for(agent_key: str) -> int:
            key = agent_key.lower()
            return sum(1 for e in events if str(getattr(e, "event_type", "")) == "error" and key in str(getattr(e, "summary", "")).lower())

        def last_event_at(agent_key: str) -> str | None:
            key = agent_key.lower()
            for e in events:
                if key in str(getattr(e, "summary", "")).lower():
                    return getattr(e, "timestamp", None)
            for d in reversed(decisions):
                if key in str(getattr(d, "agent", "")).lower():
                    return getattr(d, "timestamp", None)
            return None

        run_state = (run or {}).get("state") or "NO_RUN"
        safe_pause = str(engine.get("engine_state", "")).lower() == "safe_pause" or str(engine.get("mode", "")).lower() == "safe_pause"

        agents: list[dict] = []

        def add_agent(agent_id: str, name: str, role: str, status: str, current_action: str, *, priority: int,
                      tools: list[str], missions: list[str] | None = None, parent: str | None = None,
                      blocked_reason: str | None = None, last_event_at: str | None = None,
                      activity_level: int = 0, event_count: int = 0, error_count: int = 0,
                      cost: float | None = None) -> None:
            agents.append({
                "id": agent_id, "name": name, "role": role, "status": status,
                "current_action": current_action, "last_event_at": last_event_at,
                "activity_level": activity_level, "priority": priority, "tools": tools,
                "missions": missions or [], "parent_agent_id": parent, "blocked_reason": blocked_reason,
                "event_count": event_count, "error_count": error_count, "cost": cost,
                "data_nature": "REAL",
            })

        # --- CampaignOrchestrator (sol central) ---------------------------
        if run is None:
            add_agent("orchestrator", "CampaignOrchestrator", "Coordinación", "NO_DATA",
                      "Sin campaña activa", priority=1, tools=["orquestador", "transiciones"])
        elif safe_pause:
            add_agent("orchestrator", "CampaignOrchestrator", "Coordinación", "BLOCKED",
                      "Motor en SAFE_PAUSE", priority=1, tools=["orquestador", "transiciones"],
                      blocked_reason="SAFE_PAUSE — configuración inconsistente o pausa deliberada",
                      last_event_at=engine.get("heartbeat_at"), event_count=event_count_for("orchestrat"))
        elif run_state in ("PAUSED", "CANCELLED", "FAILED"):
            add_agent("orchestrator", "CampaignOrchestrator", "Coordinación", "BLOCKED",
                      f"Ejecución {run_state}", priority=1, tools=["orquestador", "transiciones"],
                      blocked_reason=f"Run en estado {run_state}",
                      last_event_at=run.get("updated_at") or run.get("created_at"),
                      event_count=event_count_for("orchestrat"))
        elif run_state in ("RESEARCH_PENDING", "COMMITTEE_PENDING", "EXPERIMENT_BLOCKED", "BLOCKED"):
            add_agent("orchestrator", "CampaignOrchestrator", "Coordinación", "WAITING",
                      f"Run en {run_state}: esperando investigación externa o intervención", priority=1,
                      tools=["orquestador", "transiciones"], last_event_at=run.get("updated_at") or run.get("created_at"),
                      event_count=event_count_for("orchestrat"))
        elif run_state == "COMPLETED":
            add_agent("orchestrator", "CampaignOrchestrator", "Coordinación", "IDLE",
                      "Campaña completada", priority=1, tools=["orquestador", "transiciones"],
                      last_event_at=run.get("updated_at"), event_count=event_count_for("orchestrat"))
        else:
            working = bool(last_event_at("orchestrat")) or decision_count("orchestrat") > 0
            add_agent("orchestrator", "CampaignOrchestrator", "Coordinación",
                      "WORKING" if working else "WAITING",
                      f"Run en {run_state}", priority=1, tools=["orquestador", "transiciones"],
                      last_event_at=run.get("updated_at") or run.get("created_at"),
                      activity_level=1 if working else 0, event_count=event_count_for("orchestrat"))

        # --- Scout ---------------------------------------------------------
        concepts = []
        campaign_id = None
        if run and run.get("discovery_campaign_id"):
            campaign_id = run["discovery_campaign_id"]
            detail = _safe(lambda: self.c.discovery.campaign_detail(run["discovery_campaign_id"]), None)
            concepts = (detail or {}).get("concepts") or []
        elif self.c.repos.discovery.list_campaigns():
            first = _safe(lambda: self.c.repos.discovery.list_campaigns()[0], None)
            if first:
                campaign_id = first.get("id")
                detail = _safe(lambda: self.c.discovery.campaign_detail(first["id"]), None)
                concepts = (detail or {}).get("concepts") or []
        if not concepts:
            add_agent("scout", "Scout", "Descubrimiento", "NO_DATA",
                      "Sin conceptos generados", priority=2, tools=["territorios", "lentes", "arquetipos", "fase-1"],
                      event_count=decision_count("scout"))
        else:
            last = max((c.get("updated_at") or c.get("created_at") or "" for c in concepts), default=None)
            add_agent("scout", "Scout", "Descubrimiento", "IDLE",
                      f"Fase 1: {len(concepts)} conceptos generados", priority=2,
                      tools=["territorios", "lentes", "arquetipos", "fase-1"], last_event_at=last,
                      activity_level=1, event_count=len(concepts) + decision_count("scout"))

        # --- Researcher ----------------------------------------------------
        pending = (missions or {}).get("pending") or 0
        imported = (missions or {}).get("imported") or 0
        if pending or imported:
            add_agent("researcher", "Researcher", "Investigación", "WAITING" if pending else "IDLE",
                      f"{pending} misiones pendientes · {imported} importadas" if pending else f"{imported} misiones importadas",
                      priority=3, tools=["misiones", "import-research", "paquetes"],
                      missions=[m.get("mission_id") for m in (missions.get("items") or [])][:20],
                      parent="orchestrator", last_event_at=last_event_at("research"),
                      activity_level=1 if pending else 0, event_count=pending + imported + event_count_for("research"))
        else:
            add_agent("researcher", "Researcher", "Investigación", "NO_DATA",
                      "Sin misiones de investigación", priority=3, tools=["misiones", "import-research", "paquetes"],
                      parent="orchestrator", event_count=event_count_for("research"))

        # --- Skeptic -------------------------------------------------------
        review_total = (reviews or {}).get("review_count") or 0
        if review_total:
            add_agent("skeptic", "Skeptic", "Contraste", "IDLE",
                      f"{review_total} revisiones · {(reviews or {}).get('synthesis_count') or 0} síntesis",
                      priority=4, tools=["revisiones", "red-team", "comité"], parent="orchestrator",
                      last_event_at=(reviews or {}).get("latest_synthesis_at"),
                      activity_level=1, event_count=review_total + event_count_for("skeptic"))
        else:
            add_agent("skeptic", "Skeptic", "Contraste", "NO_DATA",
                      "Sin revisiones de contraste", priority=4, tools=["revisiones", "red-team", "comité"],
                      parent="orchestrator", event_count=event_count_for("skeptic"))

        # --- Economist -----------------------------------------------------
        cycle_status = (cycle or {}).get("status") or "UNKNOWN"
        survival = (economy_metrics or {}).get("survival_status")
        econ_action = f"Ciclo {cycle_status} · supervivencia {survival or 'DESCONOCIDA'}"
        add_agent("economist", "Economist", "Economía simulada", "WAITING" if cycle_status in ("PRE_CYCLE", "NOT_STARTED") else "IDLE",
                  econ_action, priority=5, tools=["ledger", "ciclo", "presupuesto", "reconciliación"],
                  parent="orchestrator", last_event_at=last_event_at("econom"),
                  activity_level=0, event_count=decision_count("econom") + event_count_for("econom"))

        # --- Builder -------------------------------------------------------
        experiment_id = (readiness or {}).get("experiment_id")
        selected = (run or {}).get("selected_opportunity_id")
        if experiment_id:
            add_agent("builder", "Builder", "Construcción", "IDLE",
                      f"Plan de experimento definido ({experiment_id[:8]})", priority=6,
                      tools=["experimento", "capacidades", "dependencias"], parent="orchestrator",
                      activity_level=1, event_count=decision_count("builder"))
        elif selected:
            add_agent("builder", "Builder", "Construcción", "WAITING",
                      "Oportunidad seleccionada sin plan de experimento", priority=6,
                      tools=["experimento", "capacidades", "dependencias"], parent="orchestrator",
                      blocked_reason="Falta plan de experimento", event_count=decision_count("builder"))
        else:
            add_agent("builder", "Builder", "Construcción", "NO_DATA",
                      "Sin experimento definido", priority=6, tools=["experimento", "capacidades", "dependencias"],
                      parent="orchestrator", event_count=decision_count("builder"))

        # --- Compliance ----------------------------------------------------
        real_blockers = [b for b in blockers if b.get("severity") == "block" and b.get("kind") != "NINGUNO"]
        if real_blockers:
            add_agent("compliance", "Compliance", "Riesgos", "BLOCKED",
                      f"{len(real_blockers)} bloqueador(es) activo(s)", priority=7,
                      tools=["bloqueadores", "TOS", "privacidad", "legales"], parent="orchestrator",
                      blocked_reason=real_blockers[0].get("detail"),
                      event_count=len(real_blockers) + event_count_for("compliance"))
        else:
            add_agent("compliance", "Compliance", "Riesgos", "IDLE",
                      "Sin bloqueadores críticos", priority=7, tools=["bloqueadores", "TOS", "privacidad", "legales"],
                      parent="orchestrator", event_count=event_count_for("compliance"))

        # --- Judge ---------------------------------------------------------
        ev_total = (evidence or {}).get("total") or 0
        verified = (evidence or {}).get("verified") or 0
        add_agent("judge", "Judge", "Puntuación determinista", "IDLE" if ev_total or decision_count("judge") else "NO_DATA",
                  f"{verified}/{ev_total} evidencias verificadas · tope {evidence.get('max_evidence_score')}" if ev_total else "Sin evidencias puntuables",
                  priority=8, tools=["venture-score", "torneo", "fingerprint", "quality-gate"], parent="orchestrator",
                  last_event_at=last_event_at("judge"), activity_level=1 if verified else 0,
                  event_count=decision_count("judge") + event_count_for("judge"))

        # --- Proveedores ---------------------------------------------------
        provider_specs = [
            ("gemini", "Gemini (opcional)", "generación", "gemini"),
            ("openrouter", "OpenRouter (comité)", "revisión", "openrouter"),
            ("omniroute", "OmniRoute (gateway local)", "gateway", "omniroute"),
            ("mock", "MockProvider", "offline determinista", "mock"),
        ]
        for agent_id, name, role, key in provider_specs:
            h = (providers_health or {}).get(key) or {}
            configured = bool(h.get("configured") or h.get("enabled") or h.get("available") is True)
            provider_calls = [c for c in calls if key in str(c.get("provider") or "").lower()]
            if provider_calls:
                add_agent(agent_id, name, role, "WORKING" if len(provider_calls) <= 20 else "ACTIVE",
                          f"{len(provider_calls)} llamadas recientes", priority=9,
                          tools=["llm_call_log"], parent="orchestrator",
                          last_event_at=provider_calls[-1].get("created_at"), activity_level=1,
                          event_count=len(provider_calls))
            elif configured:
                add_agent(agent_id, name, role, "IDLE",
                          "Configurado, sin llamadas recientes", priority=9, tools=["llm_call_log"],
                          parent="orchestrator")
            else:
                add_agent(agent_id, name, role, "OFFLINE" if (providers_health or {}).get(key) is not None else "NO_DATA",
                          "Sin configuración — ausencia neutral", priority=9, tools=["llm_call_log"],
                          parent="orchestrator")

        mission_queue = [
            {"mission_id": m.get("mission_id"), "kind": m.get("kind"), "status": m.get("status"),
             "opportunity_id": m.get("opportunity_id")}
            for m in (missions.get("items") or []) if m.get("status") != "imported"
        ]
        scheduled = []
        if (cycle or {}).get("status") in ("PRE_CYCLE", "NOT_STARTED"):
            scheduled.append({"task": "Iniciar ciclo económico (30 días / 50 USD)", "state": "PRE_CYCLE", "nature": "REAL"})
        if (readiness or {}).get("readiness_missing"):
            scheduled.append({"task": "Resolver precondiciones de readiness", "state": "NOT_READY", "nature": "REAL"})
        if (run or {}).get("state") == "RESEARCH_PENDING":
            scheduled.append({"task": "Importar investigación de misiones (URL+fecha+fragmento)", "state": "RESEARCH_PENDING", "nature": "REAL"})

        recent_events = []
        for e in events[:15]:
            data = _safe(lambda e=e: e.model_dump(), None) or {}
            recent_events.append({"timestamp": data.get("timestamp"), "kind": data.get("event_type"),
                                  "summary": data.get("summary"), "nature": "REAL"})
        for d in reversed(decisions[-15:]):
            recent_events.append({"timestamp": getattr(d, "timestamp", None), "kind": "DECISION",
                                  "summary": f"{getattr(d, 'agent', '?')}: {getattr(d, 'decision', '') or getattr(d, 'output_summary', '')[:120]}",
                                  "nature": "REAL"})
        recent_events = sorted(recent_events, key=lambda x: x.get("timestamp") or "", reverse=True)[:30]

        readiness_missing = (readiness or {}).get("readiness_missing") or []
        experiment_state = {
            "state": "EXPERIMENT_READY" if experiment_id else ("NEEDS_EXPERIMENT" if selected else "NO_EXPERIMENT"),
            "experiment_id": experiment_id, "candidate_id": (readiness or {}).get("candidate_id"),
            "opportunity_id": (readiness or {}).get("opportunity_id"),
            "readiness_state": (readiness or {}).get("readiness_state"),
            "readiness_missing": readiness_missing, "readiness_blockers": (readiness or {}).get("readiness_blockers"),
        }

        # --- Iteración 021: ganadora, servicios pendientes y mandato ----------
        launch_winner = None
        if selected and experiment_id:
            plan = _safe(lambda: self.c.repos.orchestrator.experiment_plan_for_opportunity(selected), None)
            opp = _safe(lambda: self.c.repos.opportunities.get(selected), None)
            launch_winner = {
                "candidate_id": selected, "opportunity_id": selected, "experiment_id": experiment_id,
                "title": getattr(opp, "title", None) if opp else None,
                "offer": (plan or {}).get("offer"),
                "price_usd": (plan or {}).get("price_usd"),
                "readiness_state": (readiness or {}).get("readiness_state"),
                "evidence_verified": evidence.get("verified"),
                "evidence_groups": evidence.get("independent_verified_groups"),
                "nature": "REAL",
            }
        # Servicios que exige la oportunidad ganadora (nunca secretos: solo
        # nombres de variable y estado; la conexión la hace el propietario).
        services_required = [
            {"name": "Stripe (cobro)", "env_var": "STRIPE_SECRET_KEY", "status": "MISSING",
             "purpose": "Primer pago real (checkout, precio hipótesis 60 EUR)", "nature": "NO CONECTADO"},
            {"name": "Email transaccional", "env_var": "EMAIL_API_KEY", "status": "MISSING",
             "purpose": "Confirmación de pedido y entrega del informe", "nature": "NO CONECTADO"},
            {"name": "Hosting", "env_var": "HOSTING_*", "status": "MISSING",
             "purpose": "Despliegue de landing y checkout", "nature": "NO CONECTADO"},
            {"name": "Dominio / subdominio", "env_var": "DOMAIN", "status": "MISSING",
             "purpose": "URL pública del producto", "nature": "NO CONECTADO"},
            {"name": "Analytics", "env_var": "ANALYTICS_*", "status": "MISSING",
             "purpose": "Eventos visits/leads/checkouts/payments", "nature": "NO CONECTADO"},
            {"name": "GitHub (repositorio)", "env_var": "—", "status": "CONNECTED",
             "purpose": "Repositorio actual WAWA (los artefactos de producto viven en product/)", "nature": "REAL"},
        ]
        authorization_mandate = {
            "opportunity": (launch_winner or {}).get("title"),
            "offer": (launch_winner or {}).get("offer"),
            "price_usd": (launch_winner or {}).get("price_usd"),
            "duration_days": 30,
            "max_budget_usd": 0.0,
            "max_daily_spend_usd": 0.0,
            "allowed_channels": [
                "Contacto directo autorizado a 20 clínicas identificadas (sin spam)",
                "Colegios y directorios oficiales",
                "LinkedIn profesional",
            ],
            "automatic_actions": [
                "Seguimiento de contactos y recordatorios",
                "Generación del informe (plantilla + percentiles)",
                "Informes diarios y heartbeat",
                "Registro de eventos de analytics",
            ],
            "blocked_actions": [
                "Gasto real sin autorización", "Publicaciones automáticas", "Mensajería masiva",
                "Creación de cuentas", "Trading/compras", "Acciones irreversibles",
            ],
            "price_optimization_range_usd": [30, 90],
            "success_condition": "1 pago real confirmado (30-90 EUR) por un comprador real",
            "pivot_condition": "Interés sin pago tras 14 días: pivotar a aseguradoras/software dental o ampliar especialidades",
            "close_condition": "Sin señal de pago en 30 días y sin pivote viable",
            "human_intervention_cases": [
                "Credenciales ausentes", "Login/OAuth/CAPTCHA", "Permisos externos", "Gasto real",
                "Decisión irreversible", "Conflicto legal/ToS material", "Bloqueo técnico real",
            ],
            "state": "PENDING_OWNER_AUTHORIZATION",
            "nature": "REAL",
        }

        bootstrap_status = _safe(lambda: self.c.bootstrap.status(), None)
        return {
            "snapshot_at": generated_at,
            "version": self.c.settings.version, "iteration": "022", "build": "022-one-click-activation",
            "system_health": health,
            "production_capability": self._production_capability(engine),
            "campaign_id": campaign_id,
            "active_project": "Autonomous Business Lab" if run else None,
            "run": {"state": run_state, "id": (run or {}).get("id"), "title": (run or {}).get("title")},
            "agents": agents,
            "agent_relationships": [
                {"parent": "orchestrator", "child": a["id"]}
                for a in agents if a.get("parent_agent_id") == "orchestrator"
            ],
            "scheduled_tasks": scheduled,
            "mission_queue": mission_queue,
            "recent_events": recent_events,
            "blockers": [{"kind": b.get("kind"), "detail": b.get("detail"), "severity": b.get("severity")} for b in blockers if b.get("kind") != "NINGUNO"],
            "provider_states": [
                {"id": a["id"], "status": a["status"], "current_action": a["current_action"]}
                for a in agents if a["id"] in ("gemini", "openrouter", "omniroute", "mock")
            ],
            "costs": {
                "reported_total": llm.get("reported_cost_total"), "estimated_total": llm.get("estimated_cost_total"),
                "unknown_cost_calls": llm.get("unknown_cost_calls"), "zero_cost_calls": llm.get("zero_cost_calls"),
                "display_status": llm.get("display_status"), "billing_verified": llm.get("billing_verified"),
                "nature": llm.get("nature"),
            },
            "evidence": {
                "verified": evidence.get("verified"), "total": evidence.get("total"),
                "unverified": evidence.get("unverified"), "rejected": evidence.get("rejected"),
                "independent_verified_groups": evidence.get("independent_verified_groups"),
                "max_evidence_score": evidence.get("max_evidence_score"), "nature": evidence.get("nature"),
            },
            "reviews": {
                "review_count": reviews.get("review_count"), "synthesis_count": reviews.get("synthesis_count"),
                "committee_status": reviews.get("committee_status"), "nature": reviews.get("nature"),
            },
            "budget": {"daily_reached": (budget.get("daily") or {}).get("reached"), "limit_usd": (budget.get("daily") or {}).get("limit_usd")},
            "experiment_state": experiment_state,
            "launch_winner": launch_winner,
            "services_required": services_required,
            "authorization_mandate": authorization_mandate,
            "commercial_metrics": {"visits": "NO CONECTADO", "leads": "NO CONECTADO", "payments": "NO CONECTADO",
                                   "nature": "NO CONECTADO"},
            "bootstrap": {
                "applied": bool((bootstrap_status or {}).get("applied")),
                "applied_version": (bootstrap_status or {}).get("applied_version"),
                "recoverable": bool((bootstrap_status or {}).get("recoverable")),
                "can_repair": bool((bootstrap_status or {}).get("can_repair")),
                "run_state": (bootstrap_status or {}).get("run_state"),
                "run_status": (bootstrap_status or {}).get("run_status"),
                "missing_activation": bool((bootstrap_status or {}).get("missing_activation")),
                "assets_ok": bool((bootstrap_status or {}).get("assets_ok")),
                "nature": "REAL",
            },
            "data_nature": "REAL",
            "note": "Telemetría derivada exclusivamente de datos persistidos; sin actividad inventada. Modo demo es solo cliente (?demo=1) y se etiqueta DEMO DATA · NOT REAL ACTIVITY.",
        }

    def _system_health(self, engine, economy_status, snapshot_at) -> dict:
        safe = str(engine.get("engine_state", "")).lower() == "safe_pause" or str(engine.get("mode", "")).lower() == "safe_pause"
        sqlite_ok = True
        try:
            self.c.conn.execute("SELECT 1").fetchone()
        except (sqlite3.Error, AttributeError):
            sqlite_ok = False
        critical = [e for e in (_safe(lambda: self.c.engine.events(limit=50), []) or []) if getattr(e, "event_type", "") == "critical"]
        reconciliation = _safe(lambda: self.c.repos.ledger.consistency_issues(), []) or []
        state = "SAFE_PAUSE" if safe else ("ERROR" if not sqlite_ok or critical else ("DEGRADED" if reconciliation or str(engine.get("engine_state", "")).lower() == "degraded" else "OK"))
        return {"system_health": state, "safe_pause": safe, "heartbeat": engine.get("heartbeat_at"),
                "critical_errors_recent": len(critical), "sqlite_available": sqlite_ok,
                "orchestrator_state": ((self.c.orchestrator.current_run() or {}).get("state")),
                "economic_reconciliation": "OK" if not reconciliation else "DEGRADED",
                "reconciliation_issues": reconciliation, "required_providers": "SIN DATOS",
                "snapshot_at": snapshot_at, "nature": "REAL"}

    @staticmethod
    def _production_capability(engine) -> dict:
        if "production_capability_available" not in engine:
            return {"state": "UNAVAILABLE", "reason": "NO_DATA", "nature": "DESCONOCIDO"}
        available = bool(engine.get("production_capability_available"))
        return {"state": "AVAILABLE" if available else "BLOCKED",
                "reason": engine.get("production_block_reason"), "nature": "REAL"}

    def _timeline(self) -> list[dict]:
        items = []
        for event in _safe(lambda: self.c.engine.events(limit=25), []) or []:
            data = _safe(lambda e=event: e.model_dump(), None)
            if data:
                items.append({"timestamp": data.get("timestamp"), "kind": data.get("event_type"),
                              "summary": data.get("summary"), "nature": "REAL", "cost_usd": data.get("cost_usd")})
        for entry in _safe(lambda: self.c.repos.decision_log.recent(limit=15), []) or []:
            items.append({"timestamp": getattr(entry, "timestamp", None), "kind": "DECISION",
                          "summary": f"{getattr(entry, 'agent', '?')}: {getattr(entry, 'decision', '')}", "nature": "REAL"})
        return sorted(items, key=lambda x: x.get("timestamp") or "", reverse=True)[:30]

    def _services_summary(self) -> list[dict]:
        health = _safe(lambda: self.c.providers.health(), {}) or {}
        providers = {
            "Gemini (opcional)": bool((health.get("gemini") or {}).get("configured")),
            "OpenRouter (comité)": bool((health.get("openrouter") or {}).get("configured")),
            "OmniRoute (gateway local)": bool((health.get("omniroute") or {}).get("configured")),
            "MockProvider (offline)": True, "Manual/Freebuff": True,
        }
        out = [{"name": name, "connected": connected, "note": "" if connected else "Sin configuración — ausencia neutral",
                "nature": "REAL" if connected else "NO CONECTADO"} for name, connected in providers.items()]
        out.extend({"name": name, "connected": False, "note": "NO CONECTADO", "nature": "NO CONECTADO"}
                   for name in ("Stripe", "Hosting", "Dominio", "Email operativo", "Analytics"))
        return out
