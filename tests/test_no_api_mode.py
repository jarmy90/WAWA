"""Modo sin API: el sistema funciona completo sin ninguna clave."""
from __future__ import annotations

from app.core.container import build_container
from app.models.opportunity import OpportunityCreate
from tests.conftest import make_settings


def test_auto_provider_uses_mock_without_key(tmp_path):
    settings = make_settings(tmp_path, llm_provider="auto", gemini_api_key=None)
    container = build_container(settings)
    try:
        provider = container.providers.resolve_primary()
        assert provider.name == "mock"
    finally:
        container.close()


def test_discover_and_evaluate_offline(tmp_path):
    settings = make_settings(tmp_path, llm_provider="auto", gemini_api_key=None)
    container = build_container(settings)
    try:
        created = container.pipeline.discover(
            "Los traders de MQL5 no tienen una forma barata de auditar sus Expert Advisors antes de ejecutarlos con dinero real.",
            sector_hint="servicios técnicos para trading algorítmico / MQL5",
            source="test",
        )
        assert created, "El Scout debería crear oportunidades en modo offline"
        for opp in created:
            evaluation = container.pipeline.evaluate(opp.id, clear_existing=False)
            assert 0 <= evaluation.final_score <= 100
            assert evaluation.decision.value  # alguna decisión válida
    finally:
        container.close()


def test_scout_is_deterministic(tmp_path):
    problem = "Los traders no saben por qué su EA rinde distinto en backtest que en demo."

    container_a = build_container(make_settings(tmp_path / "a"))
    container_b = build_container(make_settings(tmp_path / "b"))
    try:
        a = container_a.pipeline.discover(problem, source="test")
        b = container_b.pipeline.discover(problem, source="test")
        assert [o.title for o in a] == [o.title for o in b]
        assert len(a) >= 1
    finally:
        container_a.close()
        container_b.close()


def test_duplicates_are_deduplicated(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        problem = "Los traders MQL5 necesitan auditoría automática de sus Expert Advisors."
        first = container.pipeline.discover(problem, source="test")
        second = container.pipeline.discover(problem, source="test")
        # La segunda ronda no debe crear duplicados (mismo título normalizado).
        assert len(second) == 0
        assert len(first) >= 1
    finally:
        container.close()


def test_pipeline_never_invents_external_data(tmp_path):
    """En modo offline, los datos externos quedan marcados como desconocidos."""
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        opp = container.opportunities.create(
            OpportunityCreate(
                title="Sin datos externos",
                problem="Problema genérico sin mención de plataformas ni datos.",
                proposed_solution="Servicio digital.",
                target_customer=None,
                sector="genérico",
            )
        )
        evaluation = container.pipeline.evaluate(opp.id, clear_existing=False)
        evidences = container.repos.evidence.list_for(opp.id)
        # Ninguna evidencia 'real' (todas son marcadores de desconocido del mock).
        real = [e for e in evidences if not e.method.startswith("mock")]
        assert real == []
        # Y el resultado lo refleja: bloqueada por falta de evidencia.
        assert any("evidencia" in b.lower() for b in evaluation.blockers)
    finally:
        container.close()
