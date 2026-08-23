"""Compliance — detecta riesgos legales, financieros, reputacionales, de
privacidad y de condiciones de servicio.

Los riesgos con ``blocker=true`` bloquean la decisión (ver docs/SCORING.md).
"""
from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.providers.manager import ProviderManager


class ComplianceAgent(BaseAgent):
    name = "compliance"

    def run(self, ctx: AgentContext, providers: ProviderManager) -> AgentResult:
        opportunity = ctx.opportunity
        text = (
            f"{opportunity.title}\n{opportunity.problem}\n{opportunity.proposed_solution or ''}\n"
            f"SECTOR: {opportunity.sector}"
        )
        call = self._call(
            providers,
            prompt=text,
            system=text,
            task="compliance",
            output_schema={"risks": "list", "blockers": "list"},
            opportunity_id=opportunity.id,
        )
        structured = call.response.structured or {}
        risks = structured.get("risks") or []
        blockers = structured.get("blockers") or []
        return self._result(
            output={"risks": risks, "blockers": blockers},
            call=call,
            assumptions=[f"Riesgo {r.get('severity')}: {r.get('description', '')[:200]}" for r in risks],
        )
