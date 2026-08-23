"""Builder — estima complejidad técnica, tiempo de desarrollo, dependencias
y grado de automatización.

Salidas marcadas como estimaciones (heurísticas de sector).
"""
from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.providers.manager import ProviderManager


class BuilderAgent(BaseAgent):
    name = "builder"

    def run(self, ctx: AgentContext, providers: ProviderManager) -> AgentResult:
        opportunity = ctx.opportunity
        prompt = (
            f"OPORTUNIDAD: {opportunity.title}\n"
            f"PROBLEMA: {opportunity.problem}\n"
            f"SOLUCIÓN: {opportunity.proposed_solution}\n"
            f"SECTOR: {opportunity.sector}\n"
        )
        call = self._call(
            providers,
            prompt=prompt,
            system=opportunity.problem,
            task="builder",
            output_schema={"estimates": "dict", "assumptions": "list"},
            opportunity_id=opportunity.id,
        )
        structured = call.response.structured or {}
        estimates = structured.get("estimates") or {}
        assumptions = structured.get("assumptions") or []
        return self._result(
            output={"estimates": estimates},
            call=call,
            assumptions=assumptions,
        )
