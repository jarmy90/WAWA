"""Evidencias y competidores.

Regla de oro del sistema: **nunca se inventa evidencia**. Cada entrada
lleva fiabilidad, verificación y método de captura. Lo que no está
verificado se marca como tal y reduce la confianza del resultado.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import EvidenceType

ALLOWED_EVIDENCE_TYPES = {t.value for t in EvidenceType}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    opportunity_id: str
    evidence_type: str = EvidenceType.other.value
    source_name: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=2_000)
    captured_at: str = Field(default_factory=_now)
    summary: str = Field(min_length=3, max_length=5_000)
    raw_excerpt: str | None = Field(default=None, max_length=20_000)
    reliability_score: float = Field(default=0.5, ge=0.0, le=1.0)
    independence_group: str | None = Field(default=None, max_length=200)
    verified: bool = False
    verification_notes: str | None = Field(default=None, max_length=2_000)
    collected_by: str = Field(default="system", max_length=100)
    method: str = Field(default="mock", max_length=100)

    @field_validator("evidence_type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        if value not in ALLOWED_EVIDENCE_TYPES:
            raise ValueError(f"Tipo de evidencia no válido: {value}")
        return value

    @field_validator("source_url")
    @classmethod
    def _sanitize_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 2_000:
            raise ValueError("URL demasiado larga")
        if value.lower().startswith(("javascript:", "data:", "file:")):
            raise ValueError("Esquema de URL no permitido")
        return value


class EvidenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_type: str = EvidenceType.other.value
    source_name: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=2_000)
    summary: str = Field(min_length=3, max_length=5_000)
    raw_excerpt: str | None = Field(default=None, max_length=20_000)
    reliability_score: float = Field(default=0.5, ge=0.0, le=1.0)
    independence_group: str | None = Field(default=None, max_length=200)
    verified: bool = False
    verification_notes: str | None = Field(default=None, max_length=2_000)
    method: str = Field(default="import", max_length=100)


class Competitor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    opportunity_id: str
    name: str = Field(min_length=1, max_length=300)
    url: str | None = Field(default=None, max_length=2_000)
    offer: str | None = Field(default=None, max_length=5_000)
    observed_price: float | None = Field(default=None, ge=0)
    strengths: str | None = Field(default=None, max_length=2_000)
    weaknesses: str | None = Field(default=None, max_length=2_000)
    evidence_id: str | None = Field(default=None, max_length=64)


class CompetitorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=300)
    url: str | None = Field(default=None, max_length=2_000)
    offer: str | None = Field(default=None, max_length=5_000)
    observed_price: float | None = Field(default=None, ge=0)
    strengths: str | None = Field(default=None, max_length=2_000)
    weaknesses: str | None = Field(default=None, max_length=2_000)
    evidence_id: str | None = Field(default=None, max_length=64)
