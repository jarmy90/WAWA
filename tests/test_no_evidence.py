"""Una oportunidad sin evidencia guardada nunca puede aprobarse."""
from __future__ import annotations

from app.core.container import build_container
from app.models.enums import Decision
from app.models.opportunity import OpportunityCreate
from tests.conftest import make_settings


def test_no_evidence_blocks(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        opp = container.opportunities.create(
            OpportunityCreate(
                title="Idea sin evidencia",
                problem="Problema hipotético descrito con detalle pero sin ninguna fuente.",
                proposed_solution="Solución hipotética.",
                target_customer=None,
                sector="genérico",
            )
        )
        # Sin evidencias: el Researcher solo añade marcadores de desconocido.
        evaluation = container.pipeline.evaluate(opp.id, clear_existing=False)
        assert evaluation.decision == Decision.blocked
        assert any("evidencia" in b.lower() for b in evaluation.blockers)
        assert evaluation.demand_score <= 10
        assert evaluation.confidence_score < 50
    finally:
        container.close()


def test_no_evidence_low_scores(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        opp = container.opportunities.create(
            OpportunityCreate(
                title="Oportunidad sin datos",
                problem="Descripción de un problema sin ninguna evidencia adjunta.",
                proposed_solution="Servicio digital.",
                target_customer="Clientes genéricos.",
                sector="genérico",
            )
        )
        evaluation = container.pipeline.evaluate(opp.id, clear_existing=False)
        assert evaluation.evidence_quality_score == 0.0
        assert evaluation.final_score < 60
    finally:
        container.close()
