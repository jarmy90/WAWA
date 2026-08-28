"""Pipeline de evaluación: orquesta los 13 pasos del flujo.

1.  Descubrir problemas (Scout)
2.  Convertir en oportunidades concretas
3.  Agrupar y eliminar duplicados
4.  Investigar evidencias (Researcher)
5.  Identificar cliente objetivo
6.  Analizar alternativas y competidores
7.  Estimar dificultad, coste, precio y margen (Economist + Builder)
8.  Evaluar capacidad de automatización (Builder)
9.  Crítica adversarial (Skeptic)
10. Puntuación determinista (Judge)
11. Proponer experimento pequeño y medible (Judge)
12. Seleccionar / aplazar / rechazar (Judge + revisión humana opcional)
13. Guardar todo el razonamiento, evidencias y decisiones (SQLite + DecisionLog)

Cada paso se registra en el DecisionLog (append-only) con su coste estimado,
método y errores. El Judge es 100% determinista: puntúa solo datos guardados.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app.agents import (
    BuilderAgent,
    ComplianceAgent,
    EconomistAgent,
    JudgeAgent,
    ResearcherAgent,
    ScoutAgent,
    SkepticAgent,
)
from app.agents.base import AgentContext, AgentResult
from app.core.config import Settings
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.models.decision_log import DecisionLog
from app.models.enums import AgentName, OpportunityStatus
from app.models.opportunity import Opportunity
from app.providers.manager import ProviderManager
from app.repositories import Repos


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate(value, limit: int = 2_000) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text[:limit]


class PipelineService:
    def __init__(self, settings: Settings, repos: Repos, providers: ProviderManager, budget, engine=None) -> None:
        self.settings = settings
        self.repos = repos
        self.providers = providers
        self.budget = budget
        self.engine = engine  # EngineService opcional: alimenta el timeline en vivo
        self.reviews = None  # ReviewService opcional: cola de finalistas (iteración 005)
        self.log = get_logger("pipeline")

    # ------------------------------------------------------------------
    def discover(self, problem: str, sector_hint: str | None = None, source: str = "scout") -> list[Opportunity]:
        """Pasos 1-3: Scout genera candidatos, se deduplican y se crean."""
        scout = ScoutAgent(self.settings)
        ctx = AgentContext(
            opportunity=Opportunity(
                title="(borrador Scout)",
                problem=problem,
                sector=sector_hint,
                source=source,
            ),
            extras={"problem": problem, "sector_hint": sector_hint, "source": source},
        )
        result = scout.run(ctx, self.providers)

        created: list[Opportunity] = []
        for draft in result.output.get("opportunities") or []:
            try:
                opportunity = Opportunity(
                    title=draft.get("title") or problem[:80],
                    problem=draft.get("problem") or problem,
                    proposed_solution=draft.get("proposed_solution"),
                    target_customer=draft.get("target_customer"),
                    sector=draft.get("sector") or sector_hint,
                    source=source,
                    status=OpportunityStatus.draft,
                )
            except Exception:
                continue
            # Paso 3: deduplicación por título normalizado.
            if self.repos.opportunities.find_similar_title(opportunity.title):
                self._log_step(AgentName.scout, opportunity, result, decision="skipped (duplicado)")
                continue
            self.repos.opportunities.create(opportunity)
            created.append(opportunity)
            self._log_step(AgentName.scout, opportunity, result)
        return created

    # ------------------------------------------------------------------
    def evaluate(self, opportunity_id: str, *, clear_existing: bool = True):
        """Pasos 4-13: investigación, crítica, economía, construcción,
        cumplimiento, puntuación y decisión."""
        opportunity = self.repos.opportunities.get(opportunity_id)
        if opportunity is None:
            raise NotFoundError("Oportunidad no encontrada.")

        # La evaluación debe partir únicamente del contexto de esta
        # oportunidad. Los agentes usan proveedores opcionales, pero sus
        # salidas se validan contra el texto persistido antes de llegar al
        # Judge; una contaminación conocida debe bloquear, no sobrescribirse.
        self._assert_opportunity_context(opportunity)
        self.budget.guard_deep_evaluation(opportunity_id)
        self.repos.opportunities.set_status(opportunity_id, OpportunityStatus.researching)

        # Limpiar resultados anteriores (el DecisionLog es append-only y se conserva).
        if clear_existing:
            self.repos.evidence.delete_for_opportunity(opportunity_id)
            self.repos.competitors.delete_for_opportunity(opportunity_id)
            # Las evaluaciones históricas son append-only; la nueva versión
            # se enlaza automáticamente mediante supersedes_id.
            self.repos.experiments.delete_for(opportunity_id)

        previous: dict = {}

        # --- Paso 4-6: Researcher (evidencias, cliente, competidores) -------
        researcher = ResearcherAgent(self.settings)
        ctx = AgentContext(
            opportunity=opportunity,
            evidences=[],
            competitors=[],
            previous=previous,
            repos=self.repos,
        )
        res_result = researcher.run(ctx, self.providers)
        self._log_step(AgentName.researcher, opportunity, res_result)
        previous["researcher"] = res_result.output

        # Recargar evidencias y competidores persistidos.
        evidences = self.repos.evidence.list_for(opportunity_id)
        competitors = self.repos.competitors.list_for(opportunity_id)
        opportunity = self.repos.opportunities.get(opportunity_id)

        # --- Paso 9: Skeptic (necesita evidencias) --------------------------
        skeptic = SkepticAgent(self.settings)
        ctx = AgentContext(opportunity=opportunity, evidences=evidences, competitors=competitors, previous=previous)
        sk_result = skeptic.run(ctx, self.providers)
        self._log_step(AgentName.skeptic, opportunity, sk_result)
        previous["skeptic"] = sk_result.output

        # --- Paso 7: Economist -------------------------------------------------
        economist = EconomistAgent(self.settings)
        ctx = AgentContext(opportunity=opportunity, evidences=evidences, competitors=competitors, previous=previous)
        ec_result = economist.run(ctx, self.providers)
        self._log_step(AgentName.economist, opportunity, ec_result)
        previous["estimates_economist"] = ec_result.output.get("estimates") or {}
        previous.setdefault("assumptions", []).extend(ec_result.assumptions)

        # --- Paso 7-8: Builder (complejidad + automatización) -------------------
        builder = BuilderAgent(self.settings)
        ctx = AgentContext(opportunity=opportunity, evidences=evidences, competitors=competitors, previous=previous)
        bu_result = builder.run(ctx, self.providers)
        self._log_step(AgentName.builder, opportunity, bu_result)
        previous["estimates_builder"] = bu_result.output.get("estimates") or {}
        previous.setdefault("assumptions", []).extend(bu_result.assumptions)

        # --- Compliance ----------------------------------------------------------
        compliance = ComplianceAgent(self.settings)
        ctx = AgentContext(opportunity=opportunity, evidences=evidences, competitors=competitors, previous=previous)
        co_result = compliance.run(ctx, self.providers)
        self._log_step(AgentName.compliance, opportunity, co_result)
        previous["risks"] = co_result.output.get("risks") or []
        previous["blockers"] = co_result.output.get("blockers") or []
        previous.setdefault("assumptions", []).extend(co_result.assumptions)

        # --- Paso 10-12: Judge (determinista) -----------------------------------
        judge = JudgeAgent(self.settings)
        ctx = AgentContext(
            opportunity=opportunity,
            evidences=evidences,
            competitors=competitors,
            previous=previous,
        )
        ju_result = judge.run(ctx, self.providers)
        evaluation = self.repos.evaluations.upsert(_evaluation_from_judge(ju_result))
        if evaluation.experiment:
            self.repos.experiments.upsert(evaluation.experiment)
        status = {
            "approved": OpportunityStatus.approved,
            "needs_more_research": OpportunityStatus.needs_more_research,
            "deferred": OpportunityStatus.deferred,
            "rejected": OpportunityStatus.rejected,
            "blocked": OpportunityStatus.blocked,
        }[evaluation.decision.value]
        self.repos.opportunities.set_status(opportunity_id, status)
        self._log_step(AgentName.judge, opportunity, ju_result, decision=evaluation.decision.value)

        # Iteración 005: las finalistas aprobadas entran en la cola del comité
        # de contraste (revisiones externas opcionales; nunca bloquea el flujo).
        if self.reviews is not None and status == OpportunityStatus.approved:
            self.reviews.auto_queue(opportunity_id)

        self.log.info(
            "Evaluación completada",
            extra={
                "opportunity_id": opportunity_id,
                "final_score": evaluation.final_score,
                "decision": evaluation.decision.value,
                "confidence": evaluation.confidence_score,
            },
        )
        return evaluation

    @staticmethod
    def _assert_opportunity_context(opportunity: Opportunity) -> None:
        """Rechaza contexto histórico incompatible antes de puntuar."""
        context = " ".join(
            str(value or "")
            for value in (opportunity.title, opportunity.problem, opportunity.proposed_solution, opportunity.sector)
        ).lower()
        trading_markers = ("mql5", "metatrader", "trading", "expert advisor")
        if "ortodoncia" in context or "clínica dental" in context or "clinica dental" in context:
            if any(marker in context for marker in trading_markers):
                raise ValueError("Integridad bloqueada: contexto dental mezclado con contexto trading/MQL5.")

    # ------------------------------------------------------------------
    def _log_step(
        self,
        agent: AgentName,
        opportunity: Opportunity,
        result: AgentResult,
        *,
        decision: str | None = None,
    ) -> None:
        if self.engine is not None:
            summary = {
                AgentName.scout: "Ha propuesto oportunidades iniciales a partir del problema.",
                AgentName.researcher: "Ha contrastado demanda, competidores y perfil de cliente.",
                AgentName.skeptic: "Ha sometido la oportunidad a crítica adversaria.",
                AgentName.economist: "Ha estimado precios, márgenes y tiempos.",
                AgentName.builder: "Ha estimado complejidad, tiempo de construcción y automatización.",
                AgentName.compliance: "Ha revisado riesgos legales, de ToS y de privacidad.",
                AgentName.judge: f"Ha puntuado la oportunidad ({result.decision or 'decisión registrada'}).",
            }.get(agent, f"Agente {agent.value} ha completado su paso.")
            try:
                self.engine.record_event(
                    event_type=f"agent:{agent.value}",
                    summary=summary,
                    opportunity_id=opportunity.id,
                    cost_usd=result.estimated_cost,
                )
            except Exception:
                pass  # el timeline nunca debe romper el pipeline
        self.repos.decision_log.add(
            DecisionLog(
                timestamp=_now(),
                agent=agent.value,
                opportunity_id=opportunity.id,
                input_summary=_truncate(f"{opportunity.title} — {opportunity.problem}", 1_000),
                output_summary=_truncate(json.dumps(result.output, ensure_ascii=False), 5_000),
                evidence_used=result.evidence_used,
                decision=decision or result.decision,
                model_or_method=result.model_or_method,
                estimated_cost=result.estimated_cost,
                cost_method=result.cost_method,
                errors=result.errors,
            )
        )


def _evaluation_from_judge(result: AgentResult):
    """Reconstruye el modelo Evaluation desde la salida del Judge."""
    from app.models.evaluation import Evaluation

    data = result.output
    return Evaluation.model_validate(data)
