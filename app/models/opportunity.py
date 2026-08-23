"""Modelo de oportunidad de negocio."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import OpportunityStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Opportunity(BaseModel):
    """Una oportunidad concreta derivada de un problema de mercado."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    title: str = Field(min_length=3, max_length=300)
    problem: str = Field(min_length=10, max_length=20_000)
    proposed_solution: str | None = Field(default=None, max_length=20_000)
    target_customer: str | None = Field(default=None, max_length=2_000)
    sector: str | None = Field(default=None, max_length=200)
    status: OpportunityStatus = OpportunityStatus.draft
    source: str = Field(default="manual", max_length=100)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)

    @field_validator("title", "problem", "proposed_solution", "target_customer", "sector", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class OpportunityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=300)
    problem: str = Field(min_length=10, max_length=20_000)
    proposed_solution: str | None = Field(default=None, max_length=20_000)
    target_customer: str | None = Field(default=None, max_length=2_000)
    sector: str | None = Field(default=None, max_length=200)
    source: str = Field(default="manual", max_length=100)


class OpportunityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=3, max_length=300)
    problem: str | None = Field(default=None, min_length=10, max_length=20_000)
    proposed_solution: str | None = Field(default=None, max_length=20_000)
    target_customer: str | None = Field(default=None, max_length=2_000)
    sector: str | None = Field(default=None, max_length=200)


class ProblemSeed(BaseModel):
    """Entrada del Scout: un problema o necesidad descrita en lenguaje natural."""

    model_config = ConfigDict(extra="forbid")

    problem: str = Field(min_length=10, max_length=20_000)
    sector_hint: str | None = Field(default=None, max_length=200)
    source: str = Field(default="manual", max_length=100)
