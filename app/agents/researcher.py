"""Researcher — busca o procesa evidencias, competidores, precios y clientes.

Regla: **nunca inventar**. Lo que el proveedor no pueda verificar se guarda
como evidencia de tipo "desconocido" (reliability 0, no verificada). Las
entradas del proveedor manual (humano/Freebuff) sí pueden llegar verificadas.

Persiste directamente en SQLite a través de ``ctx.repos``; el workflow solo
orquesta.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.models.evidence import Competitor, Evidence, EvidenceCreate
from app.providers.manager import ProviderManager


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResearcherAgent(BaseAgent):
    name = "researcher"

    def run(self, ctx: AgentContext, providers: ProviderManager) -> AgentResult:
        opportunity = ctx.opportunity
        call = self._call(
            providers,
            prompt=(
                f"OPPORTUNITY:\n{opportunity.title}\n{opportunity.problem}\n"
                f"Solución: {opportunity.proposed_solution or 'n/a'}\n"
                f"Cliente: {opportunity.target_customer or 'desconocido'}"
            ),
            system=opportunity.problem,
            task="research",
            output_schema={"evidences": "list", "competitors": "list", "target_customer": "str|null", "unknowns": "list"},
            opportunity_id=opportunity.id,
        )
        structured = call.response.structured or {}
        repos = ctx.repos
        evidence_ids: list[str] = []
        created, duplicates = 0, 0

        for raw in structured.get("evidences") or []:
            if not isinstance(raw, dict):
                continue
            try:
                create = EvidenceCreate.model_validate(raw)
            except Exception:
                continue
            verified = create.verified
            if call.response.verified is not None:
                verified = call.response.verified
            evidence = Evidence(
                **create.model_dump(exclude={"verified", "verification_notes", "method"}),
                opportunity_id=opportunity.id,
                captured_at=_now(),
                verified=verified,
                verification_notes=create.verification_notes or (
                    "Verificada por aportación manual." if verified else f"Sin verificación externa (método: {call.response.method})."
                ),
                collected_by=self.name,
                method=call.response.method,
            )
            if repos and repos.evidence.is_duplicate(evidence):
                duplicates += 1
                continue
            repos.evidence.create(evidence)
            evidence_ids.append(evidence.id)
            created += 1

        competitors_out: list[dict] = []
        if repos:
            for raw in structured.get("competitors") or []:
                if not isinstance(raw, dict):
                    continue
                try:
                    comp = Competitor(
                        **raw,
                        opportunity_id=opportunity.id,
                        evidence_id=evidence_ids[0] if evidence_ids else None,
                    )
                except Exception:
                    continue
                repos.competitors.create(comp)
                competitors_out.append(comp.model_dump())

        target_customer = structured.get("target_customer")
        if target_customer and repos and not (opportunity.target_customer and "DESCONOCIDO" not in opportunity.target_customer.upper()):
            opportunity.target_customer = str(target_customer)[:2_000]
            repos.opportunities.update(opportunity)

        return self._result(
            output={
                "evidences_created": created,
                "evidences_duplicates_skipped": duplicates,
                "competitors_created": len(competitors_out),
                "target_customer": target_customer,
                "unknowns": structured.get("unknowns") or [],
            },
            call=call,
            evidence_used=evidence_ids,
            assumptions=[f"Dato desconocido (sin evidencia): {u}" for u in (structured.get("unknowns") or [])],
        )
