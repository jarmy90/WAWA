"""Contratos del Business Discovery Engine (iteración 004).

Conceptos, evaluaciones de calidad empresarial (Venture Quality Score),
General AI Substitution Test, misiones de investigación Freebuff-first y
memoria empresarial. Todo es determinista y nunca inventa evidencia de
mercado: los conceptos son HIPÓTESIS no verificadas hasta que una misión de
investigación aporte evidencias con URL, fecha y fragmento.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

VALID_SUBSTITUTION_CLASSES = (
    "COMMODITY_WRAPPER",
    "WEAK_DIFFERENTIATION",
    "DEFENSIBLE_WORKFLOW",
    "DATA_ADVANTAGE",
    "DISTRIBUTION_ADVANTAGE",
    "NETWORK_ADVANTAGE",
    "COMPOUNDING_SYSTEM",
)

VENTURE_LABELS = (
    "NOVEL_BUT_WEAK",
    "BORING_BUT_STRONG",
    "VIRAL_BUT_FRAGILE",
    "COMMODITY",
    "EXPERIMENT_READY",
    "CAPITAL_INTENSIVE",
    "DISTRIBUTION_FIRST",
    "DATA_COMPOUNDING",
    "NETWORK_POTENTIAL",
    "HIGH_TRUST_REQUIRED",
    "SERVICE_FIRST",
    "PRODUCT_POTENTIAL",
    "CATEGORY_CREATION_CANDIDATE",
)

VENTURE_HARD_BLOCKERS = (
    "COMMODITY_WRAPPER",
    "Sin comprador identificable.",
    "Sin camino creíble a los primeros 20 usuarios.",
    "Sin resultado medible.",
    "Sin vía de validación barata.",
    "Riesgo legal o de plataforma grave.",
    "Requiere capital elevado antes de aprender.",
    "Marketplace sin cuña de liquidez.",
    "Depende de spam no solicitado.",
    "Sin ventaja defendible y sin camino creíble para construirla.",
    "Es solo una feature de una plataforma general.",
    "Requeriría evidencia inventada para parecer viable.",
)


class SubstitutionAnswers(BaseModel):
    """Respuestas del General AI Substitution Test (0-100 cada una).

    Un valor alto en ``generic_ai_can_solve`` significa que una IA generalista
    (ChatGPT/Gemini/Claude/DeepSeek) resuelve el problema del cliente sin
    producto especializado.
    """

    model_config = ConfigDict(extra="forbid")

    generic_ai_can_solve: float = Field(default=50, ge=0, le=100)
    output_is_generic: float = Field(default=50, ge=0, le=100)
    has_operational_workflow: float = Field(default=0, ge=0, le=100)
    has_data_integration: float = Field(default=0, ge=0, le=100)
    has_accumulative_memory: float = Field(default=0, ge=0, le=100)
    has_verifiable_outcome: float = Field(default=0, ge=0, le=100)
    has_followup_action: float = Field(default=0, ge=0, le=100)
    has_switching_cost: float = Field(default=0, ge=0, le=100)
    improves_with_use: float = Field(default=0, ge=0, le=100)
    survives_model_improvement: float = Field(default=0, ge=0, le=100)
    network_effect: float = Field(default=0, ge=0, le=100)
    distribution_loop: float = Field(default=0, ge=0, le=100)
    data_advantage: float = Field(default=0, ge=0, le=100)


class SubstitutionTest(BaseModel):
    """Resultado del General AI Substitution Test (determinista)."""

    model_config = ConfigDict(extra="forbid")

    answers: SubstitutionAnswers
    classification: str = VALID_SUBSTITUTION_CLASSES[0]
    general_ai_resistance: float = Field(ge=0, le=100)
    verdict: str  # "ok" | "blocked"
    reasons: list[str] = Field(default_factory=list)


class MoatAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    moat_score: float = Field(ge=0, le=100)
    moat_type: str | None = None
    reasoning: str | None = None
    can_build_without_capital: bool = True


class DistributionHypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_20_users: str | None = None
    existing_behavior: str | None = None
    discovery_mechanism: str | None = None
    recommendation_loop: str | None = None
    output_distributes: str | None = None
    legality_note: str | None = None
    channel_score: float = Field(default=0, ge=0, le=100)


class BuyerProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: str | None = None
    buyer: str | None = None
    beneficiary: str | None = None
    budget_source: str | None = None
    trigger_event: str | None = None
    current_alternative: str | None = None
    cost_of_not_solving: str | None = None
    buyer_defined: bool = False


class VentureEvaluation(BaseModel):
    """Venture Quality Score: calidad empresarial/estratégica (0-100)."""

    model_config = ConfigDict(extra="forbid")

    economic_pain: float = Field(ge=0, le=100)
    proven_demand: float = Field(ge=0, le=100)
    general_ai_resistance: float = Field(ge=0, le=100)
    defensibility: float = Field(ge=0, le=100)
    distribution: float = Field(ge=0, le=100)
    originality: float = Field(ge=0, le=100)
    validation_speed: float = Field(ge=0, le=100)
    gross_margin: float = Field(ge=0, le=100)
    recurrence: float = Field(ge=0, le=100)
    demonstrability: float = Field(ge=0, le=100)
    operational_simplicity: float = Field(ge=0, le=100)
    final_score: float = Field(ge=0, le=100)
    novelty_score: float = Field(ge=0, le=100)
    utility_score: float = Field(ge=0, le=100)
    blockers: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    rationale: dict[str, str] = Field(default_factory=dict)


class ExperimentBlueprint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis: str | None = None
    cheapest_test: str | None = None
    maximum_budget_usd: float | None = None
    success_metric: str | None = None
    success_threshold: str | None = None
    failure_threshold: str | None = None
    duration: str | None = None


class ConceptCreate(BaseModel):
    """Entrada manual para añadir un concepto a una campaña."""

    model_config = ConfigDict(extra="forbid")

    campaign_id: str
    title: str = Field(min_length=3, max_length=300)
    territory_key: str | None = Field(default=None, max_length=100)
    lens_keys: list[str] = Field(default_factory=list)
    archetype_key: str | None = Field(default=None, max_length=100)
    problem_hypothesis: str = Field(min_length=10, max_length=20_000)
    mechanism: str = Field(min_length=10, max_length=20_000)
    buyer_hypothesis: str | None = Field(default=None, max_length=2_000)
    outcome_hypothesis: str | None = Field(default=None, max_length=2_000)
    why_now: str | None = Field(default=None, max_length=2_000)
    general_ai_risk: str | None = Field(default=None, max_length=2_000)
    asset_potential: str | None = Field(default=None, max_length=2_000)


class CampaignCreate(BaseModel):
    """Crea una campaña de descubrimiento (Ruta B: open opportunity discovery)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=300)
    territory_keys: list[str] = Field(default_factory=list)  # vacío = todas
    lens_keys: list[str] = Field(default_factory=list)  # vacío = todas
    archetype_keys: list[str] = Field(default_factory=list)  # vacío = todos
    phase1_target: int = Field(default=60, ge=20, le=200)
    shortlist_target: int = Field(default=10, ge=6, le=16)
    finalists_target: int = Field(default=3, ge=1, le=5)


class MissionIn(BaseModel):
    """Respuesta de una misión de investigación Freebuff (JSON reimportable)."""

    model_config = ConfigDict(extra="forbid")

    mission_id: str = Field(min_length=1, max_length=200)
    evidences: list[dict] = Field(default_factory=list)
    competitors: list[dict] = Field(default_factory=list)
    buyer_confirmed: dict | None = None
    notes: str | None = Field(default=None, max_length=5_000)
    verified: bool = False  # nunca se auto-marca: depende de URL+fecha+fragmento


class MissionExport(BaseModel):
    """Misión exportable para Freebuff (objetivo, preguntas, formato, campos)."""

    model_config = ConfigDict(extra="forbid")

    mission_id: str
    kind: str
    target: dict = Field(default_factory=dict)
    objective: str
    questions: list[str] = Field(default_factory=list)
    suggested_queries: list[str] = Field(default_factory=list)
    output_format: str
    required_evidence_fields: list[str] = Field(default_factory=list)
    no_invention_rule: str
    reliability_criteria: list[str] = Field(default_factory=list)
    json_import_schema: dict = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def new_id() -> str:
    return uuid.uuid4().hex
