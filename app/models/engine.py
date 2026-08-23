"""Modelos del motor de operación: transiciones de modo, eventos y estado.

Regla de oro: **los cambios de modo y de estado del motor son auditables**
(tablas append-only). Las decisiones económicas importantes están controladas
por reglas deterministas, no por un LLM.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EngineState, OperatingMode


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ModeTransition(BaseModel):
    """Registro append-only de un cambio de modo de operación."""

    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    timestamp: str = Field(default_factory=_now)
    from_mode: str
    to_mode: str
    reason: str | None = Field(default=None, max_length=2_000)
    actor: str = Field(default="system", max_length=100)
    evidence_used: list[str] = Field(default_factory=list)
    budget_consumed_usd: float = Field(default=0.0, ge=0)
    revenue_usd: float = Field(default=0.0, ge=0)
    decision: str | None = None
    rule: str | None = Field(default=None, max_length=500)


class EngineEvent(BaseModel):
    """Evento de actividad para el timeline en vivo del panel."""

    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    timestamp: str = Field(default_factory=_now)
    event_type: str = Field(max_length=100)
    summary: str = Field(max_length=2_000)
    opportunity_id: str | None = None
    engine_state: str | None = None
    mode: str | None = None
    cost_usd: float = Field(default=0.0, ge=0)
    confidence: float | None = Field(default=None, ge=0, le=100)


class EngineSnapshot(BaseModel):
    """Estado operativo actual del motor (para el panel y la API)."""

    model_config = ConfigDict(extra="forbid")

    mode: OperatingMode = OperatingMode.development_and_review
    engine_state: EngineState = EngineState.researching
    current_task: str | None = None
    task_started_at: str | None = None
    last_result: str | None = None
    next_action: str | None = None
    heartbeat_at: str | None = None
    activated_at: str | None = None
    updated_at: str = Field(default_factory=_now)
