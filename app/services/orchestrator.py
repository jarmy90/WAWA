"""Orquestador único end-to-end (iteración 010).

Coordina servicios EXISTENTES (nunca duplica ni crea microservicios):
- CampaignService / DiscoveryService (campaña + conceptos + misiones)
- PipelineService (evaluación y reevaluación)
- ReviewService (comité + decisión autónoma)
- CycleEvaluator (PRE_CYCLE → ciclo)

El avance es por PASOS deterministas y resumibles: cada fase se ejecuta una
sola vez y se registra en ``orchestrator_transitions`` (append-only). El
orquestador se detiene HONESTAMENTE en ``RESEARCH_PENDING`` cuando necesita
investigación externa real (este entorno no puede hacer investigación web
automática; el botón "COPIAR MISIÓN PARA FREEBUFF" cubre esa fase).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.orchestrator import (
    FIRST_REAL_CAMPAIGN_CONFIG,
    ORCHESTRATOR_STATES,
    RESEARCH_MISSION_KINDS,
    RESEARCH_PHASE1_KINDS,
    ExperimentPlan,
    new_id,
)
from app.repositories import Repos
from app.repositories.orchestrator import OrchestratorRepository


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CampaignOrchestrator:
    def __init__(self, settings: Settings, repos: Repos, orchestrator_repo: OrchestratorRepository,
                 discovery, pipeline, reviews, opportunities) -> None:
        self.settings = settings
        self.repos = repos
        self.orr = orchestrator_repo
        self.discovery = discovery
        self.pipeline = pipeline
        self.reviews = reviews
        self.opportunities = opportunities

    # ------------------------------------------------------------------ runs
    def current_run(self) -> dict | None:
        runs = self.orr.list_runs(status="active")
        return runs[0] if runs else None

    def create_real_campaign(self) -> dict:
        """INICIAR CAMPAÑA REAL: crea la ejecución + campaña de descubrimiento
        con la configuración de la primera campaña real (diversa, sin ventaja
        de sector). Idempotente: si ya existe una ejecución activa, la devuelve."""
        existing = self.current_run()
        if existing:
            return self.detail(existing["id"])

        config = dict(FIRST_REAL_CAMPAIGN_CONFIG)
        run_id = new_id()
        run = self.orr.create_run(run_id=run_id, title=config["title"], config=config)

        discovery_campaign = self.discovery.create_campaign(
            {
                "title": config["title"],
                "territory_keys": [],  # todos los territorios (diversidad)
                "lens_keys": [],
                "archetype_keys": [],
                "phase1_target": config["phase1_target"],
                "shortlist_target": config["research_candidates"],  # 6 para investigación
                "finalists_target": config["finalists_target"],
            }
        )
        self.orr.update_run(run_id, discovery_campaign_id=discovery_campaign["id"])
        self.orr.add_transition(
            run_id=run_id, from_state="CAMPAIGN_CREATED", to_state="CAMPAIGN_CREATED",
            actor="owner", reason="Inicio deliberado de la PRIMERA CAMPAÑA REAL 001 (real_market_discovery).",
            inputs={"config": config}, synthetic=False, cost_usd=0.0, cost_source="LOCAL_ESTIMATE",
            next_action="Ejecutar fases de descubrimiento (offline, sin gasto).",
        )
        return self.detail(run_id)

    # ------------------------------------------------------------------ advance
    def advance(self, run_id: str, *, max_steps: int = 40) -> dict:
        """Continúa hasta el siguiente punto que exija datos externos o una
        intervención legítima. Idempotente y resumible (no repite fases)."""
        run = self._get(run_id)
        if run["status"] != "active":
            raise ConflictError(f"La ejecución no está activa (estado: {run['status']}).")

        steps = 0
        while steps < max_steps:
            state = run["state"]
            nxt = self._next_step(run, state)
            if nxt is None:  # punto de parada honesto (owner action o fin)
                break
            transition = self._execute_step(run, nxt)
            run = self.orr.get_run(run_id)  # type: ignore[assignment]
            steps += 1
            if transition.get("owner_action_required"):
                break
        return self.detail(run_id)

    def _next_step(self, run: dict, state: str) -> dict | None:
        """Decide el siguiente paso (o None si hay que parar). Determinista."""
        dcid = run.get("discovery_campaign_id")
        cfg = run.get("config") or {}
        if state == "CAMPAIGN_CREATED":
            return {"to": "DISCOVERING", "op": "phase1"}
        if state == "DISCOVERING":
            return {"to": "DEDUPLICATING", "op": "dedup"}
        if state == "DEDUPLICATING":
            return {"to": "FILTERING_COMMODITIES", "op": "commodity_filter"}
        if state == "FILTERING_COMMODITIES":
            return {"to": "RECOMBINING", "op": "recombine"}
        if state == "RECOMBINING":
            return {"to": "STRUCTURAL_ANALYSIS", "op": "structural"}
        if state == "STRUCTURAL_ANALYSIS":
            return {"to": "SHORTLISTING", "op": "shortlist"}
        if state == "SHORTLISTING":
            return {"to": "TOURNAMENT", "op": "tournament"}
        if state == "TOURNAMENT":
            return {"to": "RESEARCH_PLANNED", "op": "promote_and_plan_research"}
        if state == "RESEARCH_PLANNED":
            return {
                "to": "RESEARCH_PENDING",
                "op": "stop_for_research",
                "owner_action_required": True,
                "reason": "Investigación externa REAL necesaria (no hay investigación web automática en este entorno).",
                "next_action": "COPIAR MISIÓN PARA FREEBUFF y pegar la respuesta en el panel.",
            }
        if state in ("RESEARCH_PENDING", "RESEARCH_IMPORTED"):
            return {"to": "REEVALUATING", "op": "reevaluate"} if state == "RESEARCH_IMPORTED" else None
        if state == "REEVALUATING":
            return {"to": "CANDIDATES_READY", "op": "finalize_candidates"}
        if state == "CANDIDATES_READY":
            return {"to": "FINALISTS_READY", "op": "promote_finalists"}
        if state == "FINALISTS_READY":
            return {"to": "COMMITTEE_READY", "op": "queue_committee"}
        if state == "COMMITTEE_READY":
            return {"to": "COMMITTEE_PENDING", "op": "wait_committee", "owner_action_required": True,
                    "reason": "Esperando revisiones del comité (48 h opcionales; ausencia neutral).",
                    "next_action": "Pegar respuestas GPT/Grok/Gemini o usar la revisión automática (opcional)."}
        if state == "COMMITTEE_COMPLETED":
            return {"to": "DECIDING", "op": "decide"}
        if state == "DECIDING":
            decision = (run.get("config") or {}).get("last_decision")
            if decision in ("SMALL_EXPERIMENT", "PRIORITY_EXPERIMENT"):
                return {"to": "EXPERIMENT_READY", "op": "create_experiment_plan"}
            return {"to": "EXPERIMENT_BLOCKED", "op": "block_experiment"}
        if state == "EXPERIMENT_READY":
            return {"to": "PRE_CYCLE", "op": "pre_cycle"}
        if state == "PRE_CYCLE":
            return {"to": "READY_TO_START_CYCLE", "op": "ready_to_start_cycle", "owner_action_required": True,
                    "reason": "Ciclo preparado. El reloj NO arranca solo: el propietario debe ejecutar POST /api/economy/cycle/start.",
                    "next_action": "Iniciar el ciclo (activación deliberada)."}
        if state == "READY_TO_START_CYCLE":
            return {"to": "COMPLETED", "op": "complete_campaign"}
        return None

    def _execute_step(self, run: dict, step: dict) -> dict:
        op = step["op"]
        run_id = run["id"]
        dcid = run.get("discovery_campaign_id")
        to = step["to"]
        try:
            if op == "phase1":
                detail = self.discovery.run_phase1(dcid)
                considered = len(detail.get("concepts") or [])
                return self._transition(run_id, to, f"Fase 1: exploración amplia ({considered} conceptos).",
                                        concepts_considered=considered, synthetic=False,
                                        next_action="Filtro de comoditización.")
            if op == "dedup":
                detail = self.discovery.campaign_detail(dcid)
                concepts = detail.get("concepts") or []
                return self._transition(run_id, to, f"Deduplicación por fingerprint: {len(concepts)} conceptos únicos.",
                                        concepts_considered=len(concepts), synthetic=False,
                                        next_action="Filtro IA/commodity.")
            if op == "commodity_filter":
                detail = self.discovery.run_commodity_filter(dcid)
                concepts = detail.get("concepts") or []
                blocked = sum(1 for c in concepts if c.get("status") in ("COMMODITY_BLOCKED", "RECOMBINATION_INCOHERENT"))
                return self._transition(run_id, to, f"Filtro de comoditización: {blocked} bloqueados.",
                                        concepts_considered=len(concepts), concepts_rejected=blocked, synthetic=False,
                                        next_action="Recombinación.")
            if op == "recombine":
                try:
                    detail = self.discovery.run_recombine(dcid)
                    created = sum(1 for c in detail.get("concepts") or [] if c.get("source") == "recombined")
                    return self._transition(run_id, to, f"Recombinación: {created} conceptos recombinados.",
                                            concepts_considered=len(detail.get("concepts") or []), synthetic=False,
                                            next_action="Análisis estructural.")
                except ValidationError as exc:
                    return self._transition(run_id, to, f"Recombinación omitida: {exc.message}",
                                            synthetic=False, next_action="Análisis estructural.")
            if op == "structural":
                detail = self.discovery.evaluate_structural(dcid)
                concepts = detail.get("concepts") or []
                return self._transition(run_id, to, "Análisis estructural: Venture Quality Score determinista.",
                                        concepts_considered=len(concepts), synthetic=False,
                                        next_action="Shortlist diversa.")
            if op == "shortlist":
                detail = self.discovery.run_shortlist(dcid)
                candidates = sum(1 for c in detail.get("concepts") or [] if c.get("status") == "RESEARCH_CANDIDATE")
                reform = sum(1 for c in detail.get("concepts") or [] if c.get("status") == "NEEDS_REFORMULATION")
                return self._transition(
                    run_id, to,
                    f"Shortlist: {candidates} candidatas concretas; {reform} necesitan reformulación.",
                    concepts_considered=len(detail.get("concepts") or []), synthetic=False,
                    next_action="Torneo por pares.")
            if op == "tournament":
                detail = self.discovery.run_tournament(dcid)
                finalists = sum(1 for c in detail.get("concepts") or [] if c.get("status") == "FINALIST")
                return self._transition(run_id, to, f"Torneo por pares: {finalists} finalistas (0 es válido).",
                                        concepts_considered=len(detail.get("concepts") or []), synthetic=False,
                                        next_action="Preparar investigación de candidatas.")
            if op == "promote_and_plan_research":
                return self._promote_and_plan_research(run)
            if op == "stop_for_research":
                return self._transition(run_id, to, step["reason"],
                                        owner_action_required=True, next_action=step["next_action"], synthetic=False)
            if op == "reevaluate":
                return self._reevaluate(run)
            if op == "finalize_candidates":
                return self._finalize_candidates(run)
            if op == "promote_finalists":
                return self._promote_finalists(run)
            if op == "queue_committee":
                return self._queue_committee(run)
            if op == "wait_committee":
                return self._transition(run_id, to, step["reason"], owner_action_required=True,
                                        next_action=step["next_action"], synthetic=False)
            if op == "decide":
                return self._decide(run)
            if op == "create_experiment_plan":
                return self._create_experiment_plan(run)
            if op == "block_experiment":
                return self._transition(run_id, to, "La decisión no autoriza experimento (REJECT/MORE_RESEARCH).",
                                        synthetic=False, next_action="Más investigación o nueva campaña.")
            if op == "pre_cycle":
                return self._transition(run_id, to, "Plan de experimento listo: estado PRE_CYCLE (el reloj NO arranca solo).",
                                        synthetic=False, next_action="Revisar precondiciones del ciclo.")
            if op == "ready_to_start_cycle":
                return self._transition(run_id, to, step["reason"], owner_action_required=True,
                                        next_action=step["next_action"], synthetic=False)
            if op == "complete_campaign":
                self.orr.update_run(run_id, status="completed")
                return self._transition(run_id, to, "Campaña completada (estado final).", synthetic=False)
            raise ValidationError(f"Operación desconocida: {op}")
        except Exception as exc:  # noqa: BLE001 — el orquestador registra y falla con control
            return self._transition(run_id, "FAILED", f"Fallo en {op}: {exc}", errors=[str(exc)],
                                    owner_action_required=True, next_action="Revisar el error y reintentar (advance).",
                                    synthetic=False)

    # ------------------------------------------------------------- discovery → research
    def _promote_and_plan_research(self, run: dict) -> dict:
        run_id = run["id"]
        dcid = run.get("discovery_campaign_id")
        detail = self.discovery.campaign_detail(dcid)
        cfg = run.get("config") or {}
        # Iteración 013: SOLO candidatas concretas (RESEARCH_CANDIDATE/FINALIST).
        # Las NEEDS_REFORMULATION / RECOMBINATION_INCOHERENT nunca se investigan.
        candidates = [
            c for c in (detail.get("concepts") or [])
            if c.get("status") in ("RESEARCH_CANDIDATE", "FINALIST", "SHORTLISTED_WITH_EVIDENCE")
        ][: int(cfg.get("research_candidates", 6))]

        # Invalida misiones previas no superseded (nunca se borran).
        for mission in self.repos.discovery.missions_by_campaign(dcid):
            self.repos.discovery.update_mission_status(
                mission["mission_id"], "SUPERSEDED_BY_SEMANTIC_QUALITY_GATE"
            )

        promoted: list[str] = []
        missions: list[dict] = []
        for concept in candidates:
            opp = self.discovery.promote(concept["id"])
            promoted.append(opp.id)
            # Iteración 013: misiones PROGRESIVAS — solo Fase 1 (6 de descarte).
            for kind in RESEARCH_PHASE1_KINDS:
                mission = self.discovery.create_mission(kind=kind, campaign_id=dcid, concept_id=concept["id"])
                missions.append({"mission_id": mission.mission_id, "kind": kind, "concept_id": concept["id"], "opportunity_id": opp.id})
        self.orr.update_run(run_id, selected_opportunity_id=promoted[0] if promoted else None)
        outputs = {"promoted": promoted, "missions": missions}
        return self._transition(
            run_id, "RESEARCH_PLANNED",
            f"{len(promoted)} candidatas concretas promovidas; {len(missions)} misiones de Fase 1 creadas (6 por candidata, progresivas).",
            inputs={"config": cfg}, outputs=outputs, concepts_considered=len(candidates), synthetic=False,
            next_action="COPIAR MISIÓN PARA FREEBUFF (investigación externa real).",
        )

    def import_research(self, run_id: str, payloads: list[dict]) -> dict:
        """Importa resultados de misiones (respuestas Freebuff/modelos) y
        reanuda la campaña. La investigación solo aporta EVIDENCIAS cuando
        incluye fuentes verificables (URL + fecha + fragmento)."""
        from app.models.discovery import MissionIn

        run = self._get(run_id)
        if run["state"] not in ("RESEARCH_PENDING", "RESEARCH_PLANNED", "RESEARCH_IMPORTED"):
            raise ConflictError(f"La ejecución está en {run['state']}; no acepta investigación ahora.")
        imported = 0
        errors: list[str] = []
        for payload in payloads:
            mission_id = payload.get("mission_id")
            if not mission_id:
                errors.append("payload sin mission_id")
                continue
            try:
                cleaned = {
                    "mission_id": str(mission_id),
                    "evidences": payload.get("evidences") or [],
                    "competitors": payload.get("competitors") or [],
                    "buyer_confirmed": payload.get("buyer_confirmed"),
                    "notes": str(payload.get("notes") or "")[:5_000] or None,
                }
                mission_in = MissionIn(**cleaned)
                result = self.discovery.import_mission_result(mission_id, mission_in)
                opp_id = result.get("opportunity_id") or payload.get("opportunity_id")
                if opp_id:
                    self.discovery.attach_mission_evidence(opp_id, mission_id)
                imported += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{mission_id}: {exc}")
        if imported == 0 and errors:
            raise ValidationError("Ninguna misión se importó: " + "; ".join(errors[:3]))
        self.orr.update_run(run_id, state="RESEARCH_IMPORTED")
        return self._transition(
            run_id, "RESEARCH_IMPORTED", f"{imported} resultado(s) de misión importados ({len(errors)} errores).",
            outputs={"imported": imported, "errors": errors}, synthetic=False,
            next_action="Reevaluación automática (sin pulsar nada).",
        )

    def _reevaluate(self, run: dict) -> dict:
        run_id = run["id"]
        opp_ids = self._promoted_opportunities(run)
        results = []
        for opp_id in opp_ids:
            try:
                res = self.pipeline.evaluate(opp_id)
                results.append({"opportunity_id": opp_id, "status": "ok"})
            except Exception as exc:  # noqa: BLE001
                results.append({"opportunity_id": opp_id, "status": "error", "detail": str(exc)})
        return self._transition(run_id, "REEVALUATING", f"Reevaluación automática de {len(results)} candidatas.",
                                outputs={"results": results}, synthetic=False,
                                next_action="Selección de candidatas.")

    def _finalize_candidates(self, run: dict) -> dict:
        run_id = run["id"]
        opp_ids = self._promoted_opportunities(run)
        rows = []
        for opp_id in opp_ids:
            ev = self.repos.evaluations.get(opp_id)
            rows.append({"opportunity_id": opp_id, "final_score": ev.final_score if ev else None,
                         "decision": ev.decision.value if ev else None})
        return self._transition(run_id, "CANDIDATES_READY", f"{len(rows)} candidatas reevaluadas.",
                                outputs={"candidates": rows}, synthetic=False,
                                next_action="Promover finalistas que cumplan umbrales.")

    def _promote_finalists(self, run: dict) -> dict:
        run_id = run["id"]
        cfg = run.get("config") or {}
        threshold = self.settings.review_min_internal_score
        opp_ids = self._promoted_opportunities(run)
        finalists = []
        for opp_id in opp_ids:
            ev = self.repos.evaluations.get(opp_id)
            if ev is None:
                continue
            if ev.final_score >= threshold and int(ev.independent_evidence_count or 0) >= self.settings.review_min_evidence_groups:
                finalists.append({"opportunity_id": opp_id, "final_score": ev.final_score,
                                  "evidence_groups": ev.independent_evidence_count})
        finalists = finalists[: int(cfg.get("finalists_target", 3))]
        # Sin finalistas no se fuerza nada: la campaña conserva los aprendizajes.
        if not finalists:
            return self._transition(run_id, "FINALISTS_READY",
                                    "0 finalistas: ninguna candidata alcanza el umbral interno. Se conservan aprendizajes (no se fuerza).",
                                    concepts_rejected=len(opp_ids), synthetic=False,
                                    next_action="Nueva campaña con territorios/lentes distintos (o más investigación).")
        return self._transition(run_id, "FINALISTS_READY", f"{len(finalists)} finalista(s) promovida(s).",
                                outputs={"finalists": finalists}, synthetic=False,
                                next_action="Entrada automática al comité.")

    def _queue_committee(self, run: dict) -> dict:
        run_id = run["id"]
        queued = 0
        notes = []
        for row in self._finalists(run):
            try:
                self.reviews.queue_opportunity(row["opportunity_id"], quiet=False)
                queued += 1
            except ValidationError as exc:
                notes.append(f"{row['opportunity_id']}: {exc.message}")
        return self._transition(run_id, "COMMITTEE_READY", f"{queued} finalista(s) en el comité.",
                                outputs={"queued": queued, "skipped": notes}, synthetic=False,
                                next_action="Esperar revisiones (48 h opcionales) o decidir con ausencia neutral.")

    def _decide(self, run: dict) -> dict:
        run_id = run["id"]
        decision = None
        for row in self._finalists(run):
            try:
                res = self.reviews.committee_decision(row["opportunity_id"])
                decision = res["decision"]
            except Exception as exc:  # noqa: BLE001
                decision = decision or "FAILED"
                self.orr.add_transition(run_id=run_id, from_state="DECIDING", to_state="DECIDING",
                                        reason=f"decisión no disponible: {exc}")
        return self._transition(run_id, "DECIDING", f"Decisión autónoma: {decision or 'sin finalistas'}.",
                                outputs={"decision": decision}, synthetic=False,
                                next_action="Plan de experimento o bloqueo.")

    def _create_experiment_plan(self, run: dict) -> dict:
        run_id = run["id"]
        row = self._finalists(run)
        if not row:
            raise ValidationError("No hay finalista para crear el plan de experimento.")
        opp_id = row[0]["opportunity_id"]
        opp = self.repos.opportunities.get(opp_id)
        ev = self.repos.evaluations.get(opp_id)
        est = (ev.estimates if ev else None)
        price = (est.price_low_usd if est else None)
        cfg = run.get("config") or {}
        plan = ExperimentPlan(
            run_id=run_id,
            opportunity_id=opp_id,
            decision=(cfg.get("last_decision") or "SMALL_EXPERIMENT"),
            offer=opp.proposed_solution if opp else None,
            buyer=opp.target_customer if opp else None,
            problem=opp.problem if opp else None,
            price_usd=float(price) if price else None,
            max_cost_usd=float(cfg.get("experiment_budget_usd", 10.0)),
            duration_days=int(cfg.get("build_days_max", 5)),
            success_metric="primer pago real confirmado",
            success_threshold="1 pago confirmado por un comprador real",
            kill_condition="sin señal de pago tras el periodo del experimento",
            product_death_condition="el experimento no produce señal de pago y no hay pivote viable",
            acquisition_method="sin spam; captación manual autorizada por canal",
            payment_readiness="pendiente: requiere método de cobro real autorizado",
            missing_capabilities=["metodo_pago_real_autorizado", "canal_de_cobro"],
            blockers=[],
        )
        saved = self.orr.create_experiment_plan(plan)
        return self._transition(run_id, "EXPERIMENT_READY", f"Plan de experimento creado para {opp_id}.",
                                outputs={"experiment_plan": saved}, synthetic=False,
                                next_action="Revisar precondiciones del ciclo (PRE_CYCLE).")

    # ------------------------------------------------------------------ actions
    def pause(self, run_id: str) -> dict:
        run = self._get(run_id)
        self.orr.update_run(run_id, status="paused")
        # La pausa NO cambia la fase: conserva el estado para reanudar sin repetir.
        self._transition(run_id, run["state"], "Ejecución pausada por el propietario (fase conservada).",
                         actor="owner", synthetic=False)
        return self.detail(run_id)

    def resume(self, run_id: str) -> dict:
        run = self._get(run_id)
        if run["status"] != "paused":
            raise ConflictError("La ejecución no está pausada.")
        self.orr.update_run(run_id, status="active")
        self._transition(run_id, run["state"], "Ejecución reanudada.", actor="owner", synthetic=False)
        return self.advance(run_id)

    def cancel(self, run_id: str) -> dict:
        run = self._get(run_id)
        self.orr.update_run(run_id, status="cancelled")
        self._transition(run_id, "COMPLETED", "Campaña cancelada por el propietario (se conservan aprendizajes).",
                         actor="owner", synthetic=False, next_action="Nueva campaña.")
        return self.detail(run_id)

    # ------------------------------------------------------------------ helpers
    def _get(self, run_id: str) -> dict:
        run = self.orr.get_run(run_id)
        if run is None:
            raise NotFoundError("Ejecución del orquestador no encontrada.")
        return run

    def _promoted_opportunities(self, run: dict) -> list[str]:
        rows = self.orr.transitions_for(run["id"])
        for t in rows:
            if t.get("to_state") == "RESEARCH_PLANNED":
                out = t.get("outputs") or {}
                return list(out.get("promoted") or [])
        return []

    def _finalists(self, run: dict) -> list[dict]:
        rows = self.orr.transitions_for(run["id"])
        for t in rows:
            if t.get("to_state") == "FINALISTS_READY":
                out = t.get("outputs") or {}
                return list(out.get("finalists") or [])
        return []

    def current_experiment_plan(self, run_id: str) -> dict | None:
        return self.orr.experiment_plan_for_run(run_id)

    def _transition(self, run_id: str, to_state: str, reason: str, *, actor: str = "system",
                    inputs: dict | None = None, outputs: dict | None = None, concepts_considered: int = 0,
                    concepts_rejected: int = 0, owner_action_required: bool = False, synthetic: bool = True,
                    next_action: str | None = None, errors: list[str] | None = None) -> dict:
        if to_state not in ORCHESTRATOR_STATES:
            raise ValidationError(f"Estado de orquestador inválido: {to_state}")
        run = self.orr.get_run(run_id)
        if run is None:
            raise NotFoundError("Ejecución no encontrada.")
        from_state = run["state"]
        self.orr.add_transition(
            run_id=run_id, from_state=from_state, to_state=to_state, actor=actor, reason=reason,
            inputs=inputs, outputs=outputs, concepts_considered=concepts_considered,
            concepts_rejected=concepts_rejected, owner_action_required=owner_action_required,
            synthetic=synthetic, next_action=next_action, errors=errors,
            cost_usd=0.0, cost_source="LOCAL_ESTIMATE",
        )
        self.orr.update_run(run_id, state=to_state)
        return self.orr.last_transition(run_id)

    def detail(self, run_id: str) -> dict:
        run = self._get(run_id)
        transitions = self.orr.transitions_for(run_id)
        discovery = None
        if run.get("discovery_campaign_id"):
            try:
                discovery = self.discovery.campaign_detail(run["discovery_campaign_id"])
            except NotFoundError:
                discovery = None
        experiment = self.orr.experiment_plan_for_run(run_id)
        finalists = self._finalists(run)
        committee = []
        for row in finalists:
            opp = self.repos.opportunities.get(row["opportunity_id"])
            reviews = self.repos.reviews.reviews_for(row["opportunity_id"])
            synthesis = self.repos.reviews.get_synthesis(row["opportunity_id"])
            committee.append({"opportunity_id": row["opportunity_id"],
                              "title": opp.title if opp else "—",
                              "final_score": row.get("final_score"),
                              "reviews_count": len(reviews),
                              "synthesis": synthesis})
        return {
            "run": run,
            "transitions": transitions,
            "discovery": discovery,
            "experiment_plan": experiment,
            "committee": committee,
            "research_pending": run["state"] == "RESEARCH_PENDING",
            "owner_action_required": bool(transitions and transitions[0].get("owner_action_required")),
            "next_action": (transitions[0].get("next_action") if transitions else None),
        }
