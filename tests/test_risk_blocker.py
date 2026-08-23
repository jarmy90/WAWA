"""Bloqueo por riesgo grave (Compliance)."""
from __future__ import annotations

from app.core.container import build_container
from app.models.enums import Decision
from app.models.opportunity import OpportunityCreate
from tests.conftest import make_settings


def test_high_risk_blocks(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        opp = container.opportunities.create(
            OpportunityCreate(
                title="Bot con rentabilidad garantizada",
                problem="Un bot que ofrece rentabilidad garantizada operando en MetaTrader.",
                proposed_solution="Bot que promete rentabilidad garantizada automáticamente.",
                target_customer="Inversores sin experiencia.",
                sector="trading",
            )
        )
        evaluation = container.pipeline.evaluate(opp.id, clear_existing=False)
        assert evaluation.decision == Decision.blocked
        assert any("riesgo" in b.lower() or "rentabilidad" in b.lower() for b in evaluation.blockers)
        assert evaluation.safety_score <= 15
    finally:
        container.close()


def test_medium_risk_does_not_block(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        opp = container.opportunities.create(
            OpportunityCreate(
                title="Servicio técnico de análisis de logs",
                problem="Análisis técnico de logs de MetaTrader sin prometer rentabilidad.",
                proposed_solution="Herramienta de diagnóstico de software, sin asesoramiento financiero.",
                target_customer="Desarrolladores MQL5 concreto.",
                sector="servicios técnicos MQL5",
            )
        )
        evaluation = container.pipeline.evaluate(opp.id, clear_existing=False)
        # Riesgos medios (tos_plataforma, asesoramiento) no bloquean por sí solos.
        assert not any("riesgo grave" in b.lower() for b in evaluation.blockers)
    finally:
        container.close()
