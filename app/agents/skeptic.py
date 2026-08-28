"""Skeptic — intenta demostrar que la oportunidad es mala, inviable o cara.

Recibe las evidencias guardadas y produce la crítica más dura posible. Su
salida alimenta los criterios "demanda" y "diferenciación" del Judge.
"""
from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.providers.manager import ProviderManager


class SkepticAgent(BaseAgent):
    name = "skeptic"

    def run(self, ctx: AgentContext, providers: ProviderManager) -> AgentResult:
        opportunity = ctx.opportunity
        evidences = ctx.evidences
        competitors = ctx.competitors

        verified = [e for e in evidences if e.verified]
        unknowns = [e for e in evidences if e.reliability_score <= 0.0]
        real = [e for e in evidences if not (e.method == "mock" and e.reliability_score <= 0.0)]

        summary_lines = []
        for e in real[:10]:
            summary_lines.append(f"- [{e.evidence_type}] {e.summary[:200]} (fiabilidad {e.reliability_score:.2f}, verificada={e.verified})")
        if unknowns:
            summary_lines.append(f"- {len(unknowns)} dato(s) marcados como DESCONOCIDO.")

        prompt = (
            f"OPORTUNIDAD: {opportunity.title}\n"
            f"PROBLEMA: {opportunity.problem}\n"
            f"VERIFIED_{len(verified)} UNKNOWN_{len(unknowns)}\n"
            f"EVIDENCIAS:\n" + "\n".join(summary_lines) + "\n"
            f"COMPETIDORES: {len(competitors)}\n"
        )
        call = self._call(
            providers,
            prompt=prompt,
            system=opportunity.problem,
            task="skeptic",
            output_schema={"critique": "str", "objections": "list", "weakest_assumptions": "list", "counterpoints": "list"},
            opportunity_id=opportunity.id,
        )
        structured = call.response.structured or {}
        critique = structured.get("critique") or call.response.text
        context = " ".join(
            str(value or "")
            for value in (opportunity.title, opportunity.problem, opportunity.proposed_solution, opportunity.sector)
        ).lower()
        if "mql5" not in context and "metatrader" not in context and "trading" not in context:
            structured = {
                **structured,
                "objections": [o for o in (structured.get("objections") or []) if not any(
                    marker in str(o).lower() for marker in ("mql5", "metatrader", "trading")
                )],
                "weakest_assumptions": [a for a in (structured.get("weakest_assumptions") or []) if not any(
                    marker in str(a).lower() for marker in ("mql5", "metatrader", "trading")
                )],
            }
            critique = critique if not any(marker in critique.lower() for marker in ("mql5", "metatrader", "trading")) else (
                "La crítica del proveedor contenía referencias ajenas al contexto; se descartó y requiere revisión neutral."
            )
        return self._result(
            output={
                "critique": critique,
                "objections": structured.get("objections") or [],
                "weakest_assumptions": structured.get("weakest_assumptions") or [],
                "counterpoints": structured.get("counterpoints") or [],
            },
            call=call,
            evidence_used=[e.id for e in real],
            assumptions=[f"Objeciones del Skeptic: {o}" for o in (structured.get("objections") or [])],
        )
