"""Multi-Agent Ideation Arena (macro-intervención 024).

Permite que WAWA genere ideas internas y que el propietario importe ideas
provenientes de agentes externos (GPT, Grok, Gemini, etc.). El sistema las
normaliza, deduplica, filtra, enfrenta en torneo y selecciona las mejores
hasta un máximo de 5 supervivientes y 3 candidatas para investigación.

Todas las ideas importadas son HIPÓTESIS. La coincidencia entre modelos
(MULTI_MODEL_CONVERGENCE) NUNCA incrementa proven_demand ni evidence_score.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IdeaStatus(str, Enum):
    GENERATED_HYPOTHESIS = "GENERATED_HYPOTHESIS"  # WAWA internal
    IMPORTED_HYPOTHESIS = "IMPORTED_HYPOTHESIS"    # External model
    NORMALIZED = "NORMALIZED"
    DEDUPLICATED = "DEDUPLICATED"
    MERGED = "MERGED"
    COMMODITY_BLOCKED = "COMMODITY_BLOCKED"
    QUALITY_GATE_PASSED = "QUALITY_GATE_PASSED"
    QUALITY_GATE_FAILED = "QUALITY_GATE_FAILED"
    TOURNAMENT_SURVIVOR = "TOURNAMENT_SURVIVOR"
    TOURNAMENT_ELIMINATED = "TOURNAMENT_ELIMINATED"
    SELECTED_FOR_REVIEW = "SELECTED_FOR_REVIEW"
    APPROVED_FOR_RESEARCH = "APPROVED_FOR_RESEARCH"
    REJECTED = "REJECTED"


class ArenaPhase(str, Enum):
    IDLE = "IDLE"
    GENERATING = "GENERATING"
    AWAITING_EXTERNAL = "AWAITING_EXTERNAL"
    IMPORTING = "IMPORTING"
    NORMALIZING = "NORMALIZING"
    FILTERING = "FILTERING"
    TOURNAMENT = "TOURNAMENT"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    MISSIONS_CREATED = "MISSIONS_CREATED"


class ExternalProvider(str, Enum):
    WAWA = "wawa"
    GPT = "gpt"
    GROK = "grok"
    GEMINI = "gemini"
    OTHER = "other"


def new_id() -> str:
    return uuid.uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ArenaIdeaBrief(BaseModel):
    """Brief normalizado de una idea. Contrato mínimo para ser válida."""
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=5, max_length=300)
    problem: str = Field(min_length=10, max_length=2_000)
    buyer: str = Field(min_length=5, max_length=500)
    offer: str = Field(min_length=5, max_length=1_000)
    channel: str = Field(default="", max_length=500)
    price_hypothesis: str = Field(default="", max_length=200)
    differentiation: str = Field(default="", max_length=1_000)


class ArenaIdea(BaseModel):
    """Una idea dentro de la arena, proveniente de WAWA o de un agente externo."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=new_id)
    batch_id: str = Field(default="")
    provider: str = Field(default=ExternalProvider.WAWA.value, max_length=100)
    brief: ArenaIdeaBrief
    status: str = Field(default=IdeaStatus.GENERATED_HYPOTHESIS.value, max_length=50)
    structural_score: float = Field(default=0.0, ge=0, le=100)
    structural_tags: list[str] = Field(default_factory=list)
    commodity_test: str = Field(default="PENDING", max_length=30)
    quality_gate: str = Field(default="PENDING", max_length=30)
    fingerprint: str = Field(default="", max_length=64)
    merged_from: list[str] = Field(default_factory=list)
    convergence_count: int = Field(default=0, ge=0)
    raw_source: str | None = Field(default=None, max_length=200_000)
    file_hash: str | None = Field(default=None, max_length=64)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class ArenaBatch(BaseModel):
    """Un lote de ideas importadas de un agente externo."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=new_id)
    provider: str = Field(default=ExternalProvider.GPT.value, max_length=100)
    filename: str = Field(default="", max_length=300)
    idea_count: int = Field(default=0, ge=0)
    accepted_count: int = Field(default=0, ge=0)
    rejected_count: int = Field(default=0, ge=0)
    excess_count: int = Field(default=0, ge=0)
    file_hash: str | None = Field(default=None, max_length=64)
    error: str | None = Field(default=None, max_length=5_000)
    created_at: str = Field(default_factory=_now)


class ArenaPrompt(BaseModel):
    """El prompt normalizado que se copia para agentes externos."""
    model_config = ConfigDict(extra="forbid")
    batch_id: str = Field(default_factory=new_id)
    content: str = Field(default="")
    generator_label: str = Field(default="EXTERNAL_MODEL")
    created_at: str = Field(default_factory=_now)


class ArenaState(BaseModel):
    """Estado persistido de la arena para un ciclo de generación."""
    model_config = ConfigDict(extra="forbid")
    phase: str = Field(default=ArenaPhase.IDLE.value, max_length=30)
    generation_batch_id: str = Field(default="")
    total_ideas: int = Field(default=0, ge=0)
    wawa_count: int = Field(default=0, ge=0)
    external_count: int = Field(default=0, ge=0)
    duplicates_removed: int = Field(default=0, ge=0)
    commodities_removed: int = Field(default=0, ge=0)
    quality_failed: int = Field(default=0, ge=0)
    tournament_survivors: int = Field(default=0, ge=0)
    selected_for_review: int = Field(default=0, ge=0)
    approved_for_research: int = Field(default=0, ge=0)
    events: list[dict[str, Any]] = Field(default_factory=list)
    started_at: str | None = None
    last_event_at: str | None = None
    updated_at: str = Field(default_factory=_now)


class ArenaEvent(BaseModel):
    """Un evento del log vivo de la arena."""
    model_config = ConfigDict(extra="forbid")
    timestamp: str = Field(default_factory=_now)
    agent: str = Field(max_length=30)
    message: str = Field(max_length=500)
    kind: str = Field(default="info", max_length=30)  # info, warning, error, intervention


class ProviderStatus(BaseModel):
    """Estado de conexión de un proveedor externo."""
    model_config = ConfigDict(extra="forbid")
    name: str
    enabled: bool = False
    connection_status: str = Field(default="NO_KEY", max_length=30)
    requested_model: str = Field(default="", max_length=100)
    actual_model: str = Field(default="", max_length=100)
    call_limit: int = Field(default=0, ge=0)
    cost_limit: float = Field(default=0.0, ge=0)
    calls_today: int = Field(default=0, ge=0)
    cost_today: float = Field(default=0.0, ge=0)
    last_call_at: str | None = None
    last_error: str | None = None
    execution_mode: str = Field(default="MANUAL_IMPORT", max_length=30)


class ArenaGenerateIn(BaseModel):
    """Payload para generar 5 ideas WAWA."""
    model_config = ConfigDict(extra="forbid")
    count: int = Field(default=5, ge=1, le=20)


class ArenaImportIn(BaseModel):
    """Payload para importar un lote de ideas de un agente externo."""
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(min_length=1, max_length=100)
    filename: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=200_000)
    max_ideas: int = Field(default=5, ge=1, le=20)


class ArenaApproveIn(BaseModel):
    """Payload para aprobar ideas para investigación."""
    model_config = ConfigDict(extra="forbid")
    idea_ids: list[str] = Field(min_length=1, max_length=3)
