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
        context = " ".join(
            str(value or "")
            for value in (opportunity.title, opportunity.problem, opportunity.proposed_solution, opportunity.sector)
        ).lower()
        if "mql5" not in context and "metatrader" not in context and "trading" not in context:
            estimates = {
                k: v for k, v in estimates.items()
                if "mql5" not in str(v).lower() and "metatrader" not in str(v).lower() and "trading" not in str(v).lower()
            }
            assumptions = [
                a for a in assumptions
                if not any(marker in str(a).lower() for marker in ("mql5", "metatrader", "trading"))
            ]
        return self._result(
            output={"estimates": estimates},
            call=call,
            assumptions=assumptions,
        )
