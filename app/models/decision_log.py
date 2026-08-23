"""Registro de decisiones (auditoría append-only).

Cada paso de agente, cada decisión humana y cada fallo de proveedor se
registra aquí con su coste estimado y método. Nunca se borra.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DecisionLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    timestamp: str = Field(default_factory=_now)
    agent: str = Field(max_length=100)
    opportunity_id: str | None = None
    input_summary: str | None = Field(default=None, max_length=5_000)
    output_summary: str | None = Field(default=None, max_length=10_000)
    evidence_used: list[str] = Field(default_factory=list)
    decision: str | None = Field(default=None, max_length=100)
    model_or_method: str | None = Field(default=None, max_length=500)
    estimated_cost: float = Field(default=0.0, ge=0)
    cost_method: str | None = Field(default=None, max_length=100)
    errors: list[str] = Field(default_factory=list)


class CostRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    timestamp: str = Field(default_factory=_now)
    action: str = Field(max_length=200)
    opportunity_id: str | None = None
    provider: str | None = Field(default=None, max_length=200)
    estimated_cost_usd: float = Field(default=0.0, ge=0)
    cost_method: str | None = None
    simulation: bool = False
    blocked: bool = False
