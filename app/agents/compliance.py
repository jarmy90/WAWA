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
        # El proveedor mock conserva heurísticas históricas para el vertical
        # MQL5. Nunca permitimos que esas plantillas contaminen otra
        # oportunidad: el contexto persistido es la única fuente de verdad.
        context = " ".join(
            str(value or "")
            for value in (opportunity.title, opportunity.problem, opportunity.proposed_solution, opportunity.sector)
        ).lower()
        if "mql5" not in context and "metatrader" not in context and "trading" not in context:
            risks = [r for r in risks if not any(
                marker in str(r.get("description", "")).lower()
                for marker in ("trading", "mql5", "metatrader", "asesoramiento financiero")
            )]
            blockers = [b for b in blockers if not any(
                marker in str(b).lower() for marker in ("trading", "mql5", "metatrader")
            )]
        return self._result(
            output={"risks": risks, "blockers": blockers},
            call=call,
            assumptions=[f"Riesgo {r.get('severity')}: {r.get('description', '')[:200]}" for r in risks],
        )
