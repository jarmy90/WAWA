"""Economist — estima costes, precio posible, margen, recurrencia y tiempo
hasta la primera venta.

Todas las salidas son **estimaciones** (basis=estimate) o **desconocidos**.
Nunca inventa precios: si no hay precios observados guardados, lo dice.
"""
from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.providers.manager import ProviderManager


class EconomistAgent(BaseAgent):
    name = "economist"

    def run(self, ctx: AgentContext, providers: ProviderManager) -> AgentResult:
        opportunity = ctx.opportunity
        competitors = ctx.competitors
        prices = [c.observed_price for c in competitors if c.observed_price is not None]

        price_markers = "".join(f"PRICE_{p}" for p in prices) or "NO_PRICES"
        prompt = (
            f"OPORTUNIDAD: {opportunity.title}\n"
            f"PROBLEMA: {opportunity.problem}\n"
            f"SECTOR: {opportunity.sector}\n"
            f"PRECIOS OBSERVADOS: {price_markers}\n"
        )
        call = self._call(
            providers,
            prompt=prompt,
            system=opportunity.problem,
            task="economist",
            output_schema={"estimates": "dict", "assumptions": "list"},
            opportunity_id=opportunity.id,
        )
        structured = call.response.structured or {}
        estimates = structured.get("estimates") or {}
        assumptions = structured.get("assumptions") or []
        return self._result(
            output={"estimates": estimates},
            call=call,
            evidence_used=[c.evidence_id for c in competitors if c.evidence_id],
            assumptions=assumptions,
        )
