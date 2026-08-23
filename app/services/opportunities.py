"""Servicio de oportunidades: CRUD, detalle agregado y decisiones manuales."""
from __future__ import annotations

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationError
from app.models.decision_log import DecisionLog
from app.models.enums import AgentName, Decision, OpportunityStatus
from app.models.opportunity import Opportunity, OpportunityCreate
from app.repositories import Repos

MANUAL_DECISIONS = {Decision.approved, Decision.deferred, Decision.rejected, Decision.needs_more_research}

STATUS_FROM_DECISION = {
    Decision.approved: OpportunityStatus.approved,
    Decision.needs_more_research: OpportunityStatus.needs_more_research,
    Decision.deferred: OpportunityStatus.deferred,
    Decision.rejected: OpportunityStatus.rejected,
    Decision.blocked: OpportunityStatus.blocked,
}


class OpportunityService:
    def __init__(self, settings: Settings, repos: Repos) -> None:
        self.settings = settings
        self.repos = repos

    # ------------------------------------------------------------------
    def create(self, data: OpportunityCreate) -> Opportunity:
        opportunity = Opportunity(
            title=data.title,
            problem=data.problem,
            proposed_solution=data.proposed_solution,
            target_customer=data.target_customer,
            sector=data.sector,
            source=data.source,
            status=OpportunityStatus.draft,
        )
        self.repos.opportunities.create(opportunity)
        self.repos.decision_log.add(
            DecisionLog(
                agent=AgentName.human.value,
                opportunity_id=opportunity.id,
                input_summary="Creación manual de oportunidad.",
                output_summary=f"Oportunidad creada: {opportunity.title}",
                model_or_method="manual",
            )
        )
        return opportunity

    def get(self, opportunity_id: str) -> Opportunity:
        opportunity = self.repos.opportunities.get(opportunity_id)
        if opportunity is None:
            raise NotFoundError("Oportunidad no encontrada.")
        return opportunity

    def list_with_scores(self, *, status: OpportunityStatus | None = None) -> list[dict]:
        opportunities = self.repos.opportunities.list(status=status)
        scores = self.repos.evaluations.latest_scores()
        return [
            {**o.model_dump(), "final_score": scores.get(o.id), "has_evaluation": o.id in scores}
            for o in opportunities
        ]

    def detail(self, opportunity_id: str) -> dict:
        opportunity = self.get(opportunity_id)
        return {
            "opportunity": opportunity.model_dump(),
            "evidences": [e.model_dump() for e in self.repos.evidence.list_for(opportunity_id)],
            "competitors": [c.model_dump() for c in self.repos.competitors.list_for(opportunity_id)],
            "evaluation": self.repos.evaluations.get(opportunity_id).model_dump() if self.repos.evaluations.get(opportunity_id) else None,
            "experiment": self.repos.experiments.get_for(opportunity_id).model_dump() if self.repos.experiments.get_for(opportunity_id) else None,
            "decision_log": [d.model_dump() for d in self.repos.decision_log.list_for(opportunity_id)],
        }

    def set_decision(self, opportunity_id: str, decision: Decision, note: str | None = None) -> Opportunity:
        """Decisión manual (humano). Solo estados permitidos; nunca 'blocked'."""
        if decision not in MANUAL_DECISIONS:
            raise ValidationError(f"Decisión manual no permitida: {decision.value}. Use approved/deferred/rejected/needs_more_research.")
        opportunity = self.get(opportunity_id)
        new_status = STATUS_FROM_DECISION[decision]
        self.repos.opportunities.set_status(opportunity_id, new_status)

        evaluation = self.repos.evaluations.get(opportunity_id)
        if evaluation is not None:
            evaluation.decision = decision
            evaluation.rejection_reason = note or evaluation.rejection_reason
            self.repos.evaluations.upsert(evaluation)

        self.repos.decision_log.add(
            DecisionLog(
                agent=AgentName.human.value,
                opportunity_id=opportunity_id,
                input_summary=f"Decisión manual solicitada: {decision.value}",
                output_summary=note or f"Decisión manual: {decision.value}",
                decision=decision.value,
                model_or_method="manual (humano)",
            )
        )
        return self.get(opportunity_id)
