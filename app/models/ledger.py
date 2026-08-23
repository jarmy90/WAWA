"""Modelo contable: asientos del ledger (append-only) y contratos de la API.

Reglas:
- Importes SIEMPRE en Decimal (nunca float); redondeo a 2 decimales
  (ROUND_HALF_UP). Importes negativos REJECTED en validación: la dirección
  debit/credit determina el efecto.
- El saldo se deriva de los movimientos; nunca se guarda un saldo editable.
- Los movimientos confirmados no se editan ni se borran: se corrigen con una
  entrada de reversión vinculada (reversed_entry_id).
- Idempotencia: idempotency_key única; reintentar devuelve el original.
- Moneda única (base_currency); otra moneda => rechazo explícito.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import LedgerDirection, LedgerEntryType, LedgerStatus

ALLOWED_ENTRY_TYPES = {t.value for t in LedgerEntryType}
ALLOWED_STATUSES = {s.value for s in LedgerStatus}
ALLOWED_DIRECTIONS = {d.value for d in LedgerDirection}
ALLOWED_INCOME_SOURCES = {
    "simulated_customer_payment",
    "imported_result",
    "manual_simulation",
    "experiment_outcome",
}

# Tipos que aumentan saldo (credit) o lo reducen (debit).
CREDIT_TYPES = {LedgerEntryType.initial_capital.value, LedgerEntryType.simulated_income.value, LedgerEntryType.refund.value}
DEBIT_TYPES = {
    LedgerEntryType.simulated_expense.value,
    LedgerEntryType.api_cost.value,
    LedgerEntryType.infrastructure_cost.value,
    LedgerEntryType.experiment_cost.value,
    LedgerEntryType.manual_adjustment.value,
}
# Los REVERSAL adoptan la dirección opuesta a la entrada que revierten.


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def money(value) -> Decimal:
    """Convierte a Decimal redondeado a 2 decimales (ROUND_HALF_UP)."""
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class LedgerEntry(BaseModel):
    """Asiento contable inmutable (append-only)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    entry_type: str = LedgerEntryType.simulated_expense.value
    direction: str = LedgerDirection.debit.value
    amount: Decimal = Field(ge=0)
    currency: str = "USD"
    status: str = LedgerStatus.pending.value
    source_type: str | None = Field(default=None, max_length=200)
    source_id: str | None = Field(default=None, max_length=200)
    opportunity_id: str | None = Field(default=None, max_length=64)
    experiment_id: str | None = Field(default=None, max_length=64)
    description: str = Field(min_length=3, max_length=2_000)
    evidence_reference: str | None = Field(default=None, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=200)
    operating_mode: str = Field(default="development_and_review", max_length=100)
    created_by: str = Field(default="system", max_length=100)
    created_at: str = Field(default_factory=_now)
    confirmed_at: str | None = None
    reversed_entry_id: str | None = Field(default=None, max_length=64)
    metadata: dict = Field(default_factory=dict)

    @field_validator("entry_type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        if value not in ALLOWED_ENTRY_TYPES:
            raise ValueError(f"Tipo de asiento no permitido: {value}")
        return value

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: str) -> str:
        if value not in ALLOWED_STATUSES:
            raise ValueError(f"Estado no permitido: {value}")
        return value

    @field_validator("direction")
    @classmethod
    def _check_direction(cls, value: str) -> str:
        if value not in ALLOWED_DIRECTIONS:
            raise ValueError(f"Dirección no permitida: {value}")
        return value

    @field_validator("amount", mode="before")
    @classmethod
    def _money(cls, value) -> Decimal:
        return money(value)

    @model_validator(mode="after")
    def _no_negatives(self) -> "LedgerEntry":
        if self.amount < 0:
            raise ValueError("Los importes negativos no están permitidos: usa dirección debit/credit.")
        return self

    @field_validator("metadata")
    @classmethod
    def _metadata_size(cls, value: dict) -> dict:
        serialized = json.dumps(value, ensure_ascii=False)
        if len(serialized) > 4_000:
            raise ValueError("metadata demasiado grande (máx. 4 KB)")
        return value


class SimulationStartIn(BaseModel):
    """Inicio de una simulación económica (nunca crea dinero real)."""

    model_config = ConfigDict(extra="forbid")

    initial_capital: Decimal = Field(gt=0)
    currency: str = "USD"
    maximum_daily_spend: Decimal | None = Field(default=None, gt=0)
    simulation_name: str = Field(default="Simulación económica", min_length=3, max_length=200)
    notes: str | None = Field(default=None, max_length=2_000)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)

    @field_validator("initial_capital", mode="before")
    @classmethod
    def _money(cls, value) -> Decimal:
        return money(value)


class IncomeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0)
    currency: str = "USD"
    source_type: str
    description: str = Field(min_length=3, max_length=2_000)
    opportunity_id: str | None = Field(default=None, max_length=64)
    experiment_id: str | None = Field(default=None, max_length=64)
    evidence_reference: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)

    @field_validator("amount", mode="before")
    @classmethod
    def _money(cls, value) -> Decimal:
        return money(value)

    @field_validator("source_type")
    @classmethod
    def _source(cls, value: str) -> str:
        if value not in ALLOWED_INCOME_SOURCES:
            raise ValueError(f"source_type no permitido: {value}")
        return value


class ExpenseRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0)
    currency: str = "USD"
    entry_type: str = LedgerEntryType.simulated_expense.value
    description: str = Field(min_length=3, max_length=2_000)
    opportunity_id: str | None = Field(default=None, max_length=64)
    experiment_id: str | None = Field(default=None, max_length=64)
    evidence_reference: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)

    @field_validator("amount", mode="before")
    @classmethod
    def _money(cls, value) -> Decimal:
        return money(value)

    @field_validator("entry_type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        if value not in DEBIT_TYPES:
            raise ValueError(f"entry_type debe ser un gasto ({', '.join(sorted(DEBIT_TYPES))})")
        return value


class ReverseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=2_000)
    actor: str = Field(default="human", max_length=100)
