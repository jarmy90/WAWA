"""Orquestador end-to-end (iteración 010).

Un solo flujo conecta descubrimiento → ideas → filtros → torneo →
investigación → evidencias → reevaluación → finalistas → comité → decisión →
plan de experimento → PRE_CYCLE → ciclo económico (solo con capacidad
comercial real). El orquestador coordina servicios EXISTENTES (no duplica):
CampaignService, DiscoveryService, PipelineService, ReviewService y
CycleEvaluator.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

# Estados mínimos del orquestador (iteración 010).
ORCHESTRATOR_STATES = (
    "CAMPAIGN_CREATED",
    "DISCOVERING",
    "DEDUPLICATING",
    "FILTERING_COMMODITIES",
    "STRUCTURAL_ANALYSIS",
    "RECOMBINING",
    "SHORTLISTING",
    "TOURNAMENT",
    "RESEARCH_PLANNED",
    "RESEARCH_PENDING",
    "RESEARCH_IMPORTED",
    "REEVALUATING",
    "CANDIDATES_READY",
    "FINALISTS_READY",
    "COMMITTEE_READY",
    "COMMITTEE_PENDING",
    "COMMITTEE_COMPLETED",
    "DECIDING",
    "EXPERIMENT_READY",
    "EXPERIMENT_BLOCKED",
    "PRE_CYCLE",
    "READY_TO_START_CYCLE",
    "COMPLETED",
    "PAUSED",
    "FAILED",
)

RESEARCH_MISSION_KINDS = (
    "DEMAND_REALITY_CHECK",
    "BUYER_BUDGET_CHECK",
    "CURRENT_ALTERNATIVE_CHECK",
    "GENERAL_AI_SUBSTITUTION_CHECK",
    "COMPETITOR_EQUIVALENT_SEARCH",
    "DISTRIBUTION_ACCESS_CHECK",
    "MOAT_REALITY_CHECK",
    "DATA_AVAILABILITY_CHECK",
    "TOS_AND_LEGAL_CHECK",
    "EXPERIMENT_FEASIBILITY_CHECK",
)

# Iteración 013 (calidad semántica): misiones PROGRESIVAS. Fase 1 = misiones de
# descarte (demanda, comprador, alternativa, distribución, competencia,
# sustitución por IA). Si falla demanda/comprador/distribución ->
# EVIDENCE_INSUFFICIENT o REJECTED_AFTER_RESEARCH y NO se ejecuta la fase 2.
# Fase 2 (solo supervivientes): MOAT, DATA, TOS_LEGAL, EXPERIMENT_FEASIBILITY.
RESEARCH_PHASE1_KINDS = (
    "DEMAND_REALITY_CHECK",
    "BUYER_BUDGET_CHECK",
    "CURRENT_ALTERNATIVE_CHECK",
    "DISTRIBUTION_ACCESS_CHECK",
    "COMPETITOR_EQUIVALENT_SEARCH",
    "GENERAL_AI_SUBSTITUTION_CHECK",
)
RESEARCH_PHASE2_KINDS = (
    "MOAT_REALITY_CHECK",
    "DATA_AVAILABILITY_CHECK",
    "TOS_AND_LEGAL_CHECK",
    "EXPERIMENT_FEASIBILITY_CHECK",
)

# Configuración de la PRIMERA CAMPAÑA REAL (diversa; sin ventaja MQL5/trading).
FIRST_REAL_CAMPAIGN_CONFIG = {
    "title": "PRIMERA CAMPAÑA REAL 001",
    "campaign_type": "real_market_discovery",
    "phase1_target": 60,       # 60 conceptos iniciales
    "max_after_dedup": 30,     # máximo tras deduplicación
    "max_after_ai_filter": 15, # máximo tras filtro IA/commodity
    "research_candidates": 6,  # candidatas a investigación profunda
    "finalists_target": 3,     # máximo finalistas
    "experiments_selected": 1, # máximo experimento seleccionado
    "experiment_budget_usd": 10.0,   # máximo 10 USD para el primer experimento
    "build_days_max": 5,             # máximo 5 días de construcción
    "first_payment_goal_days": 10,   # objetivo de primer pago desde el lanzamiento
    "paid_ads": False,
    "spam": False,
    "restricted_sectors": ["trading", "finanzas_reguladas", "salud_regulada"],
}


def new_id() -> str:
    return uuid.uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExperimentPlan(BaseModel):
    """Plan de experimento creado automáticamente tras una decisión
    SMALL_EXPERIMENT o PRIORITY_EXPERIMENT del comité (nunca por opiniones de
    modelos; combina evaluación interna + evidencias + decisión determinista)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=new_id)
    run_id: str
    opportunity_id: str
    decision: str
    offer: str | None = None
    buyer: str | None = None
    user: str | None = None
    problem: str | None = None
    value_proposition: str | None = None
    price_usd: float | None = Field(default=None, ge=0)
    delivery_format: str | None = None
    demo: str | None = None
    channel: str | None = None
    initial_message: str | None = None
    min_sample: int | None = Field(default=None, ge=1)
    max_contacts: int | None = Field(default=None, ge=0)
    acquisition_method: str | None = None
    max_cost_usd: float | None = Field(default=None, ge=0)
    duration_days: int | None = Field(default=None, ge=1)
    success_metric: str | None = None
    success_threshold: str | None = None
    kill_condition: str | None = None
    product_death_condition: str | None = None
    possible_pivots: list[str] = Field(default_factory=list)
    automatable_tasks: list[str] = Field(default_factory=list)
    owner_tasks: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    payment_readiness: str | None = None
    missing_capabilities: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
