"""Base común de agentes.

Un agente:
1. Recibe un ``AgentContext`` con los datos guardados.
2. Usa ``ProviderManager`` para generar contenido (o lógica determinista).
3. Devuelve un ``AgentResult`` estructurado. El workflow persiste evidencias,
   decisiones y costes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.evidence import Competitor, Evidence
from app.models.opportunity import Opportunity
from app.providers.manager import ProviderCall, ProviderManager


class AgentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: str
    output: dict[str, Any] = Field(default_factory=dict)
    evidence_used: list[str] = Field(default_factory=list)
    decision: str | None = None
    model_or_method: str
    estimated_cost: float = 0.0
    cost_method: str = "zero (offline)"
    errors: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


@dataclass
class AgentContext:
    """Todo lo que un agente necesita saber, tomado de datos persistidos.

    ``repos`` es un namespace con los repositorios necesarios
    (evidence, competitors, opportunities) para que los agentes puedan
    persistir sus hallazgos directamente.
    """

    opportunity: Opportunity
    evidences: list[Evidence] = field(default_factory=list)
    competitors: list[Competitor] = field(default_factory=list)
    previous: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)
    repos: Any | None = None


class BaseAgent(ABC):
    name: str = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.log = get_logger(f"agent.{self.name}")

    @abstractmethod
    def run(self, ctx: AgentContext, providers: ProviderManager) -> AgentResult:
        """Ejecuta el agente. No debe lanzar excepciones no controladas."""

    # ------------------------------------------------------------------
    def _call(
        self,
        providers: ProviderManager,
        *,
        prompt: str,
        system: str | None = None,
        task: str | None = None,
        output_schema: dict[str, Any] | None = None,
        opportunity_id: str | None = None,
    ) -> ProviderCall:
        return providers.generate(
            prompt,
            system=system,
            task=task,
            output_schema=output_schema,
            opportunity_id=opportunity_id,
            action=f"agent:{self.name}",
        )

    def _result(
        self,
        *,
        output: dict[str, Any],
        call: ProviderCall | None = None,
        decision: str | None = None,
        evidence_used: list[str] | None = None,
        assumptions: list[str] | None = None,
        method: str | None = None,
    ) -> AgentResult:
        if call is not None:
            method = f"{call.provider}{' + fallback a mock' if call.fallback_used else ''}"
        return AgentResult(
            agent=self.name,
            output=output,
            evidence_used=evidence_used or [],
            decision=decision,
            model_or_method=method or "determinista",
            estimated_cost=call.response.cost_estimate_usd if call else 0.0,
            cost_method=call.response.cost_method if call else "zero (offline)",
            errors=list(call.errors) if call else [],
            assumptions=assumptions or [],
        )
