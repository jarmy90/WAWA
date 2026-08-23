"""Scout — descubre problemas reales y propone oportunidades iniciales.

Transforma una descripción de problema en borradores de oportunidad. No
puntúa ni decide: solo genera candidatos para el resto del pipeline.
"""
from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.providers.manager import ProviderManager


class ScoutAgent(BaseAgent):
    name = "scout"

    def run(self, ctx: AgentContext, providers: ProviderManager) -> AgentResult:
        problem = ctx.extras.get("problem", ctx.opportunity.problem)
        sector_hint = ctx.extras.get("sector_hint") or ""
        prompt = f"PROBLEMA:\n{problem}\n\nSECTOR_HINT:\n{sector_hint}"
        call = self._call(
            providers,
            prompt=prompt,
            system=problem,
            task="scout",
            output_schema={"opportunities": "list"},
        )
        structured = call.response.structured or {}
        opportunities = structured.get("opportunities") or []
        return self._result(
            output={"opportunities": opportunities, "source": ctx.extras.get("source", "scout")},
            call=call,
            assumptions=["Las oportunidades generadas son hipótesis iniciales, no hechos de mercado."],
        )
