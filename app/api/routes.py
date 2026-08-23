"""Rutas de la API local."""
from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import ValidationError
from app.core.security import validate_extension, validate_payload_size, validate_uuid
from app.models.discovery import CampaignCreate, MissionIn
from app.models.enums import Decision, OpportunityStatus, OperatingMode
from app.models.external_review import QueueOpportunityIn, ReviewImportIn
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
# Economía SIMULADA (nunca mueve dinero real)
# ---------------------------------------------------------------------------
@router.get("/economy/status")
def economy_status(request: Request) -> dict:
    return get_container(request).economy.status()


@router.get("/economy/metrics")
def economy_metrics(request: Request) -> dict:
    return get_container(request).economy.metrics()


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
def discovery_create_campaign(payload: CampaignCreate, request: Request) -> dict:
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
    result = container.reviews.import_review(opportunity_id, payload)
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
    synthesis = container.reviews.synthesize(opportunity_id)
    return {**REVIEW_NOTICE, "synthesis": synthesis}


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
