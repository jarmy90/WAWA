"""Rutas de la API local."""
from __future__ import annotations

import json
import threading
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import ValidationError
from app.core.security import validate_extension, validate_payload_size, validate_uuid
from app.models.campaign import CampaignCreate, ReasoningIn, SessionOutputIn, SessionPrepareIn, StageChangeIn
from app.models.discovery import CampaignCreate as DiscoveryCampaignCreate, MissionIn
from app.models import arena as models_arena
from app.models.enums import Decision, OpportunityStatus, OperatingMode
from app.models.external_review import (
    CombinedReviewImportIn,
    QueueOpportunityIn,
    ReviewImportIn,
)
from app.models.ledger import ExpenseRequestIn, IncomeIn, ReverseIn, SimulationStartIn
from app.models.opportunity import OpportunityCreate, ProblemSeed
from app.services.import_export import ResearchPackageIn
from app.workflows.demo import DemoSeeder

router = APIRouter(prefix="/api")


def get_container(request: Request):
    return request.app.state.container


def valid_id(opportunity_id: str) -> str:
    return validate_uuid(opportunity_id)


def valid_entry_id(entry_id: str) -> str:
    """Valida un id de asiento del ledger (32 hex).

    FastAPI resuelve el parámetro de una dependencia por nombre: debe coincidir
    con el parámetro de la ruta (entry_id), igual que `valid_id` para
    `opportunity_id`."""
    return validate_uuid(entry_id, field="entry_id")


def valid_campaign_id(campaign_id: str) -> str:
    return validate_uuid(campaign_id, field="campaign_id")


def valid_run_id(run_id: str) -> str:
    return validate_uuid(run_id, field="run_id")


def valid_concept_id(concept_id: str) -> str:
    return validate_uuid(concept_id, field="concept_id")


def valid_mission_id(mission_id: str) -> str:
    return validate_uuid(mission_id, field="mission_id")


def valid_review_id(review_id: str) -> str:
    return validate_uuid(review_id, field="review_id")


