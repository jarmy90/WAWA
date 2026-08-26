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
            "iteration": "019",
            "build": "019-command-center-contract",
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
