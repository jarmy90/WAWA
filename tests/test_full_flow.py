"""Flujo completo: de problema a decisión, con evidencia verificada -> aprobada."""
from __future__ import annotations

from app.core.container import build_container
from app.models.enums import Decision
from app.models.evidence import Competitor, Evidence
from app.models.opportunity import OpportunityCreate
from tests.conftest import make_settings


def _seed_verified_opportunity(container):
    """Oportunidad con 4 evidencias verificadas independientes + competidor con precio."""
    opp = container.opportunities.create(
        OpportunityCreate(
            title="Auditoría de EAs con investigación verificada",
            problem="Los desarrolladores MQL5 necesitan auditorías sistemáticas de sus Expert Advisors antes de publicarlos.",
            proposed_solution="Servicio de auditoría automática de código y configuración, sin prometer rentabilidad.",
            target_customer="Desarrolladores de EAs MQL5 (perfil concreto identificado).",
            sector="servicios técnicos para trading algorítmico / MQL5",
        )
    )
    evs = [
        Evidence(
            opportunity_id=opp.id,
            evidence_type="demand_signal",
            source_name="Entrevistas a 5 desarrolladores (verificado)",
            summary="5 desarrolladores confirman que pagarían por una auditoría automática.",
            reliability_score=1.0,
            independence_group="entrevistas",
            verified=True,
            verification_notes="Verificado manualmente por el humano.",
            method="import",
        ),
        Evidence(
            opportunity_id=opp.id,
            evidence_type="customer_profile",
            source_name="Encuesta comunidad MQL5",
            summary="Perfil de cliente confirmado: desarrolladores individuales y compradores del Mercado MQL5.",
            reliability_score=0.95,
            independence_group="encuesta",
            verified=True,
            method="import",
        ),
        Evidence(
            opportunity_id=opp.id,
            evidence_type="price",
            source_name="Presupuestos recopilados",
            summary="Presupuestos reales de auditorías manuales entre 80 y 150 USD.",
            reliability_score=0.9,
            independence_group="presupuestos",
            verified=True,
            method="import",
        ),
        Evidence(
            opportunity_id=opp.id,
            evidence_type="technical",
            source_name="Prueba de concepto",
            summary="Prototipo validado: el parseo de logs de MetaTrader funciona en 3 cuentas reales.",
            reliability_score=0.9,
            independence_group="prototipo",
            verified=True,
            method="import",
        ),
    ]
    for e in evs:
        container.repos.evidence.create(e)
    container.repos.competitors.create(
        Competitor(
            opportunity_id=opp.id,
            name="Auditores freelance",
            url="https://example.test/freelance",
            offer="Auditoría manual",
            observed_price=150.0,
            strengths="Conocimiento humano",
            weaknesses="Lento, caro, sin trazabilidad sistemática",
        )
    )
    return opp


def test_full_flow_with_verified_evidence_approves(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        opp = _seed_verified_opportunity(container)
        evaluation = container.pipeline.evaluate(opp.id, clear_existing=False)

        assert 0 <= evaluation.final_score <= 100
        assert evaluation.decision == Decision.approved
        assert evaluation.confidence_score >= 60
        assert evaluation.independent_evidence_count >= 3
        assert evaluation.evidence_quality_score >= 60
        assert evaluation.experiment is not None
        assert evaluation.experiment.cheapest_test
        assert evaluation.experiment.maximum_budget and evaluation.experiment.maximum_budget > 0

        # Los agentes del pipeline dejaron huella en el log (más el humano que creó la oportunidad).
        agents = {l.agent for l in container.repos.decision_log.list_for(opp.id)}
        for expected in ("human", "researcher", "skeptic", "economist", "builder", "compliance", "judge"):
            assert expected in agents

        # Estado final coherente.
        reloaded = container.opportunities.get(opp.id)
        assert reloaded.status.value == "approved"
    finally:
        container.close()


def test_scoring_reproducible_across_runs(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        opp = _seed_verified_opportunity(container)
        e1 = container.pipeline.evaluate(opp.id, clear_existing=False)
        e2 = container.pipeline.evaluate(opp.id, clear_existing=False)
        assert e1.final_score == e2.final_score
        assert e1.decision == e2.decision
        assert e1.confidence_score == e2.confidence_score
    finally:
        container.close()


def test_full_pipeline_offline_mql5(tmp_path):
    """El pipeline completo funciona sin API sobre una oportunidad MQL5 de demo."""
    settings = make_settings(tmp_path, llm_provider="auto", gemini_api_key=None)
    container = build_container(settings)
    try:
        from app.workflows.demo import DemoSeeder

        summary = DemoSeeder(container.settings, container.repos, container.pipeline).seed(evaluate=True)
        assert summary["created"] == 4
        decisions = {r["decision"] for r in summary["results"]}
        assert "needs_more_research" in decisions or "deferred" in decisions  # bandas honestas
        assert container.repos.opportunities.count() == 4
    finally:
        container.close()
