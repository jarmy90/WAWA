"""Políticas de routing por tarea (iteración 008).

Cada tarea define de forma determinista: proveedor principal, modelo
principal, fallbacks, coste máximo, latencia máxima, requisitos de JSON,
requisitos de contexto, si se permiten modelos gratuitos aleatorios, si se
exige modelo fijo y si está permitido continuar sin respuesta.

Política inicial:
- external_committee  -> OpenRouter con modelo FIJO (nunca sustituido en
  silencio por OmniRoute); OmniRoute es un segundo revisor OPCIONAL.
- discovery            -> offline/mock hasta superar el A/B (OmniRoute
  desactivado para Discovery general).
- classification / clustering / evidence_extraction / solution_generation /
  skeptic_review / summarization -> mock en desarrollo; gemini opcional.
- manual_import        -> disponible siempre (vía humana/Freebuff).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TASKS = (
    "classification",
    "clustering",
    "discovery",
    "evidence_extraction",
    "solution_generation",
    "skeptic_review",
    "external_committee",
    "summarization",
)


@dataclass(frozen=True)
class TaskRoutingPolicy:
    task: str
    provider: str = "mock"  # principal
    model: str | None = None  # None = default del proveedor
    fallbacks: tuple[str, ...] = ()
    fallback_models: dict[str, str] = field(default_factory=dict)
    max_cost_usd: float | None = None
    max_latency_ms: int | None = None
    requires_json: bool = False
    min_context_tokens: int = 0
    allow_free_random: bool = False  # modelos gratuitos aleatorios
    require_fixed_model: bool = False  # el modelo NO puede variar
    allow_continue_without_response: bool = True  # ausencia neutral
    notes: str = ""


TASK_POLICIES: dict[str, TaskRoutingPolicy] = {
    "external_committee": TaskRoutingPolicy(
        task="external_committee",
        provider="openrouter",
        fallbacks=("manual_import",),
        max_cost_usd=0.05,
        requires_json=False,
        require_fixed_model=True,
        allow_continue_without_response=True,
        notes="Modelo FIJO del comité (OPENROUTER_REVIEW_MODEL). OmniRoute SOLO como segundo revisor opcional; nunca sustituye el fijo en silencio.",
    ),
    "discovery": TaskRoutingPolicy(
        task="discovery",
        provider="mock",
        fallbacks=(),
        max_cost_usd=0.0,
        allow_continue_without_response=True,
        notes="OmniRoute desactivado para Discovery general hasta superar el benchmark A/B (iteración 008).",
    ),
    "classification": TaskRoutingPolicy(
        task="classification", provider="mock", fallbacks=("gemini",), max_cost_usd=0.0, requires_json=True,
    ),
    "clustering": TaskRoutingPolicy(
        task="clustering", provider="mock", fallbacks=("gemini",), max_cost_usd=0.0,
    ),
    "evidence_extraction": TaskRoutingPolicy(
        task="evidence_extraction", provider="mock", fallbacks=("gemini",), max_cost_usd=0.0, requires_json=True,
        notes="La extracción NUNCA marca evidencia como verificada sin URL+fecha+fragmento.",
    ),
    "solution_generation": TaskRoutingPolicy(
        task="solution_generation", provider="mock", fallbacks=("gemini",), max_cost_usd=0.0,
    ),
    "skeptic_review": TaskRoutingPolicy(
        task="skeptic_review", provider="mock", fallbacks=("gemini",), max_cost_usd=0.0,
        allow_continue_without_response=True,
    ),
    "summarization": TaskRoutingPolicy(
        task="summarization", provider="mock", fallbacks=("gemini",), max_cost_usd=0.0,
    ),
}


def resolve_policy(task: str) -> TaskRoutingPolicy:
    return TASK_POLICIES.get(task, TASK_POLICIES["classification"])


def providers_for_task(task: str, settings: Any) -> list[dict[str, Any]]:
    """Orden de intentos para una tarea: [(provider, model, policy), ...].

    OmniRoute solo entra si está explícitamente habilitado Y la política lo
    permite (external_committee como segundo revisor opcional; discovery NO).
    """
    policy = resolve_policy(task)
    attempts: list[dict[str, Any]] = [{"provider": policy.provider, "model": policy.model, "policy": policy}]
    for fb in policy.fallbacks:
        attempts.append({"provider": fb, "model": policy.fallback_models.get(fb), "policy": policy})
    # OmniRoute: solo comité y solo si OMNIROUTE_ENABLED=true (nunca silencioso).
    if task == "external_committee" and getattr(settings, "omniroute_enabled", False):
        attempts.append({
            "provider": "omniroute",
            "model": getattr(settings, "omniroute_review_model", "auto"),
            "policy": policy,
            "role": "second_optional_reviewer",
        })
    return attempts
