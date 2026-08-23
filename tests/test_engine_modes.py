"""Motor de operación: modos, activación deliberada, guardas y auditoría."""
from __future__ import annotations

import pytest

from app.core.container import build_container
from app.core.errors import ModeBlockedError
from app.models.enums import EngineState, OperatingMode
from tests.conftest import make_settings


def test_default_mode_is_development(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        status = container.engine.status()
        assert status["mode"] == OperatingMode.development_and_review.value
        assert status["engine_state"] == EngineState.researching.value
        assert status["production_enabled"] is False
        assert status["production_activatable"] is False  # sin clave configurada
    finally:
        container.close()


def test_production_cannot_activate_without_key(tmp_path):
    settings = make_settings(tmp_path)  # engine_activation_key=None
    container = build_container(settings)
    try:
        with pytest.raises(ModeBlockedError):
            container.engine.set_mode(OperatingMode.autonomous_production, reason="test")
    finally:
        container.close()


def test_production_blocked_by_capability_even_with_key(tmp_path):
    """Iteración 003: la clave ya no basta; la capacidad de producción es
    una regla explícita (production_capability_available=false)."""
    settings = make_settings(tmp_path, engine_activation_key="clave-secreta-del-propietario")
    container = build_container(settings)
    try:
        with pytest.raises(ModeBlockedError) as exc:
            container.engine.set_mode(OperatingMode.autonomous_production, activation_key="clave-secreta-del-propietario")
        assert "no implementada" in str(exc.value) or "not implemented" in str(exc.value) or "bloqueado" in str(exc.value).lower()
        assert container.engine.status()["production_enabled"] is False
    finally:
        container.close()


def test_production_activatable_only_with_capability_and_key(tmp_path):
    """Si el propietario declara la capacidad Y da la clave, la activación es
    posible (mecanismo probado); por defecto la capacidad es false."""
    settings = make_settings(
        tmp_path,
        engine_activation_key="clave-secreta-del-propietario",
        production_capability_available=True,
    )
    container = build_container(settings)
    try:
        container.engine.set_mode(OperatingMode.autonomous_production, activation_key="clave-secreta-del-propietario")
        assert container.engine.status()["mode"] == OperatingMode.autonomous_production.value
        transitions = container.engine.transitions()
        assert any(t.to_mode == OperatingMode.autonomous_production.value for t in transitions)
    finally:
        container.close()


def test_env_cannot_activate_production_directly(tmp_path):
    """Una variable de entorno NUNCA activa producción: arranca en SAFE_PAUSE
    con motivo auditable (regla de capacidad)."""
    settings = make_settings(tmp_path, operating_mode="autonomous_production")
    container = build_container(settings)
    try:
        status = container.engine.status()
        assert status["mode"] == OperatingMode.safe_pause.value
        assert status["production_enabled"] is False
        assert status["production_capability_available"] is False
        # Transición y evento crítico registrados.
        assert any(t.to_mode == OperatingMode.safe_pause.value for t in container.engine.transitions())
        assert any(e.event_type == "critical" for e in container.engine.events(20))
    finally:
        container.close()


def test_env_can_arm_production_with_preconditions(tmp_path):
    """La variable de entorno puede, como máximo, llevar a PRODUCTION_ARMED
    si las precondiciones económicas se cumplen."""
    settings = make_settings(
        tmp_path,
        operating_mode="production_armed",
        capital_total_usd=50.0,
        base_currency="USD",
        max_daily_spend_usd=2.0,
    )
    container = build_container(settings)
    try:
        status = container.engine.status()
        assert status["mode"] == OperatingMode.production_armed.value
        assert status["production_enabled"] is False
        # PRODUCTION_ARMED bloquea gasto real (coste > 0).
        with pytest.raises(ModeBlockedError):
            container.budget.spend(action="test", estimated_usd=0.01)
    finally:
        container.close()


def test_env_armed_without_capital_goes_safe_pause(tmp_path):
    """Arranque con PRODUCTION_ARMED sin capital/moneda/presupuesto → SAFE_PAUSE."""
    settings = make_settings(tmp_path, operating_mode="production_armed", capital_total_usd=0.0)
    container = build_container(settings)
    try:
        status = container.engine.status()
        assert status["mode"] == OperatingMode.safe_pause.value
        assert any("capital" in (t.reason or "").lower() for t in container.engine.transitions())
    finally:
        container.close()


def test_safe_pause_blocks_spending(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        container.engine.set_mode(OperatingMode.safe_pause, reason="mantenimiento")
        with pytest.raises(ModeBlockedError):
            container.budget.spend(action="test", estimated_usd=0.0)
        # Reversible.
        container.engine.set_mode(OperatingMode.development_and_review, reason="fin del mantenimiento")
        container.budget.spend(action="test", estimated_usd=0.0)
        assert container.engine.status()["mode"] == OperatingMode.development_and_review.value
    finally:
        container.close()


def test_safe_pause_blocks_deep_evaluation(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        from app.models.opportunity import OpportunityCreate

        opp = container.opportunities.create(
            OpportunityCreate(title="Pausado", problem="Problema de prueba con longitud suficiente.", proposed_solution="S.", sector="t")
        )
        container.engine.set_mode(OperatingMode.safe_pause, reason="test")
        with pytest.raises(ModeBlockedError):
            container.pipeline.evaluate(opp.id, clear_existing=False)
    finally:
        container.close()


def test_shadow_mode_blocks_real_spend_but_allows_zero_cost(tmp_path):
    settings = make_settings(tmp_path, free_mode=False, simulation_mode=False, daily_budget_usd=100.0)
    container = build_container(settings)
    try:
        container.engine.set_mode(OperatingMode.shadow_mode, reason="shadow test")
        with pytest.raises(ModeBlockedError):
            container.budget.spend(action="gemini", estimated_usd=0.01)
        container.budget.spend(action="mock", estimated_usd=0.0)  # coste cero permitido
    finally:
        container.close()


def test_safe_shutdown_blocks_everything(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        container.engine.set_engine_state(EngineState.safe_shutdown, reason="cierre del ciclo")
        with pytest.raises(ModeBlockedError):
            container.budget.spend(action="x", estimated_usd=0.0)
        with pytest.raises(ModeBlockedError):
            container.engine.set_mode(OperatingMode.autonomous_production, activation_key="cualquiera")
        # Aún se puede consultar el estado (modo lectura).
        assert container.engine.status()["engine_state"] == EngineState.safe_shutdown.value
    finally:
        container.close()


def test_engine_state_transitions_are_logged(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        container.engine.set_engine_state(EngineState.researching, reason="nuevo problema", rule="workflow")
        container.engine.set_engine_state(EngineState.experimenting, reason="experimento lanzado", rule="workflow")
        transitions = container.engine.transitions()
        states = [t.decision for t in transitions]
        assert EngineState.experimenting.value in states
        assert all(t.rule for t in transitions)
    finally:
        container.close()


def test_events_feed_and_heartbeat(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        container.engine.record_event(event_type="agent:researcher", summary="Ha contrastado demanda.")
        container.engine.record_event(event_type="agent:judge", summary="Ha puntuado la oportunidad.")
        container.engine.heartbeat(task="revisando evidencias", last_result="ok")
        status = container.engine.status()
        assert status["counts"]["events"] == 2
        assert status["heartbeat_at"] is not None
        feed = container.engine.events(5)
        assert feed[0].summary == "Ha puntuado la oportunidad."  # más reciente primero
    finally:
        container.close()


def test_pipeline_records_activity_events(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        from app.models.opportunity import OpportunityCreate

        opp = container.opportunities.create(
            OpportunityCreate(
                title="Actividad",
                problem="Problema de prueba para el timeline con suficiente detalle.",
                proposed_solution="S.",
                target_customer="Cliente.",
                sector="pruebas",
            )
        )
        container.pipeline.evaluate(opp.id, clear_existing=False)
        events = container.engine.events(50)
        agents = {e.event_type for e in events}
        assert "agent:researcher" in agents
        assert "agent:judge" in agents
    finally:
        container.close()
