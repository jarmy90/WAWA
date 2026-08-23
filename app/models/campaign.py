"""CampaignRunner Freebuff-first (iteración 006).

Campañas de descubrimiento/investigación ejecutadas mediante sesiones de
trabajo de 2-6 h con Freebuff, reanudables y con checkpoints persistentes.
Sin API LLM de producción: ``api_budget_usd=0`` por defecto y la política lo
registra. Nunca se asume que Freebuff es un runtime 24/7 ni que dispone de una
API runtime estable.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_FUNNEL_LIMITS: dict[str, int] = {
    "max_concepts": 100,
    "max_after_dedup": 40,
    "max_after_commodity": 20,
    "max_after_structural": 10,
    "max_after_tournament": 5,
    "maximum_finalists": 3,
}


def new_id() -> str:
    return uuid.uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CampaignStage(str, Enum):
    """Etapas de una campaña Freebuff-first (máquina de estados explícita)."""

    created = "CREATED"
    territory_selection = "TERRITORY_SELECTION"
    signal_collection = "SIGNAL_COLLECTION"
    wide_ideation = "WIDE_IDEATION"
    commodity_filter = "COMMODITY_FILTER"
    recombination = "RECOMBINATION"
    structural_analysis = "STRUCTURAL_ANALYSIS"
    shortlist = "SHORTLIST"
    internal_tournament = "INTERNAL_TOURNAMENT"
    finalists = "FINALISTS"
    research_missions = "RESEARCH_MISSIONS"
    external_review_ready = "EXTERNAL_REVIEW_READY"
    external_review_pending = "EXTERNAL_REVIEW_PENDING"
    synthesis = "SYNTHESIS"
    experiment_design = "EXPERIMENT_DESIGN"
    owner_review = "OWNER_REVIEW"
    completed = "COMPLETED"

    @property
    def label_es(self) -> str:
        return {
            "CREATED": "Creada",
            "TERRITORY_SELECTION": "Selección de territorios",
            "SIGNAL_COLLECTION": "Recogida de señales",
            "WIDE_IDEATION": "Ideación amplia",
            "COMMODITY_FILTER": "Filtro de comoditización",
            "RECOMBINATION": "Recombinación",
            "STRUCTURAL_ANALYSIS": "Análisis estructural",
            "SHORTLIST": "Shortlist",
            "INTERNAL_TOURNAMENT": "Torneo interno",
            "FINALISTS": "Finalistas",
            "RESEARCH_MISSIONS": "Misiones de investigación",
            "EXTERNAL_REVIEW_READY": "Comité listo",
            "EXTERNAL_REVIEW_PENDING": "Comité en curso",
            "SYNTHESIS": "Síntesis",
            "EXPERIMENT_DESIGN": "Diseño de experimento",
            "OWNER_REVIEW": "Revisión del propietario",
            "COMPLETED": "Completada",
        }[self.value]


class CampaignStatus(str, Enum):
    """Estado global de la campaña (puede pausarse/bloquearse en cualquier etapa)."""

    active = "active"
    paused = "PAUSED"
    blocked = "BLOCKED"
    failed = "FAILED"
    cancelled = "CANCELLED"
    completed = "COMPLETED"


class ReasoningLevel(str, Enum):
    """Niveles de profundidad de razonamiento (ahorro de tokens)."""

    level_0_deterministic = "LEVEL_0_DETERMINISTIC"
    level_1_fast_review = "LEVEL_1_FAST_REVIEW"
    level_2_deep_reasoning = "LEVEL_2_DEEP_REASONING"
    level_3_committee_ready = "LEVEL_3_COMMITTEE_READY"
    level_4_experiment_ready = "LEVEL_4_EXPERIMENT_READY"

    @property
    def label_es(self) -> str:
        return {
            "LEVEL_0_DETERMINISTIC": "Nivel 0 — determinista (dedup, filtros, reglas, persistencia)",
            "LEVEL_1_FAST_REVIEW": "Nivel 1 — revisión rápida (títulos, resúmenes, etiquetas, descartes obvios)",
            "LEVEL_2_DEEP_REASONING": "Nivel 2 — razonamiento profundo (recombinación, moat, distribución, comprador, red-team)",
            "LEVEL_3_COMMITTEE_READY": "Nivel 3 — listo para comité (máx. 10 candidatas, expedientes, pares)",
            "LEVEL_4_EXPERIMENT_READY": "Nivel 4 — listo para experimento (máx. 3 finalistas, tesis, investigación profunda)",
        }[self.value]


class APIReadinessState(str, Enum):
    api_not_needed = "API_NOT_NEEDED"
    api_premature = "API_PREMATURE"
    api_useful_for_experiment = "API_USEFUL_FOR_EXPERIMENT"
    api_required_for_delivery = "API_REQUIRED_FOR_DELIVERY"
    api_required_for_24_7_operation = "API_REQUIRED_FOR_24_7_OPERATION"
    api_rejected_low_roi = "API_REJECTED_LOW_ROI"


class ResearchMissionType(str, Enum):
    demand_reality_check = "DEMAND_REALITY_CHECK"
    buyer_budget_check = "BUYER_BUDGET_CHECK"
    current_alternative_check = "CURRENT_ALTERNATIVE_CHECK"
    general_ai_substitution_check = "GENERAL_AI_SUBSTITUTION_CHECK"
    competitor_equivalent_search = "COMPETITOR_EQUIVALENT_SEARCH"
    distribution_access_check = "DISTRIBUTION_ACCESS_CHECK"
    moat_reality_check = "MOAT_REALITY_CHECK"
    data_availability_check = "DATA_AVAILABILITY_CHECK"
    tos_and_legal_check = "TOS_AND_LEGAL_CHECK"
    experiment_feasibility_check = "EXPERIMENT_FEASIBILITY_CHECK"


class Campaign(BaseModel):
    """Campaña Freebuff-first reanudable."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=new_id)
    title: str = Field(min_length=3, max_length=300)
    status: CampaignStatus = CampaignStatus.active
    stage: CampaignStage = CampaignStage.created
    discovery_campaign_id: str | None = None
    territory_keys: list[str] = Field(default_factory=list)
    lens_keys: list[str] = Field(default_factory=list)
    archetype_keys: list[str] = Field(default_factory=list)
    # Presupuestos de la campaña (nunca aumentan silenciosamente).
    time_budget_hours: int = Field(default=3, ge=2, le=6)
    api_budget_usd: float = 0.0
    experiment_budget_usd: float = 0.0
    external_review_slots: int = 3
    maximum_deep_research_candidates: int = 10
    funnel_limits: dict[str, int] = Field(default_factory=lambda: dict(DEFAULT_FUNNEL_LIMITS))
    # Contadores observados.
    signals_count: int = 0
    concepts_count: int = 0
    concepts_rejected: int = 0
    finalists_count: int = 0
    missions_count: int = 0
    evidences_added: int = 0
    sessions_count: int = 0
    is_synthetic: bool = False
    closed_reason: str | None = None
    next_recommended_action: str | None = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class CampaignTransition(BaseModel):
    """Registro auditable de cada transición de etapa."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=new_id)
    campaign_id: str
    from_stage: str
    to_stage: str
    timestamp: str = Field(default_factory=_now)
    actor: str = "system"
    reason: str | None = None
    inputs_used: list[str] = Field(default_factory=list)
    outputs_generated: list[str] = Field(default_factory=list)
    concepts_considered: int = 0
    concepts_rejected: int = 0
    costs_recorded: dict = Field(default_factory=dict)
    unknowns: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    next_recommended_action: str | None = None


class FreebuffSession(BaseModel):
    """Sesión de trabajo reanudable (2-6 h) con artefactos persistentes."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=new_id)
    session_id: str = Field(default_factory=new_id)
    campaign_id: str
    status: str = "planned"  # planned | active | completed | failed
    time_budget_hours: int = Field(ge=2, le=6)
    stage_start: str = ""
    stage_end: str | None = None
    started_at: str = Field(default_factory=_now)
    completed_at: str | None = None
    tasks_planned: list[str] = Field(default_factory=list)
    tasks_completed: list[str] = Field(default_factory=list)
    tasks_pending: list[str] = Field(default_factory=list)
    concepts_created: int = 0
    concepts_rejected: int = 0
    evidences_added: int = 0
    review_packets_created: int = 0
    blockers: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    next_action: str | None = None
    repo_commit: str | None = None
    plan_path: str | None = None
    state_path: str | None = None
    output_path: str | None = None
    report_path: str | None = None
    next_session_path: str | None = None
    short_prompt: str | None = None
    is_synthetic: bool = False


