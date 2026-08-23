"""Evaluación completa de una oportunidad: criterios, puntuación y decisión."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Basis, Decision

CRITERIA_KEYS = (
    "pain",
    "demand",
    "customer_reach",
    "automation",
    "margin",
    "build_speed",
    "differentiation",
    "safety",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CriterionScore(BaseModel):
    """Puntuación de un criterio (0-100) con su base y evidencias que lo sustentan."""

    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0, le=100)
    basis: Basis = Basis.unknown
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str | None = Field(default=None, max_length=2_000)


class RiskItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str = Field(max_length=200)
    severity: str = Field(default="low", pattern="^(high|medium|low)$")
    description: str = Field(max_length=5_000)
    mitigation: str | None = Field(default=None, max_length=5_000)
    blocker: bool = False


class Estimates(BaseModel):
    """Estimaciones del Economist/Builder. Siempre son estimaciones, nunca datos."""

    model_config = ConfigDict(extra="forbid")

    build_cost_low_usd: float | None = None
    build_cost_high_usd: float | None = None
    price_low_usd: float | None = None
    price_high_usd: float | None = None
    margin_low_pct: float | None = None
    margin_high_pct: float | None = None
    recurrence: str | None = None
    time_to_first_sale_days: int | None = None
    initial_spend_level: str | None = None
    reachability: str | None = None
    complexity: str | None = None
    build_days_low: int | None = None
    build_days_high: int | None = None
    dependencies: list[str] = Field(default_factory=list)
    automation_degree: int | None = Field(default=None, ge=0, le=100)
    automatable_steps: list[str] = Field(default_factory=list)
    platform_dependencies: list[str] = Field(default_factory=list)


class Experiment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    opportunity_id: str
    hypothesis: str | None = None
    cheapest_test: str | None = None
    maximum_budget: float | None = Field(default=None, ge=0)
    success_metric: str | None = None
    success_threshold: str | None = None
    failure_threshold: str | None = None
    duration: str | None = None
    status: str = Field(default="proposed", pattern="^(proposed|running|success|failed|cancelled)$")
    result: str | None = None


class Evaluation(BaseModel):
    """Resultado persistido del Judge. Solo usa datos y evidencias guardados."""

    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    pain_score: float = Field(ge=0, le=100)
    demand_score: float = Field(ge=0, le=100)
    customer_reach_score: float = Field(ge=0, le=100)
    automation_score: float = Field(ge=0, le=100)
    margin_score: float = Field(ge=0, le=100)
    build_speed_score: float = Field(ge=0, le=100)
    differentiation_score: float = Field(ge=0, le=100)
    safety_score: float = Field(ge=0, le=100)
    evidence_quality_score: float = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=100)
    final_score: float = Field(ge=0, le=100)
    per_criterion: dict[str, CriterionScore] = Field(default_factory=dict)
    independent_evidence_count: int = Field(default=0, ge=0)
    unverified_assumptions_count: int = Field(default=0, ge=0)
    assumptions: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    approval_reason: str | None = None
    rejection_reason: str | None = None
    decision: Decision = Decision.deferred
    model_or_method: str | None = None
    skeptic_critique: str | None = None
    risks: list[RiskItem] = Field(default_factory=list)
    estimates: Estimates = Field(default_factory=Estimates)
    experiment: Experiment | None = None
    created_at: str = Field(default_factory=_now)
