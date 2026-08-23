"""Judge — calcula la puntuación final usando EXCLUSIVAMENTE los datos y
evidencias guardados.

Es 100% determinista (no llama a ningún proveedor de IA): reproduce el
mismo resultado para los mismos datos. Cada criterio lleva su base
(evidence/estimate/unknown) y las evidencias que lo sustentan.

Pesos por defecto (ver docs/SCORING.md):
pain 20% | demand 20% | customer_reach 15% | automation 15% |
margin 10% | build_speed 10% | differentiation 5% | safety 5%
"""
from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.models.enums import Basis
from app.models.evaluation import CriterionScore, Estimates, Evaluation, Experiment, RiskItem
from app.providers.manager import ProviderManager
from app.scoring.engine import ScoreInput, decide

UNKNOWN_CUSTOMER_MARKERS = ("DESCONOCIDO", "POR DEFINIR", "PENDIENTE")


def _is_real_evidence(e) -> bool:
    """Evidencia real = datos aportados por fuentes (demo/import/manual/gemini)
    con fiabilidad > 0 o verificados. Los marcadores del proveedor simulado
    (método 'mock*', fiabilidad 0) NO cuentan como evidencia."""
    if e.method.startswith("mock"):
        return False
    return e.reliability_score > 0.0 or e.verified


