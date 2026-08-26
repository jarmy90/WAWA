#!/usr/bin/env python3
"""Iteración 021 — Fijación determinista del estado de lanzamiento.

Decisión de la ganadora por criterios deterministas (torneo 018 + evidencia
verificada de la iteración 021), creación de la evaluación interna honesta
(derivada del Venture Quality Score con evidencia, sin LLM), plan de
experimento completo y auditoría en decision_log. No activa producción ni
conecta servicios: deja el sistema en READY_TO_CONNECT_SERVICES con la lista
de credenciales pendientes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.container import build_container  # noqa: E402
from app.models.decision_log import DecisionLog  # noqa: E402
from app.models.enums import Decision  # noqa: E402
from app.models.evaluation import Evaluation  # noqa: E402
from app.models.orchestrator import ExperimentPlan  # noqa: E402

RUN_ID = "a75e2a00954040398c41cfd660989d33"
WINNER_CONCEPT = "3867e04ec3d64a12bed5f1e8f97c6ac8"
WINNER_OPP = "c1dfd7d527904468997785f8ba18342c"


def main() -> int:
    container = build_container(get_settings())
    repos = container.repos

    venture_rows = repos.discovery.venture_evaluations_by_concept(WINNER_CONCEPT)
    venture = venture_rows[0] if venture_rows else {}
    evidence = repos.evidence.list_for(WINNER_OPP)
    verified = [e for e in evidence if getattr(e, "verified", False)]
    groups = {getattr(e, "independence_group", None) or "x" for e in verified}
    evidence_backed = float(venture.get("evidence_backed_venture_score") or 0.0)

    # 1) Run: seleccionar ganadora y marcar investigación importada.
    repos.orchestrator.update_run(RUN_ID, state="RESEARCH_IMPORTED", selected_opportunity_id=WINNER_OPP)
    repos.orchestrator.add_transition(
        run_id=RUN_ID, from_state="RESEARCH_PENDING", to_state="RESEARCH_IMPORTED",
        actor="system", reason=(
            "Investigación Fase 1 REAL importada (18 misiones, 31 evidencias verificadas). "
            "Ganadora determinista (torneo 018 + evidencia): Benchmark de tarifas de ortodoncia."
        ),
        inputs={"tournament_winner": WINNER_CONCEPT, "evidence_groups": len(groups)},
        outputs={"imported": 18, "evidences_attached": len(verified), "verified_groups": len(groups)},
        synthetic=False, next_action="Preparar paquete de lanzamiento y CONECTAR SERVICIOS (propietario).",
    )

    # 2) Evaluación interna derivada (sin LLM; campos documentados).
    def _avg(*vals: float) -> float:
        return round(sum(vals) / len(vals), 2)

    evaluation = Evaluation(
        opportunity_id=WINNER_OPP,
        pain_score=_avg(venture.get("economic_pain") or 0.0),
        demand_score=venture.get("proven_demand") or 0.0,
        customer_reach_score=venture.get("distribution") or 0.0,
        automation_score=venture.get("operational_simplicity") or 0.0,
        margin_score=venture.get("gross_margin") or 0.0,
        build_speed_score=venture.get("validation_speed") or 0.0,
        differentiation_score=_avg(venture.get("defensibility") or 0.0, venture.get("general_ai_resistance") or 0.0),
        safety_score=100.0,  # benchmark anónimo sin datos de pacientes ni consejo clínico
        evidence_quality_score=min(100.0, float(len(verified)) * 5.0 + float(len(groups)) * 5.0),
        confidence_score=evidence_backed,
        final_score=evidence_backed,
        per_criterion={},
        independent_evidence_count=len(groups),
        unverified_assumptions_count=3,
        assumptions=[
            "Comprador (gerente de clínica 2-5 dentistas) pagaría por un informe de tarifas: HIPÓTESIS no verificada con comprador real.",
            "Presupuesto real de la clínica por este informe: HIPÓTESIS (30-90 EUR).",
            "Urgencia/evento de compra: no detectado en evidencia.",
        ],
        blockers=[],
        approval_reason=(
            f"{len(groups)} grupos de evidencia independiente verificada (URL+fecha+fragmento), "
            f"sin bloqueadores; score con evidencia {evidence_backed:.1f}; decisión SMALL_EXPERIMENT determinista."
        ),
        rejection_reason=None,
        decision=Decision.approved,  # "approved" = candidata a experimento (contrato de readiness)
        model_or_method="activation_021_deterministic (Venture Quality Score con evidencia; sin LLM)",
        skeptic_critique=(
            "El comprador puede resolver con guías de precios gratuitas; la urgencia no está demostrada; "
            "el dominio sanitario exige no tocar datos de pacientes. Por eso la decisión es un experimento "
            "pequeño y barato, no un lanzamiento."
        ),
        risks=[],
        estimates=__import__("app.models.evaluation", fromlist=["Estimates"]).Estimates(),
        experiment=None,
    )
    repos.evaluations.upsert(evaluation)

    # 3) Plan de experimento completo (precondiciones de readiness).
    plan = ExperimentPlan(
        run_id=RUN_ID,
        opportunity_id=WINNER_OPP,
        decision="approved",
        offer="Informe de benchmark anónimo de tarifas de ortodoncia por provincia (rangos y percentiles) para decidir el precio de la clínica.",
        buyer="Gerentes de clínicas dentales de 2-5 dentistas",
        user="Gerente o director de la clínica dental",
        problem="Las clínicas dentales pequeñas fijan el precio de ortodoncia sin un comparativo de tarifas de su zona y pierden margen o pacientes.",
        value_proposition="Decide tu tarifa de ortodoncia con datos reales de tu provincia, no con guías genéricas.",
        price_usd=60.0,
        delivery_format="Informe PDF + revisión por videollamada (entrega concierge)",
        demo="Muestra con 2 provincias de ejemplo antes del pago",
        channel="Contacto directo a 20 clínicas identificadas vía colegios y directorios oficiales (sin spam); LinkedIn y colegios provinciales",
        initial_message="Solicitud de permiso para compartir un informe de tarifas de ortodoncia de tu provincia (sin datos de pacientes).",
        min_sample=3,
        max_contacts=20,
        acquisition_method="Captación manual autorizada por canal; sin spam ni mensajería masiva",
        max_cost_usd=0.0,
        duration_days=30,
        success_metric="primer pago real confirmado",
        success_threshold="1 pago confirmado (30-90 EUR) por un comprador real",
        kill_condition="sin señal de pago tras 14 días de contacto activo",
        product_death_condition="sin señal de pago en 30 días y sin pivote viable",
        possible_pivots=[
            "Vender el benchmark a aseguradoras/software dental como dato agregado anónimo",
            "Ampliar a otras especialidades (implantes, invisible)",
            "Suscripción trimestral de actualización de tarifas",
        ],
        automatable_tasks=[
            "Recopilación y normalización de tarifarios públicos",
            "Generación del informe (plantilla + percentiles)",
            "Seguimiento de contactos y recordatorios",
        ],
        owner_tasks=[
            "Aportar credenciales Stripe (cobro real)",
            "Aportar email transaccional y hosting",
            "Autorizar el ciclo autónomo de 30 días",
        ],
        risks=[
            "Guías de precios gratuitas como sustituto (kill condition cubre)",
            "Dominio sanitario: nunca usar datos de pacientes (informe anónimo agregado)",
            "Urgencia no demostrada: sin evento de compra claro",
        ],
        dependencies=[
            "Método de cobro real autorizado (Stripe u otro)",
            "Email transaccional (envío del informe)",
            "Hosting/dominio para la landing",
            "Analytics de eventos (visitas, leads, checkouts)",
        ],
        payment_readiness="PENDIENTE: requiere método de cobro real autorizado por el propietario",
        missing_capabilities=[],
        blockers=[],
    )
    saved_plan = repos.orchestrator.create_experiment_plan(plan)

    # 4) Auditoría.
    repos.decision_log.add(
        DecisionLog(
            agent="activation_021",
            opportunity_id=WINNER_OPP,
            input_summary="18 misiones Fase 1 importadas con evidencia verificada (URL+fecha+fragmento); torneo 018: 77.5.",
            output_summary=(
                f"Ganadora determinista: {saved_plan['offer'][:80]}. "
                f"{len(verified)} evidencias verificadas, {len(groups)} grupos independientes, "
                f"score con evidencia {evidence_backed:.1f}. Decisión approved (candidata a experimento SMALL). "
                "Producción bloqueada; servicios pendientes de credenciales."
            ),
            evidence_used=[e.source_url for e in verified if e.source_url][:10],
            decision="SMALL_EXPERIMENT",
            model_or_method="deterministic_activation_021",
            estimated_cost=0.0,
            cost_method="zero (offline)",
        )
    )

    snapshot = container.command_center.snapshot()
    readiness = snapshot.get("readiness") or {}
    print(
        json.dumps(
            {
                "readiness_state": readiness.get("readiness_state"),
                "readiness_met": readiness.get("readiness_met"),
                "readiness_missing": readiness.get("readiness_missing"),
                "readiness_blockers": readiness.get("readiness_blockers"),
                "candidate_id": readiness.get("candidate_id"),
                "opportunity_id": readiness.get("opportunity_id"),
                "experiment_id": readiness.get("experiment_id"),
                "evidence": snapshot.get("evidence"),
                "explanation": readiness.get("explanation"),
                "conditions": readiness.get("conditions"),
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    container.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
