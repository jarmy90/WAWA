"""Registro por llamada de proveedor LLM (append-only).

La honestidad del coste es obligatoria: una estimación nunca se presenta como
coste real. ``reported_cost`` es ``None`` salvo que el proveedor devuelva un
coste explícito; ``billing_verified`` solo puede ser ``true`` tras una
reconciliación con el panel de facturación (en esta fase siempre ``false``).
Un coste desconocido nunca se convierte en cero.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CostSource(str, Enum):
    provider_response = "PROVIDER_RESPONSE"
    local_estimate = "LOCAL_ESTIMATE"
    billing_reconciliation = "BILLING_RECONCILIATION"
    free_tier = "FREE_TIER"
    unknown = "UNKNOWN"


class LLMCallRecord(BaseModel):
    """Una llamada a un proveedor LLM, con su rastro de coste y uso."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    provider: str = Field(max_length=100)
    action: str = Field(default="llm_call", max_length=100)
    opportunity_id: str | None = Field(default=None, max_length=64)
    requested_model: str = Field(default="", max_length=200)
    actual_model: str | None = Field(default=None, max_length=200)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    reported_cost: float | None = Field(default=None, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    cost_source: str = CostSource.unknown.value
    billing_verified: bool = False
    latency_ms: int | None = Field(default=None, ge=0)
    retry_count: int = Field(default=0, ge=0)
    fallback_used: bool = False
    response_status: str = Field(default="ok", max_length=50)
    notes: str | None = Field(default=None, max_length=2_000)
    # --- Routing y procedencia (iteración 008) --------------------------------
    actual_provider: str | None = Field(default=None, max_length=100)
    routing_strategy: str | None = Field(default=None, max_length=100)
    fallback_reason: str | None = Field(default=None, max_length=500)
    response_is_external: bool = True  # ¿la respuesta vino de un servicio externo real?
    response_is_synthetic: bool = False  # ¿fue generada por un simulador/mock?
    quota_state: str | None = Field(default=None, max_length=100)
    created_at: str = Field(default_factory=_now)