def _is_unknown_text(value: str | None) -> bool:
    if not value:
        return True
    upper = value.upper()
    return any(m in upper for m in UNKNOWN_CUSTOMER_MARKERS)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class JudgeAgent(BaseAgent):
    name = "judge"

    def run(self, ctx: AgentContext, providers: ProviderManager) -> AgentResult:
        opportunity = ctx.opportunity
        evidences = ctx.evidences
        competitors = ctx.competitors
        prev = ctx.previous

        real = [e for e in evidences if _is_real_evidence(e)]
        verified = [e for e in real if e.verified]
        groups = {e.independence_group for e in real if e.independence_group}

        estimates: dict = {}
        for key in ("estimates_economist", "estimates_builder"):
            estimates.update(prev.get(key) or {})
        try:
            estimates_model = Estimates.model_validate(estimates)
        except Exception:
            estimates_model = Estimates()

        risks = [RiskItem.model_validate(r) for r in (prev.get("risks") or [])]
        blockers = list(prev.get("blockers") or [])
        skeptic = prev.get("skeptic") or {}

        # --- Criterios ---------------------------------------------------
        criteria: dict[str, CriterionScore] = {}

        # pain
        pain_evidence = [e for e in real if e.evidence_type in ("demand_signal", "customer_profile", "technical")]
        if pain_evidence:
            avg = sum(e.reliability_score for e in pain_evidence) / len(pain_evidence)
            criteria["pain"] = CriterionScore(
                score=round(_clamp(40 + 30 * avg, 20, 90), 1),
                basis=Basis.evidence,
                evidence_ids=[e.id for e in pain_evidence],
                rationale="Hay evidencia guardada sobre dolor/necesidad; la fiabilidad modula la puntuación.",
            )
        else:
            criteria["pain"] = CriterionScore(
                score=15.0, basis=Basis.unknown, rationale="Sin evidencia de dolor: desconocido."
            )

        # demand
        if real:
            eql = _evidence_quality(real, verified, groups)
            criteria["demand"] = CriterionScore(
                score=round(eql, 1),
                basis=Basis.evidence,
                evidence_ids=[e.id for e in real],
                rationale="Puntuación de demanda = calidad de la evidencia guardada.",
            )
        else:
            criteria["demand"] = CriterionScore(
                score=10.0, basis=Basis.unknown, rationale="Sin evidencia guardada: demanda desconocida."
            )

        # customer_reach
        customer_ok = opportunity.target_customer and not _is_unknown_text(opportunity.target_customer)
        reachability = estimates_model.reachability
        reach_known = bool(reachability) and not _is_unknown_text(reachability)
        profile_evidence = [e for e in real if e.evidence_type == "customer_profile"]
        reach_estimated = reach_known or bool(profile_evidence)
        if customer_ok and reach_known:
            criteria["customer_reach"] = CriterionScore(
                score=75.0, basis=Basis.estimate, rationale="Cliente objetivo definido y canal de llegada estimado (sin verificar)."
            )
        elif customer_ok and profile_evidence:
            criteria["customer_reach"] = CriterionScore(
                score=60.0,
                basis=Basis.estimate,
                rationale="Cliente objetivo definido; canal plausible indicado por evidencia de perfil (sin verificar).",
            )
        elif customer_ok:
            criteria["customer_reach"] = CriterionScore(
                score=45.0, basis=Basis.estimate, rationale="Cliente objetivo definido, pero canales de llegada desconocidos."
            )
        else:
            criteria["customer_reach"] = CriterionScore(
                score=15.0, basis=Basis.unknown, rationale="Sin cliente objetivo concreto."
            )

        # automation
        if estimates_model.automation_degree is not None:
            criteria["automation"] = CriterionScore(
                score=float(estimates_model.automation_degree),
                basis=Basis.estimate,
                rationale="Grado de automatización estimado por el Builder.",
            )
        else:
            criteria["automation"] = CriterionScore(score=30.0, basis=Basis.unknown, rationale="Automatización no estimada.")

        # margin
        price_known = estimates_model.price_low_usd is not None and estimates_model.price_low_usd > 0
        if price_known:
            criteria["margin"] = CriterionScore(
                score=70.0,
                basis=Basis.estimate,
                rationale="Precio estimado a partir de precios observados; margen típico de servicios digitales (55-85%).",
            )
        else:
            criteria["margin"] = CriterionScore(
                score=20.0, basis=Basis.unknown, rationale="Precio desconocido: no hay precios observados guardados."
            )

        # build_speed
        if estimates_model.build_days_low is not None and estimates_model.build_days_high is not None:
            avg_days = (estimates_model.build_days_low + estimates_model.build_days_high) / 2
            criteria["build_speed"] = CriterionScore(
                score=round(_clamp(100 - avg_days * 2.5, 20, 90), 1),
                basis=Basis.estimate,
                rationale="Velocidad de construcción estimada por el Builder.",
            )
        else:
            criteria["build_speed"] = CriterionScore(score=30.0, basis=Basis.unknown, rationale="Tiempo de construcción no estimado.")

        # differentiation
        if competitors:
            has_weaknesses = any(c.weaknesses for c in competitors)
            criteria["differentiation"] = CriterionScore(
                score=80.0 if has_weaknesses else 65.0,
                basis=Basis.estimate,
                rationale=f"{len(competitors)} competidor(es) identificado(s); debilidades documentadas." if has_weaknesses else f"{len(competitors)} competidor(es) identificado(s).",
            )
        else:
            criteria["differentiation"] = CriterionScore(
                score=25.0, basis=Basis.unknown, rationale="Sin competidores identificados: diferenciación desconocida."
            )

        # safety
        high_risks = [r for r in risks if r.severity == "high"]
        medium_risks = [r for r in risks if r.severity == "medium"]
        if high_risks:
            criteria["safety"] = CriterionScore(
                score=15.0, basis=Basis.estimate, rationale=f"{len(high_risks)} riesgo(s) de severidad alta."
            )
        elif medium_risks:
            criteria["safety"] = CriterionScore(
                score=70.0, basis=Basis.estimate, rationale=f"{len(medium_risks)} riesgo(s) medios con mitigación propuesta."
            )
        elif risks:
            criteria["safety"] = CriterionScore(score=85.0, basis=Basis.estimate, rationale="Riesgos bajos.")
        else:
            criteria["safety"] = CriterionScore(score=50.0, basis=Basis.unknown, rationale="Riesgos no evaluados.")

        # --- Bloqueadores estructurales -----------------------------------
        if not real:
            blockers.append("No contiene evidencias guardadas (solo marcadores de desconocido).")
        if not customer_ok:
            blockers.append("No tiene un cliente objetivo concreto.")
        if not reach_estimated:
            blockers.append("No existe una forma razonable de llegar a compradores.")
        if estimates_model.initial_spend_level and "alto" in str(estimates_model.initial_spend_level).lower():
            blockers.append("Requiere un gasto inicial elevado.")
        for risk in risks:
            if risk.blocker:
                blockers.append(f"Riesgo grave: {risk.description}")
            if risk.category == "tos_plataforma" and risk.severity == "high":
                blockers.append("Depende de una plataforma externa que puede prohibir la automatización.")
            if risk.category in ("asesoramiento_financiero", "regulada") and risk.severity == "high":
                blockers.append("Exige una actividad regulada que el sistema no puede cumplir.")

        # Deduplicar manteniendo el orden.
        blockers = list(dict.fromkeys(blockers))

        # --- Puntuación -----------------------------------------------------
        assumptions = list(prev.get("assumptions") or [])
        assumptions += skeptic.get("weakest_assumptions") or []
        unique_assumptions = list(dict.fromkeys(a for a in assumptions if a))

        score_input = ScoreInput(
            criteria=criteria,
            weights=self.settings.scoring_weights(),
            assumptions=unique_assumptions,
            blockers=blockers,
            verified_evidence_count=len(verified),
            total_evidence_count=len(real),
            reliability_values=[e.reliability_score for e in real],
            independent_groups=groups,
            bands=self.settings.decision_bands(),
        )
        result = decide(score_input)

        # --- Experimento (si procede) --------------------------------------
        experiment: Experiment | None = None
        if result.decision in ("approved", "needs_more_research"):
            price_ref = estimates_model.price_low_usd or 50.0
            experiment = Experiment(
                opportunity_id=opportunity.id,
                hypothesis=(
                    f"Existen compradores con el problema '{opportunity.problem[:160]}' "
                    f"dispuestos a pagar ≈{price_ref:.0f} USD por la solución propuesta."
                ),
                cheapest_test=(
                    "Venta concierge: ofrecer el servicio manualmente a 3-5 clientes potenciales "
                    "(o página de aterrizaje con lista de espera) antes de construir nada."
                ),
                maximum_budget=min(50.0, price_ref),
                success_metric="Número de clientes que pagan o reservan",
                success_threshold=">=3 reservas/pagos confirmados",
                failure_threshold="0 reservas en 14 días",
                duration="14-30 días",
                status="proposed",
            )

        evaluation = Evaluation(
            opportunity_id=opportunity.id,
            pain_score=criteria["pain"].score,
            demand_score=criteria["demand"].score,
            customer_reach_score=criteria["customer_reach"].score,
            automation_score=criteria["automation"].score,
            margin_score=criteria["margin"].score,
            build_speed_score=criteria["build_speed"].score,
            differentiation_score=criteria["differentiation"].score,
            safety_score=criteria["safety"].score,
            evidence_quality_score=result.evidence_quality_score,
            confidence_score=result.confidence_score,
            final_score=result.final_score,
            per_criterion=criteria,
            independent_evidence_count=result.independent_evidence_count,
            unverified_assumptions_count=result.unverified_assumptions_count,
            assumptions=unique_assumptions,
            blockers=result.blockers,
            approval_reason=result.approval_reason,
            rejection_reason=result.rejection_reason,
            decision=result.decision,
            model_or_method="determinista (motor de puntuación, sin LLM)",
            skeptic_critique=skeptic.get("critique"),
            risks=risks,
            estimates=estimates_model,
            experiment=experiment,
        )

        return self._result(
            output=evaluation.model_dump(),
            decision=result.decision.value,
            evidence_used=[e.id for e in real],
            assumptions=unique_assumptions,
            method="determinista (motor de puntuación)",
        )


def _evidence_quality(real, verified, groups) -> float:
    """Reutiliza la fórmula del motor (consistencia garantizada)."""
    from app.scoring.engine import evidence_quality_score

    return evidence_quality_score(
        reliability_values=[e.reliability_score for e in real],
        verified_evidence_count=len(verified),
        total_evidence_count=len(real),
        independent_groups=groups,
    )