class SessionOutputIn(BaseModel):
    """SESSION_OUTPUT.json: resultados estructurados importables.

    Todo es DATO: se valida, se deduplica y se respetan los límites del embudo.
    La verificación de evidencias exige URL + fecha + fragmento; nunca se
    auto-marca nada como demanda verificada sin referencias.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=64)
    completed_tasks: list[str] = Field(default_factory=list, max_length=100)
    signals: list[dict] = Field(default_factory=list, max_length=200)
    concepts: list[dict] = Field(default_factory=list, max_length=200)
    concepts_rejected: list[dict] = Field(default_factory=list, max_length=200)
    evidences: list[dict] = Field(default_factory=list, max_length=200)
    mission_results: list[dict] = Field(default_factory=list, max_length=50)
    reviews: list[dict] = Field(default_factory=list, max_length=20)
    blockers: list[str] = Field(default_factory=list, max_length=50)
    unknowns: list[str] = Field(default_factory=list, max_length=100)
    notes: str | None = Field(default=None, max_length=5_000)
    api_calls_made: int = Field(default=0, ge=0)
    api_cost_usd: float = Field(default=0.0, ge=0.0)


class APIReadinessGate(BaseModel):
    """API Readiness Gate: decide si gastar tokens empieza a tener sentido.

    NO activa ninguna API: solo es una puerta determinista. Por defecto
    ``API_PREMATURE`` o ``API_NOT_NEEDED``.
    """

    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    state: APIReadinessState = APIReadinessState.api_premature
    criteria: dict[str, bool] = Field(default_factory=dict)
    unknown_criteria: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    reasoning: str | None = None
    proposed_daily_limit_usd: float | None = None
    estimated_cost_per_call_usd: float | None = None
    estimated_value_per_call_usd: float | None = None
    evaluated_at: str = Field(default_factory=_now)


class ReasoningIn(BaseModel):
    """Entrada para registrar un nivel de razonamiento usado (auditoría)."""

    model_config = ConfigDict(extra="forbid")

    level: ReasoningLevel
    action: str = Field(min_length=1, max_length=200)
    reason: str | None = Field(default=None, max_length=1_000)
    session_id: str | None = Field(default=None, max_length=64)


class ReasoningRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=new_id)
    campaign_id: str
    session_id: str | None = None
    level: str
    action: str = Field(max_length=200)
    reason: str | None = None
    created_at: str = Field(default_factory=_now)


class CampaignCreate(BaseModel):
    """Creación de una campaña Freebuff-first."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=300)
    time_budget_hours: int = Field(default=3, ge=2, le=6)
    territory_keys: list[str] = Field(default_factory=list)
    lens_keys: list[str] = Field(default_factory=list)
    archetype_keys: list[str] = Field(default_factory=list)
    external_review_slots: int = Field(default=3, ge=0, le=10)
    maximum_finalists: int = Field(default=3, ge=0, le=5)
    maximum_deep_research_candidates: int = Field(default=10, ge=1, le=30)
    notes: str | None = Field(default=None, max_length=2_000)


class SessionPrepareIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hours: int = Field(ge=2, le=6)
    actor: str = Field(default="human", max_length=100)


class StageChangeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to_stage: CampaignStage
    actor: str = Field(default="human", max_length=100)
    reason: str | None = Field(default=None, max_length=2_000)
    next_action: str | None = Field(default=None, max_length=2_000)
