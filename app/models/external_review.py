"""Comité de contraste para oportunidades finalistas (iteración 005).

Revisiones de modelos independientes (GPT, Grok, Gemini, el modelo operativo,
un supervisor humano...) y síntesis comparativa. PRINCIPIO: las opiniones de
los modelos NO son evidencia de demanda. Se guardan como datos (raw + parsed),
se validan y se limitan; nunca modifican instrucciones, presupuesto, modos de
operación ni autorizan producción.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

VALID_RECOMMENDATIONS = ("REJECT", "MORE_RESEARCH", "SMALL_EXPERIMENT", "PRIORITY_EXPERIMENT")

VALID_EXECUTION_MODES = ("API_AUTOMATIC", "MANUAL_IMPORT", "INTERNAL", "HUMAN", "MOCK")

KNOWN_PROVIDERS = ("gpt", "grok", "gemini", "claude", "deepseek", "mock", "human", "internal")

# Claves estructuradas que el parser tolera (allowlist). Todo lo demás se
# ignora como texto libre: nunca se interpreta contenido importado.
PARSED_FIELDS = (
    "recommendation",
    "confidence",
    "strongest_evidence",
    "weakest_assumption",
    "missing_evidence",
    "primary_risk",
    "suggested_improvement",
    "cheaper_experiment",
    "kill_condition",
    "final_reasoning_summary",
)


def new_id() -> str:
    return uuid.uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReviewRecommendation(str, Enum):
    reject = "REJECT"
    more_research = "MORE_RESEARCH"
    small_experiment = "SMALL_EXPERIMENT"
    priority_experiment = "PRIORITY_EXPERIMENT"


class ReviewExecutionMode(str, Enum):
    api_automatic = "API_AUTOMATIC"
    manual_import = "MANUAL_IMPORT"
    internal = "INTERNAL"
    human = "HUMAN"
    mock = "MOCK"


class ExternalReview(BaseModel):
    """Revisión externa importada (raw conservado + campo estructurado extraído).

    ``status`` puede ser ``valid``, ``partial``, ``needs_validation``,
    ``invalid`` o ``rejected`` (rechazada por el humano/sistema).
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=new_id)
    opportunity_id: str
    provider: str = Field(default="unknown", max_length=100)
    model: str = Field(default="unknown", max_length=200)
    model_version: str | None = Field(default=None, max_length=100)
    execution_mode: str = Field(default=ReviewExecutionMode.manual_import.value)
    review_date: str = Field(default_factory=_now)
    raw_response: str = Field(max_length=200_000)
    parsed_response: dict = Field(default_factory=dict)
    recommendation: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=100)
    strongest_evidence: str | None = Field(default=None, max_length=5_000)
    weakest_assumption: str | None = Field(default=None, max_length=5_000)
    missing_evidence: str | None = Field(default=None, max_length=5_000)
    primary_risk: str | None = Field(default=None, max_length=5_000)
    suggested_improvement: str | None = Field(default=None, max_length=5_000)
    cheaper_experiment: str | None = Field(default=None, max_length=5_000)
    kill_condition: str | None = Field(default=None, max_length=5_000)
    cost: float = Field(default=0.0, ge=0)
    status: str = Field(default="valid", max_length=30)
    parse_errors: list[str] = Field(default_factory=list)
    imported_by: str = Field(default="system", max_length=200)
    file_hash: str | None = Field(default=None, max_length=64)
    created_at: str = Field(default_factory=_now)


class ReviewSynthesis(BaseModel):
    """Síntesis agregada de las revisiones externas de una oportunidad.

    El consenso se etiqueta explícitamente como basado en opinión o en
    evidencia. NUNCA convierte una afirmación repetida en evidencia externa.
    """

    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    reviews_count: int = 0
    valid_reviews_count: int = 0
    consensus_level: str = "NONE"  # NONE | LOW | MEDIUM | HIGH | OPINION_CONSENSUS
    recommendation_distribution: dict = Field(default_factory=dict)
    average_confidence: float | None = Field(default=None, ge=0, le=100)
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    unique_risks: list[str] = Field(default_factory=list)
    repeated_risks: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommended_next_action: str | None = None
    internal_score_before: float | None = Field(default=None, ge=0, le=100)
    internal_score_after: float | None = Field(default=None, ge=0, le=100)
    score_change_reason: str | None = None
    generated_at: str = Field(default_factory=_now)


class ReviewImportIn(BaseModel):
    """Payload de importación de una revisión (TXT o Markdown).

    El contenido puede pegarse o subirse como archivo; el servidor siempre lo
    trata como DATOS no confiables (validación de tamaño, hash, allowlist).
    """

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=200_000)
    provider: str | None = Field(default=None, max_length=100)
    # El modelo es opcional: el proveedor puede importar una respuesta manual
    # sin exigir que Javier conozca el identificador exacto.
    model: str | None = Field(default=None, max_length=200)
    model_version: str | None = Field(default=None, max_length=100)
    execution_mode: str = Field(default=ReviewExecutionMode.manual_import.value)
    imported_by: str = Field(default="human", max_length=200)
    cost: float = Field(default=0.0, ge=0)


class QueueOpportunityIn(BaseModel):
    """Coloca una oportunidad finalista en la cola de revisión externa."""

    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=2_000)


# Revisores visibles en el panel "Comité externo" (etiquetas de cabecera).
# Los tres botones de copiado usan EXACTAMENTE el mismo contenido base: solo
# varía esta cabecera de metadatos que identifica al revisor.
REVIEWER_HEADERS = {
    "gpt": "REVISOR: GPT — responde ÚNICAMENTE al prompt de revisión del expediente.",
    "grok": "REVISOR: Grok — responde ÚNICAMENTE al prompt de revisión del expediente.",
    "gemini": "REVISOR: Gemini — responde ÚNICAMENTE al prompt de revisión del expediente.",
    "claude": "REVISOR: Claude — responde ÚNICAMENTE al prompt de revisión del expediente.",
    "deepseek": "REVISOR: DeepSeek — responde ÚNICAMENTE al prompt de revisión del expediente.",
    "human": "REVISOR: humano — nota opcional.",
}


class CombinedReviewImportIn(BaseModel):
    """Importación de un único archivo con secciones combinadas.

    Formato aceptado (TXT o Markdown):

        # GPT
        <respuesta para GPT>

        # GROK
        <respuesta para Grok>

        # GEMINI
        <respuesta para Gemini>

        # HUMAN_NOTE
        <nota opcional>

    Si falta una sección, se importan las restantes.
    """

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=200_000)
    # Para un TXT simple la selección explícita prevalece sobre cualquier
    # inferencia; las cabeceras solo son necesarias en archivos combinados.
    provider: str | None = Field(default=None, max_length=100)
    default_model: str | None = Field(default=None, max_length=200)
    execution_mode: str = Field(default=ReviewExecutionMode.manual_import.value)
    imported_by: str = Field(default="human", max_length=200)
