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
        # El resultado del proveedor debe pertenecer al contexto actual. Las
        # heurísticas específicas de MQL5 no pueden aparecer en ortodoncia.
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
            evidence_used=[c.evidence_id for c in competitors if c.evidence_id],
            assumptions=assumptions,
        )