class MissionCreateIn(BaseModel):
    """Crea una misión de investigación Freebuff-first."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1, max_length=30)
    campaign_id: str | None = Field(default=None, max_length=64)
    concept_id: str | None = Field(default=None, max_length=64)


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Decision
    note: str | None = Field(default=None, max_length=2_000)


class ModeIn(BaseModel):
    """Cambio de modo de operación (activación deliberada y auditable)."""

    model_config = ConfigDict(extra="forbid")

    mode: OperatingMode
    reason: str | None = Field(default=None, max_length=2_000)
    activation_key: str | None = Field(default=None, max_length=500)
    actor: str = Field(default="human", max_length=100)


# ---------------------------------------------------------------------------
# Salud y configuración
# ---------------------------------------------------------------------------
@router.get("/health")
def health(request: Request) -> dict:
    container = get_container(request)
    return {
        "status": "ok",
        "app_name": container.settings.app_name,
        "version": container.settings.version,
        "providers": container.providers.health(),
        "budget": container.budget.status(),
        "engine": container.engine.status(),
        "db_initialized": True,
    }


@router.get("/config")
def config(request: Request) -> dict:
    container = get_container(request)
    return {
        "scoring_weights": container.settings.scoring_weights(),
        "decision_bands": container.settings.decision_bands(),
        "llm_provider": container.settings.llm_provider,
        "free_mode": container.settings.free_mode,
        "simulation_mode": container.settings.simulation_mode,
        "max_upload_bytes": container.settings.max_upload_bytes,
    }


@router.get("/budget")
def budget(request: Request) -> dict:
    return get_container(request).budget.status()


@router.get("/command-center")
def command_center(request: Request) -> dict:
    """Centro de mando (iteración 018): snapshot agregado con datos REALES del
    sistema. Cada bloque indica su naturaleza (REAL / SIMULADO / HIPÓTESIS /
    MODELO / DESCONOCIDO / NO CONECTADO). Nunca inventa cifras."""
    container = get_container(request)
    return container.command_center.snapshot()


@router.get("/agent-telemetry")
def agent_telemetry(request: Request) -> dict:
    """Telemetría de agentes (iteración 020): estados derivados SOLO de datos
    persistidos (run, misiones, evidencias, comité, costes LLM, proveedores,
    decisiones y eventos). Nunca inventa actividad: sin datos el estado es
    NO_DATA/IDLE, no ACTIVE. Modo demo (?demo=1) es exclusivamente cliente."""
    container = get_container(request)
    return container.command_center.agent_telemetry()


# ---------------------------------------------------------------------------
# Motor de operación
# ---------------------------------------------------------------------------
@router.get("/engine/status")
def engine_status(request: Request) -> dict:
    return get_container(request).engine.status()


@router.post("/engine/mode")
def engine_set_mode(request: Request, payload: ModeIn) -> dict:
    container = get_container(request)
    snapshot = container.engine.set_mode(
        payload.mode,
        reason=payload.reason,
        actor=payload.actor,
        activation_key=payload.activation_key,
    )
    return {"status": container.engine.status(), "transition_logged": True, "mode": snapshot.mode.value}


@router.post("/engine/heartbeat")
def engine_heartbeat(request: Request, task: str | None = None, last_result: str | None = None, next_action: str | None = None) -> dict:
    container = get_container(request)
    container.engine.heartbeat(task=task, last_result=last_result, next_action=next_action)
    return container.engine.status()


@router.get("/engine/events")
def engine_events(request: Request, limit: int = Query(default=20, ge=1, le=100)) -> dict:
    container = get_container(request)
    return {"items": [e.model_dump() for e in container.engine.events(limit)], "count": container.repos.engine.event_count()}


@router.get("/engine/transitions")
def engine_transitions(request: Request, limit: int = Query(default=20, ge=1, le=100)) -> dict:
    container = get_container(request)
    return {"items": [t.model_dump() for t in container.engine.transitions(limit)]}


# ---------------------------------------------------------------------------
# Orquestador end-to-end (iteración 010)
# ---------------------------------------------------------------------------
@router.post("/orchestrator/start")
def orchestrator_start(request: Request) -> dict:
    """INICIAR CAMPAÑA REAL: crea la ejecución + campaña de descubrimiento y
    avanza hasta el siguiente punto que exija datos externos (RESEARCH_PENDING)
    o una intervención legítima. Idempotente."""
    container = get_container(request)
    run = container.orchestrator.create_real_campaign()
    run = container.orchestrator.advance(run["run"]["id"])
    return {**run, "real_money_moved": False}


@router.get("/orchestrator/runs/{run_id}")
def orchestrator_detail(request: Request, run_id: str = Depends(valid_run_id)) -> dict:
    return get_container(request).orchestrator.detail(run_id)


@router.get("/orchestrator/current")
def orchestrator_current(request: Request) -> dict:
    """Ejecución activa del orquestador (o null si no hay)."""
    container = get_container(request)
    run = container.orchestrator.current_run()
    if run is None:
        return {"run": None}
    return container.orchestrator.detail(run["id"])


@router.post("/orchestrator/runs/{run_id}/advance")
def orchestrator_advance(request: Request, run_id: str = Depends(valid_run_id)) -> dict:
    return get_container(request).orchestrator.advance(run_id)


@router.post("/orchestrator/runs/{run_id}/pause")
def orchestrator_pause(request: Request, run_id: str = Depends(valid_run_id)) -> dict:
    return get_container(request).orchestrator.pause(run_id)


@router.post("/orchestrator/runs/{run_id}/resume")
def orchestrator_resume(request: Request, run_id: str = Depends(valid_run_id)) -> dict:
    return get_container(request).orchestrator.resume(run_id)


@router.post("/orchestrator/runs/{run_id}/cancel")
def orchestrator_cancel(request: Request, run_id: str = Depends(valid_run_id)) -> dict:
    return get_container(request).orchestrator.cancel(run_id)


class ResearchImportIn(BaseModel):
    """Importación de resultados de misiones pegados desde el panel."""

    model_config = ConfigDict(extra="forbid")

    mission_id: str = Field(min_length=1, max_length=200)
    opportunity_id: str | None = Field(default=None, max_length=64)
    evidences: list[dict] = Field(default_factory=list)
    competitors: list[dict] = Field(default_factory=list)
    buyer_confirmed: dict | None = None
    notes: str | None = Field(default=None, max_length=5_000)


@router.post("/orchestrator/runs/{run_id}/import-research")
def orchestrator_import_research(
    request: Request, payload: list[ResearchImportIn], run_id: str = Depends(valid_run_id)
) -> dict:
    """Pegar investigación (respuestas Freebuff/modelos) y reanudar la campaña
    automáticamente. Las evidencias solo cuentan con URL + fecha + fragmento."""
    container = get_container(request)
    result = container.orchestrator.import_research(run_id, [p.model_dump() for p in payload])
    return {**result, "real_money_moved": False}


@router.get("/orchestrator/runs/{run_id}/missions")
def orchestrator_missions(request: Request, run_id: str = Depends(valid_run_id)) -> dict:
    """Misiones pendientes de investigación de la ejecución (para copiar).

    Iteración 016: si no hay misiones, explica HONESTAMENTE el motivo (p. ej.
    cero candidatas concretas) en lugar de devolver una lista vacía silenciosa;
    cada misión lleva su contexto completo trazable y hay recuento de estados
    de conceptos para que los contadores del frontend coincidan con el backend.
    """
    container = get_container(request)
    run = container.orchestrator._get(run_id)
    rows = container.repos.orchestrator.transitions_for(run_id)
    missions: list[dict] = []
    explanation: str | None = None
    status_counts: dict = {}
    for t in rows:
        if t.get("to_state") == "RESEARCH_PLANNED":
            outs = t.get("outputs") or {}
            missions = list(outs.get("missions") or [])
            break
        if t.get("to_state") == "RESEARCH_PENDING":
            outs = t.get("outputs") or {}
            explanation = outs.get("no_mission_explanation")
            status_counts = dict(outs.get("concept_status_counts") or {})
    if not missions and run.get("discovery_campaign_id"):
        # Fallback robusto: misiones activas persistidas (nunca superseded).
        try:
            active = [
                m for m in container.repos.discovery.missions_by_campaign(run["discovery_campaign_id"])
                if m.get("status") not in ("SUPERSEDED_BY_SEMANTIC_QUALITY_GATE", "CANCELLED")
            ]
            missions = [
                {
                    "mission_id": m["mission_id"],
                    "kind": (m.get("target") or {}).get("kind") or "MISSION",
                    "concept_id": (m.get("target") or {}).get("concept_id"),
                    "opportunity_id": None,
                }
                for m in active
            ]
        except Exception:
            pass
    for m in missions:
        try:
            m["markdown"] = container.discovery.export_mission_markdown(m["mission_id"])
        except Exception:
            m["markdown"] = None
        # Contexto trazable de la candidata asociada.
        title = None
        cid = m.get("concept_id")
        if cid and run.get("discovery_campaign_id"):
            try:
                det = container.discovery.campaign_detail(run["discovery_campaign_id"])
                for c in det.get("concepts") or []:
                    if c.get("id") == cid:
                        title = c.get("title")
                        break
            except Exception:
                title = None
        m["concept_title"] = title
    if not missions and explanation is None:
        explanation = (
            f"No hay misiones pendientes en el estado {run['state']}: todavía no se ha "
            f"planificado ninguna investigación o todas están importadas/superseded."
        )
    return {
        "run_id": run_id,
        "state": run["state"],
        "missions": missions,
        "count": len(missions),
        "explanation": explanation,
        "status_counts": status_counts,
    }


@router.get("/orchestrator/runs/{run_id}/exports/{fmt}")
def orchestrator_export(
    request: Request, run_id: str = Depends(valid_run_id), fmt: str = "csv"
) -> Response:
    """Descargables de ideas: csv | json | md | finalists | research_zip."""
    from app.services import campaign_exports as exp

    container = get_container(request)
    run = container.orchestrator._get(run_id)
    detail = container.discovery.campaign_detail(run["discovery_campaign_id"])
    # Etiqueta conservadora: los conceptos generados offline (mock) no son
    # evidencia de mercado; se marcan como sintéticos hasta que haya
    # investigación externa verificada importada.
    synthetic = True
    if fmt == "csv":
        content = exp.build_csv(detail, synthetic=synthetic)
        media, name = "text/csv; charset=utf-8", f"business_ideas_campaign_{run['id'][:8]}.csv"
    elif fmt == "json":
        content = exp.build_json(detail, synthetic=synthetic, run=run)
        media, name = "application/json; charset=utf-8", f"business_ideas_campaign_{run['id'][:8]}.json"
    elif fmt == "md":
        content = exp.build_markdown(detail, synthetic=synthetic)
        media, name = "text/markdown; charset=utf-8", f"business_ideas_campaign_{run['id'][:8]}.md"
    elif fmt == "finalists":
        content = exp.build_finalists_markdown(detail, synthetic=synthetic, committee=container.orchestrator.detail(run_id)["committee"])
        media, name = "text/markdown; charset=utf-8", f"business_ideas_campaign_{run['id'][:8]}_finalists.md"
    elif fmt == "research_zip":
        missions = container.orchestrator.detail(run_id)["transitions"]
        by_concept: dict[str, list[dict]] = {}
        md_map: dict[str, str] = {}
        for t in missions:
            if t.get("to_state") == "RESEARCH_PLANNED":
                for m in (t.get("outputs") or {}).get("missions") or []:
                    by_concept.setdefault(m.get("concept_id"), []).append(m)
                    try:
                        md_map[m["mission_id"]] = container.discovery.export_mission_markdown(m["mission_id"])
                    except Exception:
                        pass
        content = exp.build_research_packets_zip(detail, by_concept, md_map)
        media, name = "application/zip", f"business_ideas_campaign_{run['id'][:8]}_research_packets.zip"
        return Response(content=content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})
    else:
        raise ValidationError(f"Formato de exportación desconocido: {fmt}")
    return Response(
        content=content if isinstance(content, str) else content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


# ---------------------------------------------------------------------------
# Economía SIMULADA (nunca mueve dinero real)
# ---------------------------------------------------------------------------
@router.get("/economy/status")
def economy_status(request: Request) -> dict:
    return get_container(request).economy.status()


@router.get("/economy/metrics")
def economy_metrics(request: Request) -> dict:
    return get_container(request).economy.metrics()


@router.get("/economy/cycle")
def economy_cycle(request: Request) -> dict:
    """Estado del ciclo económico inicial (30 días / 50 USD; vías A/B)."""
    return get_container(request).cycle.evaluate()


@router.post("/economy/cycle/extend")
def economy_cycle_extend(request: Request) -> dict:
    """Solicita la prórroga única de 14 días (vía B). Determinista: se rechaza
    sin un pago real confirmado (y solo puede concederse una vez)."""
    return get_container(request).cycle.request_extension()


@router.post("/economy/cycle/start")
def economy_cycle_start(request: Request) -> dict:
    """Arranque EXPLÍCITO del ciclo (PRE_CYCLE → en marcha). Determinista e
    idempotente. Sin precondiciones cumplidas devuelve started:false con
    missing_conditions y el reloj sigue parado. Consultar el estado o abrir
    la web NUNCA arranca el reloj."""
    return get_container(request).cycle.start(actor="owner")


@router.get("/economy/ledger")
def economy_ledger(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    opportunity_id: str | None = None,
    experiment_id: str | None = None,
    status: str | None = None,
) -> dict:
    container = get_container(request)
    items = container.repos.ledger.list(limit=limit, opportunity_id=opportunity_id, experiment_id=experiment_id, status=status)
    return {
        "simulated": True,
        "real_money_moved": False,
        "items": [e.model_dump(mode="json") for e in items],
        "count": len(items),
        "total": container.repos.ledger.count(),
    }


@router.post("/economy/simulation/start")
def economy_simulation_start(payload: SimulationStartIn, request: Request) -> dict:
    return get_container(request).economy.start_simulation(payload)


@router.post("/economy/income")
def economy_income(payload: IncomeIn, request: Request) -> dict:
    return get_container(request).economy.record_income(payload)


@router.post("/economy/expense/request")
def economy_expense_request(payload: ExpenseRequestIn, request: Request) -> dict:
    return get_container(request).economy.request_expense(payload)


@router.post("/economy/expense/{entry_id}/confirm")
def economy_expense_confirm(request: Request, entry_id: str = Depends(valid_entry_id)) -> dict:
    return get_container(request).economy.confirm_expense(entry_id)


@router.post("/economy/expense/{entry_id}/reject")
def economy_expense_reject(request: Request, entry_id: str = Depends(valid_entry_id)) -> dict:
    return get_container(request).economy.reject_expense(entry_id)


@router.post("/economy/ledger/{entry_id}/reverse")
def economy_ledger_reverse(request: Request, payload: ReverseIn, entry_id: str = Depends(valid_entry_id)) -> dict:
    return get_container(request).economy.reverse_entry(entry_id, reason=payload.reason, actor=payload.actor)


@router.post("/economy/reconcile")
def economy_reconcile(request: Request) -> dict:
    return get_container(request).economy.reconcile()


# ---------------------------------------------------------------------------
# Oportunidades
# ---------------------------------------------------------------------------
@router.get("/opportunities")
def list_opportunities(
    request: Request,
    status: OpportunityStatus | None = None,
    min_score: float | None = Query(default=None, ge=0, le=100),
    max_score: float | None = Query(default=None, ge=0, le=100),
) -> dict:
    container = get_container(request)
    items = container.opportunities.list_with_scores(status=status)
    if min_score is not None:
        items = [i for i in items if i.get("final_score") is not None and i["final_score"] >= min_score]
    if max_score is not None:
        items = [i for i in items if i.get("final_score") is not None and i["final_score"] <= max_score]
    return {"items": items, "count": len(items)}


@router.post("/opportunities")
def create_opportunity(payload: OpportunityCreate, request: Request) -> dict:
    container = get_container(request)
    opportunity = container.opportunities.create(payload)
    return container.opportunities.detail(opportunity.id)


@router.post("/opportunities/discover")
def discover(payload: ProblemSeed, request: Request) -> dict:
    """Pasos 1-3: Scout genera oportunidades a partir de un problema."""
    container = get_container(request)
    created = container.pipeline.discover(
        problem=payload.problem,
        sector_hint=payload.sector_hint,
        source=payload.source,
    )
    return {"created": [o.model_dump() for o in created], "count": len(created)}


@router.get("/opportunities/{opportunity_id}")
def get_opportunity(request: Request, opportunity_id: str = Depends(valid_id)) -> dict:
    return get_container(request).opportunities.detail(opportunity_id)


@router.post("/opportunities/{opportunity_id}/evaluate")
def evaluate_opportunity(request: Request, opportunity_id: str = Depends(valid_id)) -> dict:
    container = get_container(request)
    evaluation = container.pipeline.evaluate(opportunity_id)
    return {
        "evaluation": evaluation.model_dump(),
        "detail": container.opportunities.detail(opportunity_id),
    }


@router.post("/opportunities/{opportunity_id}/decision")
def decide_opportunity(
    request: Request,
    payload: DecisionIn,
    opportunity_id: str = Depends(valid_id),
) -> dict:
    container = get_container(request)
    opportunity = container.opportunities.set_decision(opportunity_id, payload.decision, note=payload.note)
    return {"opportunity": opportunity.model_dump(), "detail": container.opportunities.detail(opportunity_id)}


@router.get("/opportunities/{opportunity_id}/export")
def export_opportunity(
    request: Request,
    opportunity_id: str = Depends(valid_id),
    format: Literal["json", "md"] = "json",
) -> Response:
    container = get_container(request)
    if format == "json":
        data = container.exports.export_json(opportunity_id)
        return Response(
            content=json.dumps(data, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="opportunity_{opportunity_id}.json"'},
        )
    markdown = container.exports.export_markdown(opportunity_id)
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="opportunity_{opportunity_id}.md"'},
    )


# ---------------------------------------------------------------------------
# Business Discovery Engine (iteración 004)
# ---------------------------------------------------------------------------
@router.get("/discovery/campaigns")
def discovery_list_campaigns(request: Request) -> dict:
    container = get_container(request)
    items = container.discovery.list_campaigns()
    return {"items": items, "count": len(items)}


@router.post("/discovery/campaigns")
def discovery_create_campaign(payload: DiscoveryCampaignCreate, request: Request) -> dict:
    container = get_container(request)
    campaign = container.discovery.create_campaign(payload.model_dump())
    return {"campaign": campaign}


@router.get("/discovery/campaigns/{campaign_id}")
def discovery_get_campaign(request: Request, campaign_id: str = Depends(valid_campaign_id)) -> dict:
    return get_container(request).discovery.campaign_detail(campaign_id)


@router.post("/discovery/campaigns/{campaign_id}/phase1")
def discovery_phase1(request: Request, campaign_id: str = Depends(valid_campaign_id)) -> dict:
    return get_container(request).discovery.run_phase1(campaign_id)


@router.post("/discovery/campaigns/{campaign_id}/filter")
def discovery_filter(request: Request, campaign_id: str = Depends(valid_campaign_id)) -> dict:
    return get_container(request).discovery.run_commodity_filter(campaign_id)


@router.post("/discovery/campaigns/{campaign_id}/recombine")
def discovery_recombine(request: Request, campaign_id: str = Depends(valid_campaign_id)) -> dict:
    return get_container(request).discovery.run_recombine(campaign_id)


@router.post("/discovery/campaigns/{campaign_id}/shortlist")
def discovery_shortlist(request: Request, campaign_id: str = Depends(valid_campaign_id)) -> dict:
    return get_container(request).discovery.run_shortlist(campaign_id)


@router.post("/discovery/campaigns/{campaign_id}/tournament")
def discovery_tournament(request: Request, campaign_id: str = Depends(valid_campaign_id)) -> dict:
    return get_container(request).discovery.run_tournament(campaign_id)


class OpportunityBriefIn(BaseModel):
    """Opportunity Brief (iteración 013): hipótesis concreta, no evidencia."""

    model_config = ConfigDict(extra="forbid")
    brief: dict


class ReformulationPlanIn(BaseModel):
    """Plan de reformulación portable (iteración 017). Los concept_id que
    trae son de una reproducción aislada: NUNCA se insertan, solo trazabilidad."""

    model_config = ConfigDict(extra="forbid")
    plan: dict = Field(min_length=2)
    preview: bool = True
    run_id: str | None = Field(default=None, max_length=64)


class ResearchPortablePackageIn(BaseModel):
    """Paquete de investigación portable (iteración 017): se asocia a misiones
    LOCALES por mapeo estable (título normalizado + kind + phase + ordinal)."""

    model_config = ConfigDict(extra="forbid")
    package: dict = Field(min_length=2)
    apply: bool = False
    run_id: str | None = Field(default=None, max_length=64)


@router.post("/discovery/campaigns/{campaign_id}/reprocess")
def discovery_reprocess(request: Request, campaign_id: str = Depends(valid_campaign_id)) -> dict:
    """Iteración 013: reprocesa la campaña con la puerta de calidad semántica
    (estados honestos, coherencia, marcadores genéricos, misiones superseded).
    No borra ideas ni evidencia: conserva trazabilidad."""
    return get_container(request).discovery.reprocess_semantic_gate(campaign_id)


@router.post("/discovery/campaigns/{campaign_id}/reformulations/{concept_id}")
def discovery_generate_reformulations(
    request: Request,
    campaign_id: str = Depends(valid_campaign_id),
    concept_id: str = Depends(valid_concept_id),
) -> dict:
    """Iteración 013: genera 3-5 reformulaciones concretas (hipótesis) para un
    concepto abstracto. Ninguna se investiga hasta completar su brief."""
    return get_container(request).discovery.generate_reformulations(campaign_id, concept_id)


@router.post("/orchestrator/reformulation-plan")
def orchestrator_apply_reformulation_plan(request: Request, payload: ReformulationPlanIn) -> dict:
    """APLICAR PLAN DE REFORMULACIÓN (iteración 017): localiza los conceptos
    LOCALES por título normalizado / territorio+lente+arquetipo con coincidencia
    inequívoca, aplica los briefs válidos y deja que el orquestador ejecute
    Quality Gate + torneo (≤3) + misiones Fase 1 con IDs locales. Idempotente.
    Los IDs del plan nunca se insertan en la base local."""
    from app.services.reformulation_import import apply_reformulation_plan

    container = get_container(request)
    result = apply_reformulation_plan(
        container, payload.plan, run_id=payload.run_id, preview=payload.preview
    )
    return {**result, "real_money_moved": False}


@router.post("/orchestrator/research-package")
def orchestrator_resolve_research_package(request: Request, payload: ResearchPortablePackageIn) -> dict:
    """Importación en lote de un paquete de investigación portable (iteración
    017): asocia resultados a misiones locales por mapeo estable; asociaciones
    ambiguas se rechazan; delega en import_research (raw conservado, dedupe,
    verificación URL+fecha+fragmento). Con apply=False devuelve la vista previa."""
    from app.services.reformulation_import import resolve_research_package

    container = get_container(request)
    result = resolve_research_package(
        container, payload.package, run_id=payload.run_id, apply=payload.apply
    )
    return {**result, "real_money_moved": False}


@router.post("/discovery/concepts/{concept_id}/brief")
def discovery_complete_brief(payload: OpportunityBriefIn, request: Request, concept_id: str = Depends(valid_concept_id)) -> dict:
    """Iteración 013: completa el Opportunity Brief. Solo si es concreto el
    concepto pasa a RESEARCH_CANDIDATE. El brief es hipótesis: no añade
    evidencia ni demanda verificada."""
    return get_container(request).discovery.complete_opportunity_brief(concept_id, payload.brief)


@router.get("/discovery/concepts/{concept_id}")
def discovery_get_concept(request: Request, concept_id: str = Depends(valid_concept_id)) -> dict:
    container = get_container(request)
    concept = container.repos.discovery.get_concept(concept_id)
    if concept is None:
        from app.core.errors import NotFoundError

        raise NotFoundError("Concepto no encontrado.")
    tests = container.repos.discovery.substitution_tests_by_concept(concept_id)
    evals = container.repos.discovery.venture_evaluations_by_concept(concept_id)
    return {
        "concept": concept,
        "substitution": tests[0] if tests else None,
        "venture": evals[0] if evals else None,
    }


@router.post("/discovery/concepts/{concept_id}/promote")
def discovery_promote(request: Request, concept_id: str = Depends(valid_concept_id)) -> dict:
    container = get_container(request)
    opportunity = container.discovery.promote(concept_id)
    return container.opportunities.detail(opportunity.id)


@router.post("/discovery/missions")
def discovery_create_mission(payload: MissionCreateIn, request: Request) -> dict:
    container = get_container(request)
    mission = container.discovery.create_mission(
        kind=payload.kind,
        campaign_id=payload.campaign_id,
        concept_id=payload.concept_id,
    )
    return {"mission": mission.model_dump(mode="json")}


@router.get("/discovery/missions")
def discovery_list_missions(request: Request, status: str | None = None) -> dict:
    container = get_container(request)
    items = container.discovery.list_missions(status=status)
    return {"items": items, "count": len(items)}


@router.get("/discovery/missions/{mission_id}/export")
def discovery_export_mission(request: Request, mission_id: str = Depends(valid_mission_id)) -> Response:
    container = get_container(request)
    markdown = container.discovery.export_mission_markdown(mission_id)
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="mission_{mission_id}.md"'},
    )


@router.post("/discovery/missions/{mission_id}/import")
def discovery_import_mission(payload: MissionIn, request: Request, mission_id: str = Depends(valid_mission_id)) -> dict:
    return get_container(request).discovery.import_mission_result(mission_id, payload)


@router.post("/discovery/opportunities/{opportunity_id}/missions/{mission_id}/attach")
def discovery_attach_mission(
    request: Request,
    opportunity_id: str = Depends(valid_id),
    mission_id: str = Depends(valid_mission_id),
) -> dict:
    return get_container(request).discovery.attach_mission_evidence(opportunity_id, mission_id)


@router.get("/discovery/learning")
def discovery_learning(request: Request, kind: str | None = None) -> dict:
    container = get_container(request)
    items = container.discovery.list_learning_records(kind=kind)
    return {"items": items, "count": len(items)}


# ---------------------------------------------------------------------------
# Comité de contraste: Laboratorio de oportunidades (iteración 005)
# ---------------------------------------------------------------------------
# Las revisiones son OPINIÓN de modelos, nunca evidencia de demanda.
REVIEW_NOTICE = {"model_opinion_not_evidence": True, "real_money_moved": False}

# Iteración 023: single-flight para síntesis/decisión del comité. La conexión
# SQLite es COMPARTIDA entre hilos (uvicorn atiende peticiones en paralelo) y
# sqlite3 no serializa una transacción entre hilos. Un doble clic (o dos
# operaciones solapadas síntesis+decisión) podía abrir un COMMIT a mitad de la
# lectura del otro hilo → "cannot start a transaction within a transaction" →
# error no manejado → el frontend se quedaba en "Sintetizando…" para siempre.
# El lock garantiza que solo UNA operación del comité accede a la vez; es
# idempotente y rápido (determinista), así que reintentar es seguro.
_COMMITTEE_OPS_LOCK = threading.RLock()


@router.post("/reviews/opportunities/{opportunity_id}/auto-review-omniroute")
def reviews_auto_review_omniroute(request: Request, opportunity_id: str = Depends(valid_id)) -> dict:
    """Segundo revisor OPCIONAL vía OmniRoute (aislado; desactivado por defecto)."""
    container = get_container(request)
    result = container.reviews.auto_review_omniroute(opportunity_id)
    return {**REVIEW_NOTICE, **OMNIROUTE_NOTICE, **result, "provider": "omniroute"}


@router.get("/reviews/auto-status")
def reviews_auto_status(request: Request) -> dict:
    """Presupuesto de inferencia y circuit breaker (sin llamadas)."""
    return {"auto_status": get_container(request).reviews.auto_status()}


@router.get("/reviews/queue")
def reviews_queue(request: Request, status: str | None = None) -> dict:
    container = get_container(request)
    data = container.reviews.queue_status()
    if status:
        data["items"] = [i for i in data["items"] if i["status"] == status]
        data["count"] = len(data["items"])
    return {**REVIEW_NOTICE, **data}


@router.post("/reviews/opportunities/{opportunity_id}/queue")
def reviews_enqueue(request: Request, payload: QueueOpportunityIn, opportunity_id: str = Depends(valid_id)) -> dict:
    container = get_container(request)
    item = container.reviews.queue_opportunity(opportunity_id, note=payload.note)
    return {**REVIEW_NOTICE, "queue_item": item}


@router.post("/reviews/opportunities/{opportunity_id}/packet")
def reviews_generate_packet(request: Request, opportunity_id: str = Depends(valid_id)) -> dict:
    container = get_container(request)
    packet = container.reviews.generate_review_packet(opportunity_id)
    return {**REVIEW_NOTICE, **packet}


@router.get("/reviews/opportunities/{opportunity_id}/packet")
def reviews_download_packet(request: Request, opportunity_id: str = Depends(valid_id)) -> Response:
    container = get_container(request)
    packet = container.reviews.get_review_packet(opportunity_id)
    return Response(
        content=packet["content"],
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="review_packet_{opportunity_id}.md"',
            "X-Review-Packet-Sha256": packet["sha256"],
        },
    )


@router.post("/reviews/opportunities/{opportunity_id}/import")
def reviews_import(request: Request, payload: ReviewImportIn, opportunity_id: str = Depends(valid_id)) -> dict:
    container = get_container(request)
    with _COMMITTEE_OPS_LOCK:
        result = container.reviews.import_review(opportunity_id, payload)
    return {**REVIEW_NOTICE, **result}


@router.get("/reviews/opportunities/{opportunity_id}/packet/copy")
def reviews_copy_packet(
    request: Request, opportunity_id: str = Depends(valid_id), reviewer: str | None = Query(default=None)
) -> dict:
    """Expediente listo para COPIAR (mismo contenido base para todos los
    revisores; solo varía la cabecera de metadatos del revisor)."""
    container = get_container(request)
    packet = container.reviews.review_packet_for_copy(opportunity_id, reviewer=reviewer)
    return {**REVIEW_NOTICE, **packet}


@router.post("/reviews/opportunities/{opportunity_id}/import-combined")
def reviews_import_combined(
    request: Request, payload: CombinedReviewImportIn, opportunity_id: str = Depends(valid_id)
) -> dict:
    """Importa un archivo combinado (# GPT / # GROK / # GEMINI / # HUMAN_NOTE)."""
    container = get_container(request)
    with _COMMITTEE_OPS_LOCK:
        result = container.reviews.import_combined_review(opportunity_id, payload)
    return {**REVIEW_NOTICE, **result}


@router.post("/reviews/opportunities/{opportunity_id}/decide")
def reviews_decide(request: Request, opportunity_id: str = Depends(valid_id)) -> dict:
    """Decisión autónoma determinista (sin votos del propietario). Nunca
    autoriza producción, gasto, ingresos ni elimina bloqueadores."""
    container = get_container(request)
    with _COMMITTEE_OPS_LOCK:
        result = container.reviews.committee_decision(opportunity_id)
    return {**REVIEW_NOTICE, **result}


@router.get("/reviews/opportunities/{opportunity_id}")
def reviews_list_for_opportunity(request: Request, opportunity_id: str = Depends(valid_id)) -> dict:
    container = get_container(request)
    reviews = container.repos.reviews.reviews_for(opportunity_id)
    synthesis = container.repos.reviews.get_synthesis(opportunity_id)
    return {
        **REVIEW_NOTICE,
        "opportunity_id": opportunity_id,
        "items": reviews,
        "count": len(reviews),
        "synthesis": synthesis,
    }


@router.get("/reviews/{review_id}")
def reviews_get(request: Request, review_id: str = Depends(valid_review_id)) -> dict:
    container = get_container(request)
    review = container.repos.reviews.get_review(review_id)
    if review is None:
        from app.core.errors import NotFoundError

        raise NotFoundError("Revisión no encontrada.")
    return {**REVIEW_NOTICE, "review": review}


@router.post("/reviews/{review_id}/invalidate")
def reviews_invalidate(request: Request, review_id: str = Depends(valid_review_id), reason: str | None = None) -> dict:
    container = get_container(request)
    updated = container.reviews.invalidate_review(review_id, reason=reason)
    return {**REVIEW_NOTICE, "review": updated}


@router.post("/reviews/opportunities/{opportunity_id}/synthesize")
def reviews_synthesize(request: Request, opportunity_id: str = Depends(valid_id)) -> dict:
    container = get_container(request)
    with _COMMITTEE_OPS_LOCK:
        synthesis = container.reviews.synthesize(opportunity_id)
    return {**REVIEW_NOTICE, "synthesis": synthesis}


@router.post("/reviews/opportunities/{opportunity_id}/synthesize-and-decide")
def reviews_synthesize_and_decide(request: Request, opportunity_id: str = Depends(valid_id)) -> dict:
    """Operación compuesta IDEMPOTENTE (iteración 023): valida revisiones,
    reutiliza la síntesis persistida si corresponde, sintetiza, decide,
    persiste y devuelve UN único contrato con `operation_id` y `status`.

    Reintenable tras timeout/refresco; sin llamadas LLM; sin modificar
    evidencia; sin iniciar PRE_CYCLE; sin conectar servicios; sin autorizar
    producción. Si la decisión es MORE_RESEARCH crea UNA misión específica
    (nunca repite las 18); si es REJECT señala las candidatas siguientes sin
    inventar sustitutas.
    """
    container = get_container(request)
    with _COMMITTEE_OPS_LOCK:
        result = container.reviews.synthesize_and_decide(opportunity_id)
    return result


@router.post("/reviews/opportunities/{opportunity_id}/continue")
def reviews_continue(request: Request, opportunity_id: str = Depends(valid_id), note: str | None = None) -> dict:
    container = get_container(request)
    item = container.reviews.continue_without_review(opportunity_id, note=note)
    return {**REVIEW_NOTICE, "queue_item": item}


@router.post("/reviews/opportunities/{opportunity_id}/note")
def reviews_note(request: Request, payload: QueueOpportunityIn, opportunity_id: str = Depends(valid_id)) -> dict:
    container = get_container(request)
    if not payload.note:
        raise ValidationError("La nota es obligatoria.")
    item = container.reviews.add_note(opportunity_id, payload.note)
    return {**REVIEW_NOTICE, "queue_item": item}


@router.post("/reviews/demo")
def reviews_demo(request: Request) -> dict:
    """Demostración SINTÉTICA del comité de contraste (etiquetada como demo)."""
    container = get_container(request)
    result = container.reviews.run_review_demo(container.pipeline)
    return {**REVIEW_NOTICE, **result}


@router.post("/reviews/opportunities/{opportunity_id}/auto-review")
def reviews_auto_review(request: Request, opportunity_id: str = Depends(valid_id)) -> dict:
    """Opción A: una revisión de contraste automática vía OpenRouter.

    Guardas deterministas (máx. 1 por oportunidad, circuit breaker, límites
    diarios/mensuales). Sin clave o con fallo: NO se fabrica revisión; la
    ausencia es neutral. Coste registrado con honestidad en llm_call_log.
    """
    container = get_container(request)
    result = container.reviews.auto_review(opportunity_id)
    return {
        **REVIEW_NOTICE,
        **result,
        "auto_review": True,
        "provider": "openrouter",
    }


@router.get("/llm-calls")
def llm_calls_list(request: Request, limit: int = Query(default=30, ge=1, le=200)) -> dict:
    """Log append-only de llamadas LLM (coste honesto por llamada)."""
    return {"items": get_container(request).repos.llm_calls.list_recent(limit=limit), "count": None}


# ---------------------------------------------------------------------------
# OmniRoute (OPCIONAL, AISLADO — iteración 008) y routing por tarea
# ---------------------------------------------------------------------------
OMNIROUTE_NOTICE = {"omniroute_isolated": True, "production_use_blocked": True}


@router.get("/providers/omniroute/status")
def omniroute_status(request: Request) -> dict:
    """Estado del proveedor OmniRoute (sin claves) + uso + allowlist."""
    container = get_container(request)
    provider = container.providers.omniroute
    today = __import__("datetime").date.today().isoformat()
    from app.core.omniroute_allowlist import is_connection_allowed

    allowed, reason = is_connection_allowed("omniroute-gateway", production=False)
    return {
        **OMNIROUTE_NOTICE,
        "enabled": provider.available(),
        "health": provider.health(),
        "requests_today": container.repos.llm_calls.count_since(today, provider="omniroute"),
        "daily_request_limit": container.settings.omniroute_daily_request_limit,
        "cost_today_usd": container.repos.llm_calls.cost_since(today, provider="omniroute"),
        "daily_cost_limit_usd": container.settings.omniroute_daily_cost_limit_usd,
        "allowlist_default": {"allowed": allowed, "reason": reason},
        "allow_free_only": container.settings.omniroute_allow_free_only,
    }


# ---------------------------------------------------------------------------
# Ventana prioritaria OX Alpha (iteración 015) — OPCIONAL, AISLADO, NO EVIDENCIA
# ---------------------------------------------------------------------------
OX_ALPHA_NOTICE = {
    "ox_alpha_is_evidence": False,
    "production_use_blocked": True,
    "real_money_moved": False,
}


class DeepTaskIn(BaseModel):
    """Petición de tarea profunda (P0) por la ventana OX Alpha."""

    model_config = ConfigDict(extra="forbid")
    task: str = Field(min_length=1, max_length=40)
    concept: dict = Field(default_factory=dict)
    concepts_for_comparison: list[dict] = Field(default_factory=list, max_length=20)
    opportunity_id: str | None = Field(default=None, max_length=64)


@router.get("/oxalpha/status")
def oxalpha_status(request: Request) -> dict:
    """Estado de la ventana gratuita (identidad verificada, expiración, límites).
    Sin claves ni secretos. La identidad es OX_ALPHA_UNVERIFIED hasta que el
    propietario fije el slug EXACTO tras verificarlo en el catálogo real."""
    container = get_container(request)
    return {**OX_ALPHA_NOTICE, **container.deep_reasoning.status()}


@router.post("/oxalpha/catalog-check")
def oxalpha_catalog_check(request: Request) -> dict:
    """Consulta el catálogo REAL del gateway para verificar el slug.
    Nunca inventa slugs; sin coincidencia inequívoca => OX_ALPHA_UNVERIFIED."""
    return {**OX_ALPHA_NOTICE, **get_container(request).deep_reasoning.catalog_check()}


@router.post("/oxalpha/task")
def oxalpha_task(payload: DeepTaskIn, request: Request) -> dict:
    """Ejecuta una tarea P0 reservada (reformulation | coherence_check |
    red_team | variation_comparison). Fallo/bloqueo => ausencia NEUTRAL;
    nunca salida sintética presentada como OX Alpha. El resultado es
    razonamiento de modelo: NUNCA evidencia y requiere validación
    determinista posterior."""
    container = get_container(request)
    result = container.deep_reasoning.run_deep_task(
        payload.task,
        payload.concept,
        opportunity_id=payload.opportunity_id,
        concepts_for_comparison=payload.concepts_for_comparison,
    )
    return {**OX_ALPHA_NOTICE, **result}


@router.get("/routing/policies")
def routing_policies(request: Request) -> dict:
    """Políticas de routing por tarea (deterministas, sin LLM)."""
    from app.core.routing_policies import TASK_POLICIES

    return {
        "policies": [
            {
                "task": p.task,
                "provider": p.provider,
                "model": p.model,
                "fallbacks": list(p.fallbacks),
                "max_cost_usd": p.max_cost_usd,
                "max_latency_ms": p.max_latency_ms,
                "requires_json": p.requires_json,
                "require_fixed_model": p.require_fixed_model,
                "allow_free_random": p.allow_free_random,
                "allow_continue_without_response": p.allow_continue_without_response,
                "notes": p.notes,
            }
            for p in TASK_POLICIES.values()
        ]
    }


@router.get("/omniroute/allowlist")
def omniroute_allowlist(request: Request) -> dict:
    """Allowlist de conexiones OmniRoute (sin secretos)."""
    from app.core.omniroute_allowlist import OMNIROUTE_CONNECTIONS

    return {
        **OMNIROUTE_NOTICE,
        "connections": [
            {
                "provider": c.provider,
                "auth_method": c.auth_method,
                "status": c.status,
                "review_date": c.review_date,
                "commercial_use_permitted": c.commercial_use_permitted,
                "notes": c.notes,
            }
            for c in OMNIROUTE_CONNECTIONS.values()
        ],
    }


# ---------------------------------------------------------------------------
# Campañas Freebuff-first (sesiones reanudables, sin API runtime)
# ---------------------------------------------------------------------------
CAMPAIGN_NOTICE = {"freebuff_session": True, "no_24_7_guarantee": True, "api_cost_usd": 0.0}


@router.get("/campaigns")
def campaigns_list(request: Request) -> dict:
    return get_container(request).campaigns.list_campaigns()


@router.post("/campaigns")
def campaigns_create(payload: CampaignCreate, request: Request) -> dict:
    return {**CAMPAIGN_NOTICE, **get_container(request).campaigns.create_campaign(payload.model_dump())}


@router.get("/campaigns/{campaign_id}")
def campaigns_detail(request: Request, campaign_id: str = Depends(valid_campaign_id)) -> dict:
    return get_container(request).campaigns.campaign_detail(campaign_id)


@router.post("/campaigns/{campaign_id}/stage")
def campaigns_stage(request: Request, payload: StageChangeIn, campaign_id: str = Depends(valid_campaign_id)) -> dict:
    return get_container(request).campaigns.transition(
        campaign_id, payload.to_stage, actor=payload.actor, reason=payload.reason, next_action=payload.next_action
    )


@router.get("/campaigns/{campaign_id}/prompt")
def campaigns_prompt(request: Request, campaign_id: str = Depends(valid_campaign_id)) -> dict:
    return {**CAMPAIGN_NOTICE, "short_prompt": get_container(request).campaigns.short_prompt(campaign_id)}


@router.get("/campaigns/{campaign_id}/sessions")
def campaigns_sessions(request: Request, campaign_id: str = Depends(valid_campaign_id)) -> dict:
    return {"sessions": get_container(request).repos.campaigns.sessions_for(campaign_id)}


@router.post("/campaigns/{campaign_id}/sessions")
def campaigns_prepare_session(payload: SessionPrepareIn, request: Request, campaign_id: str = Depends(valid_campaign_id)) -> dict:
    session = get_container(request).campaigns.prepare_session(campaign_id, payload.hours, actor=payload.actor)
    return {**CAMPAIGN_NOTICE, "session": session}


@router.get("/campaigns/{campaign_id}/reasoning")
def campaigns_reasoning(request: Request, campaign_id: str = Depends(valid_campaign_id)) -> dict:
    return {"reasoning_log": get_container(request).repos.campaigns.reasoning_for(campaign_id)}


@router.post("/campaigns/{campaign_id}/readiness/{opportunity_id}")
def campaigns_readiness(request: Request, campaign_id: str = Depends(valid_campaign_id), opportunity_id: str = Depends(valid_id)) -> dict:
    return {**CAMPAIGN_NOTICE, "gate": get_container(request).campaigns.evaluate_api_readiness(opportunity_id)}


@router.post("/campaigns/{campaign_id}/reasoning")
def campaigns_record_reasoning(payload: ReasoningIn, request: Request, campaign_id: str = Depends(valid_campaign_id)) -> dict:
    return get_container(request).campaigns.record_reasoning(
        campaign_id, payload.level, payload.action, payload.reason, session_id=payload.session_id
    )


@router.post("/campaigns/demo")
def campaigns_demo(request: Request) -> dict:
    """Piloto SINTÉTICO FREEBUFF-FIRST PILOT 001 (0 llamadas API, etiquetado)."""
    container = get_container(request)
    result = container.campaigns.run_demo(container.pipeline)
    return {**CAMPAIGN_NOTICE, **result}


# ---------------------------------------------------------------------------
# Sesiones Freebuff
# ---------------------------------------------------------------------------
@router.post("/sessions/{session_id}/import")
def sessions_import(payload: SessionOutputIn, request: Request, session_id: str) -> dict:
    return get_container(request).campaigns.import_session_output(session_id, payload)


@router.post("/sessions/{session_id}/finalize")
def sessions_finalize(request: Request, session_id: str) -> dict:
    return get_container(request).campaigns.finalize_session(session_id)


@router.get("/sessions")
def sessions_list(request: Request, limit: int = Query(default=20, ge=1, le=100)) -> dict:
    return {"sessions": get_container(request).repos.campaigns.list_sessions(limit=limit)}


# ---------------------------------------------------------------------------
# Activación de un clic (iteración 022): bootstrap comercial + candidatas
# ---------------------------------------------------------------------------
@router.get("/bootstrap/status")
def bootstrap_status(request: Request) -> dict:
    """Estado del bootstrap comercial (sin ejecutarlo): aplicado, recuperable,
    diagnóstico y acción de recuperación. Sin secretos ni stack traces."""
    return get_container(request).bootstrap.status(include_snapshot=True)


@router.post("/bootstrap/commercial")
def bootstrap_commercial(request: Request) -> dict:
    """REPARAR Y CONTINUAR AUTOMÁTICAMENTE: aplica el bootstrap comercial de
    forma idempotente y con checkpoints. Nunca duplica datos; deja producción
    bloqueada, gasto real en cero y PRE_CYCLE detenido."""
    return get_container(request).bootstrap.apply()


@router.get("/candidates")
def candidates(request: Request) -> dict:
    """Tarjetas de candidatas (máximo 3): datos de investigación empaquetados
    021 + puntuaciones/evidencia/revisiones en vivo. La ganadora es
    determinista PARA EXPERIMENTO; nunca demanda validada (sin pago real)."""
    return get_container(request).bootstrap.candidates()


# ---------------------------------------------------------------------------
# Asistente CONECTAR SERVICIOS (iteración 022) — sin secretos por API
# ---------------------------------------------------------------------------
@router.get("/services/status")
def services_status(request: Request) -> dict:
    """Estado de los servicios requeridos (CONNECTED / PARTIAL / INVALID /
    MISSING) + últimos 4 caracteres cuando es seguro. Nunca devuelve valores."""
    return get_container(request).connect_services.status()


class CredentialsSaveIn(BaseModel):
    """Guardado local de credenciales del asistente. Los valores se escriben en
    el archivo local de credenciales (`.env`, fuera de Git) y nunca se
    devuelven por la API."""

    model_config = ConfigDict(extra="forbid")
    values: dict[str, str] = Field(default_factory=dict)


@router.post("/services/save")
def services_save(payload: CredentialsSaveIn, request: Request) -> dict:
    return get_container(request).connect_services.save(payload.values)


@router.post("/services/check")
def services_check(payload: CredentialsSaveIn, request: Request) -> dict:
    return get_container(request).connect_services.check(payload.values)


# ---------------------------------------------------------------------------
# Importación / demostración
# ---------------------------------------------------------------------------
@router.post("/import")
def import_research(request: Request, payload: ResearchPackageIn, filename: str | None = None) -> dict:
    container = get_container(request)
    content_length = request.headers.get("content-length")
    if content_length:
        validate_payload_size(int(content_length), container.settings.max_upload_bytes)
    if filename:
        validate_extension(filename, container.settings.allowed_import_extensions)
    return container.imports.import_research(payload)


@router.post("/demo/load")
def load_demo(request: Request, evaluate: bool = True) -> dict:
    container = get_container(request)
    seeder = DemoSeeder(container.settings, container.repos, container.pipeline)
    return seeder.seed(evaluate=evaluate)


# ---------------------------------------------------------------------------
# Multi-Agent Ideation Arena (iteración 024)
# ---------------------------------------------------------------------------
@router.get("/arena/state")
def arena_state(request: Request) -> dict:
    return get_container(request).arena.get_state()


@router.post("/arena/generate")
def arena_generate(request: Request, count: int = Query(default=5, ge=1, le=20)) -> dict:
    return get_container(request).arena.generate_wawa_ideas(count=count)


@router.get("/arena/prompt")
def arena_prompt(
    request: Request,
    generator: str = Query(default="EXTERNAL_MODEL"),
) -> dict:
    return get_container(request).arena.generate_prompt(generator_label=generator)


@router.post("/arena/import")
def arena_import(request: Request, payload: models_arena.ArenaImportIn) -> dict:
    return get_container(request).arena.import_batch(
        provider=payload.provider,
        filename=payload.filename,
        content=payload.content,
        max_ideas=payload.max_ideas,
    )


@router.post("/arena/filter")
def arena_filter(request: Request) -> dict:
    return get_container(request).arena.run_filter()


@router.post("/arena/tournament")
def arena_tournament(request: Request) -> dict:
    return get_container(request).arena.run_tournament()


@router.get("/arena/review")
def arena_review(request: Request) -> dict:
    return get_container(request).arena.get_review_queue()


@router.post("/arena/approve")
def arena_approve(request: Request, payload: models_arena.ArenaApproveIn) -> dict:
    return get_container(request).arena.approve_for_research(payload.idea_ids)


@router.get("/arena/providers")
def arena_providers(request: Request) -> dict:
    return {"providers": get_container(request).arena.get_provider_statuses()}


@router.get("/arena/events")
def arena_events(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    agent: str | None = Query(default=None),
) -> dict:
    return {"events": get_container(request).arena.get_events(limit=limit, agent=agent)}


@router.post("/arena/reset")
def arena_reset(request: Request) -> dict:
    return get_container(request).arena.reset()


# =====================================================================
# AUTONOMOUS 24/7 RUNTIME (iteración 025)
# =====================================================================

@router.get("/runtime/status")
def runtime_status(request: Request) -> dict:
    """Estado completo del runtime autónomo: scheduler, worker, OmniRoute,
    circuit breaker, jobs, approvals, SAFE_PAUSE."""
    container = get_container(request)
    conn = container.conn
    row = conn.execute("SELECT * FROM runtime_state WHERE id = 1").fetchone()
    runtime = dict(row) if row else {}

    job_counts = container.repos.jobs.count_by_status()
    pending_approvals = container.repos.approvals.list_pending()

    return {
        "runtime": runtime,
        "scheduler_running": container.scheduler.is_running,
        "worker_running": container.worker.is_running,
        "llm_router": container.llm_router.health(),
        "job_counts": job_counts,
        "pending_approvals": len(pending_approvals),
        "safe_pause": container.safe_pause.status(),
    }


@router.get("/runtime/preflight")
def runtime_preflight(request: Request) -> dict:
    """Preflight: ¿listo para 24/7 autónomo?"""
    container = get_container(request)
    from app.services.preflight import run_preflight
    return run_preflight(container.conn, container.settings)


@router.get("/runtime/jobs")
def runtime_jobs(
    request: Request,
    status: str | None = Query(default=None),
    job_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    """Lista de jobs con filtros opcionales."""
    container = get_container(request)
    jobs = container.repos.jobs.list_jobs(status=status, job_type=job_type, limit=limit)
    return {"jobs": jobs, "total": len(jobs)}


@router.post("/runtime/jobs")
def runtime_create_job(request: Request, payload: dict) -> dict:
    """Crear un job manualmente (para testing o intervención del propietario)."""
    container = get_container(request)
    job = container.repos.jobs.create_job(
        job_type=payload.get("job_type", "maintenance_healthcheck"),
        payload=payload.get("payload", {}),
        priority=payload.get("priority", 2),
        idempotency_key=payload.get("idempotency_key", ""),
        purpose=payload.get("purpose", "maintenance"),
    )
    return {"job": job}


@router.post("/runtime/jobs/{job_id}/cancel")
def runtime_cancel_job(request: Request, job_id: str = Depends(valid_id)) -> dict:
    container = get_container(request)
    container.repos.jobs.cancel(job_id)
    return {"cancelled": True, "job_id": job_id}


@router.post("/runtime/jobs/{job_id}/retry")
def runtime_retry_job(request: Request, job_id: str = Depends(valid_id)) -> dict:
    """Forzar un job FAILED de vuelta a PENDING para reintento."""
    container = get_container(request)
    conn = container.conn
    conn.execute(
        "UPDATE job_queue SET status = 'PENDING', updated_at = ? WHERE job_id = ? AND status = 'FAILED'",
        (_now_str(), job_id),
    )
    conn.commit()
    return {"retried": True, "job_id": job_id}


@router.post("/runtime/pause")
def runtime_pause(request: Request, payload: dict | None = None) -> dict:
    """Activar SAFE_PAUSE."""
    container = get_container(request)
    reason = (payload or {}).get("reason", "Manual pause by owner")
    scope = (payload or {}).get("scope", "GLOBAL")
    return container.safe_pause.activate(reason, scope)


@router.post("/runtime/resume")
def runtime_resume(request: Request) -> dict:
    """Desactivar SAFE_PAUSE y reanudar jobs."""
    container = get_container(request)
    return container.safe_pause.deactivate(actor="owner_api")


@router.get("/runtime/approvals")
def runtime_approvals(request: Request) -> dict:
    """Cola de aprobaciones pendientes del propietario."""
    container = get_container(request)
    pending = container.repos.approvals.list_pending()
    return {"approvals": pending, "count": len(pending)}


@router.post("/runtime/approvals/{approval_id}/decide")
def runtime_decide_approval(
    request: Request,
    approval_id: str = Depends(valid_id),
    payload: dict | None = None,
) -> dict:
    container = get_container(request)
    data = payload or {}
    decision = data.get("decision", "approved")
    notes = data.get("notes", "")
    result = container.repos.approvals.decide(approval_id, decision, notes=notes)
    return {"decided": True, "approval": result}


@router.get("/runtime/usage")
def runtime_usage(request: Request) -> dict:
    """Consumo de LLM: tokens, requests, coste hoy."""
    container = get_container(request)
    return container.llm_router.health()


@router.get("/runtime/provider-health")
def runtime_provider_health(request: Request) -> dict:
    """Salud del proveedor OmniRoute."""
    container = get_container(request)
    return container.llm_router.health()


@router.get("/runtime/audit")
def runtime_audit(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    """Últimos eventos de auditoría del runtime."""
    container = get_container(request)
    rows = container.conn.execute(
        "SELECT * FROM engine_events ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return {"events": [dict(r) for r in rows], "count": len(rows)}


@router.post("/runtime/backup")
def runtime_backup(request: Request) -> dict:
    """Forzar backup de la base de datos."""
    container = get_container(request)
    job = container.repos.jobs.create_job(
        job_type="maintenance_backup", priority=1, purpose="maintenance",
    )
    return {"job": job, "message": "Backup job enqueued"}


@router.get("/runtime/daily-summary")
def runtime_daily_summary(request: Request) -> dict:
    """Resumen diario de operación autónoma."""
    container = get_container(request)
    job_counts = container.repos.jobs.count_by_status()
    usage = container.llm_router.health()
    safe_pause = container.safe_pause.status()
    return {
        "job_counts": job_counts,
        "usage": usage,
        "safe_pause": safe_pause,
    }


def _now_str() -> str:
    import datetime
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
