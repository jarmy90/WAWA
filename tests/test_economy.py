"""Economía simulada: ledger append-only, idempotencia, reversiones,
métricas deterministas, reconciliación y SAFE_PAUSE.

Cubre los 30 puntos obligatorios de la iteración 003 (varios de seguridad de
modos viven en test_engine_modes.py; aquí está la capa contable).
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.container import build_container
from app.core.errors import BudgetExceededError, ConflictError, ValidationError
from app.models.enums import LedgerStatus, OperatingMode
from app.models.ledger import ExpenseRequestIn, IncomeIn, LedgerEntry, SimulationStartIn
from tests.conftest import make_settings

HEX32 = "0" * 32


def _sim(payload: SimulationStartIn, container):
    return container.economy.start_simulation(payload)


def _start(container, capital: str = "100.00", daily: str | None = None, name: str = "Simulación de prueba") -> dict:
    return _sim(SimulationStartIn(initial_capital=capital, maximum_daily_spend=daily, simulation_name=name), container)


def _expense(container, amount: str, *, opportunity_id: str | None = None, experiment_id: str | None = None, key: str | None = None) -> dict:
    return container.economy.request_expense(
        ExpenseRequestIn(
            amount=amount,
            description=f"Gasto simulado de {amount}",
            opportunity_id=opportunity_id,
            experiment_id=experiment_id,
            idempotency_key=key,
        )
    )


def _income(container, amount: str, *, key: str | None = None) -> dict:
    return container.economy.record_income(
        IncomeIn(amount=amount, source_type="manual_simulation", description=f"Ingreso simulado de {amount}", idempotency_key=key)
    )


# ---------------------------------------------------------------------------
# 1-2. Capital inicial
# ---------------------------------------------------------------------------
def test_initial_capital_creation(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        result = _start(container, capital="50.00", name="Capital inicial")
        assert result["simulation_started"] is True
        assert result["simulated"] is True
        assert result["real_money_moved"] is False
        assert "SIMULACIÓN" in result["warning"]
        entry = result["entry"]
        assert entry["entry_type"] == "INITIAL_CAPITAL"
        assert entry["direction"] == "credit"
        assert entry["status"] == "CONFIRMED"
        assert Decimal(entry["amount"]) == Decimal("50.00")
        assert container.economy.is_active() is True
    finally:
        container.close()


def test_cannot_initialize_twice(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="50.00")
        with pytest.raises(ConflictError):
            _start(container, capital="999.00")  # no reinicia silenciosamente el ledger
        # El ledger sigue intacto con el capital original.
        assert container.repos.ledger.count() == 1
        sim = [e for e in container.repos.ledger.list(limit=10) if e.entry_type == "INITIAL_CAPITAL"][0]
        assert sim.amount == Decimal("50.00")
    finally:
        container.close()


# ---------------------------------------------------------------------------
# 3. Saldo derivado del ledger
# ---------------------------------------------------------------------------
def test_balance_derived_from_ledger(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="100.00")
        assert container.economy._accounting_balance() == Decimal("100.00")
        assert container.economy._available_balance() == Decimal("100.00")

        _income(container, "25.00")
        assert container.economy._accounting_balance() == Decimal("125.00")

        exp = _expense(container, "10.00")
        assert container.economy._accounting_balance() == Decimal("125.00")  # COMMITTED no afecta saldo contable
        assert container.economy._available_balance() == Decimal("115.00")  # sí reduce disponible

        container.economy.confirm_expense(exp["entry"]["id"])
        assert container.economy._accounting_balance() == Decimal("115.00")
        assert container.economy._available_balance() == Decimal("115.00")
    finally:
        container.close()


# ---------------------------------------------------------------------------
# 4-6. Decimal, redondeo, negativos, moneda
# ---------------------------------------------------------------------------
def test_decimal_rounding_half_up(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        entry = LedgerEntry(
            entry_type="SIMULATED_INCOME",
            direction="credit",
            amount="1.005",
            description="redondeo ROUND_HALF_UP",
            idempotency_key="key-redondeo-0001",
        )
        assert entry.amount == Decimal("1.01")
        assert isinstance(entry.amount, Decimal)
    finally:
        container.close()


def test_negative_amounts_rejected():
    with pytest.raises(PydanticValidationError):
        SimulationStartIn(initial_capital=-5, simulation_name="Negativo")
    with pytest.raises(PydanticValidationError):
        IncomeIn(amount="-1.00", source_type="manual_simulation", description="Ingreso negativo")
    with pytest.raises(PydanticValidationError):
        ExpenseRequestIn(amount=-1.00, description="Gasto negativo")


def test_other_currency_rejected(tmp_path):
    settings = make_settings(tmp_path)  # base_currency=USD
    container = build_container(settings)
    try:
        with pytest.raises(ValidationError) as exc:
            _sim(SimulationStartIn(initial_capital=50, currency="EUR", simulation_name="En euros"), container)
        assert "EUR" in str(exc.value)
        assert container.repos.ledger.count() == 0
    finally:
        container.close()


# ---------------------------------------------------------------------------
# 7-8. Idempotencia
# ---------------------------------------------------------------------------
def test_income_idempotency(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="100.00")
        first = _income(container, "10.00", key="income-clave-0001")
        second = _income(container, "10.00", key="income-clave-0001")
        assert first["created"] is True
        assert second["created"] is False
        assert second["entry"]["id"] == first["entry"]["id"]
        assert container.repos.ledger.count() == 2  # capital + 1 ingreso (no duplicado)
        # El ingreso confirmado NO incluye el capital inicial (financiación ≠ ingreso ganado).
        assert container.economy._confirmed_income() == Decimal("10.00")
        assert container.economy._accounting_balance() == Decimal("110.00")
    finally:
        container.close()


def test_expense_idempotency(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="100.00")
        first = _expense(container, "5.00", key="expense-clave-001")
        second = _expense(container, "5.00", key="expense-clave-001")
        assert first["created"] is True
        assert second["created"] is False
        assert second["entry"]["id"] == first["entry"]["id"]
        assert container.economy._available_balance() == Decimal("95.00")
    finally:
        container.close()


# ---------------------------------------------------------------------------
# 9-11. Gasto: comprometido / confirmado / rechazado
# ---------------------------------------------------------------------------
def test_expense_committed_then_confirmed(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="100.00")
        exp = _expense(container, "20.00")
        entry_id = exp["entry"]["id"]
        assert exp["status"] == "COMMITTED"
        assert container.repos.ledger.get(entry_id).status == LedgerStatus.committed.value
        assert container.economy._committed_expenses() == Decimal("20.00")
        assert container.economy._confirmed_expenses() == Decimal("0.00")

        container.economy.confirm_expense(entry_id)
        entry = container.repos.ledger.get(entry_id)
        assert entry.status == LedgerStatus.confirmed.value
        assert entry.confirmed_at is not None
        assert container.economy._committed_expenses() == Decimal("0.00")
        assert container.economy._confirmed_expenses() == Decimal("20.00")
    finally:
        container.close()


def test_expense_rejected_releases_commitment(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="100.00")
        exp = _expense(container, "20.00")
        container.economy.reject_expense(exp["entry"]["id"], reason="Gasto no justificado")
        entry = container.repos.ledger.get(exp["entry"]["id"])
        assert entry.status == LedgerStatus.rejected.value
        assert container.economy._committed_expenses() == Decimal("0.00")
        assert container.economy._confirmed_expenses() == Decimal("0.00")
        assert container.economy._available_balance() == Decimal("100.00")
    finally:
        container.close()


def test_confirm_reject_only_from_committed(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="100.00")
        income = _income(container, "5.00")
        with pytest.raises(ConflictError):
            container.economy.confirm_expense(income["entry"]["id"])  # no es gasto COMMITTED
    finally:
        container.close()


# ---------------------------------------------------------------------------
# 12-13. Reversión
# ---------------------------------------------------------------------------
def test_reversal_restores_balance_and_is_audited(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="100.00")
        exp = _expense(container, "30.00")
        entry_id = exp["entry"]["id"]
        container.economy.confirm_expense(entry_id)
        assert container.economy._accounting_balance() == Decimal("70.00")

        result = container.economy.reverse_entry(entry_id, reason="Asiento erróneo", actor="reviewer")
        assert result["real_money_moved"] is False
        # Original intacto pero marcado REVERSED; reversión vinculada.
        original = container.repos.ledger.get(entry_id)
        assert original.status == LedgerStatus.reversed.value
        reversal = container.repos.ledger.get(result["reversal_entry"]["id"])
        assert reversal.entry_type == "REVERSAL"
        assert reversal.direction == "credit"  # opuesta al gasto
        assert reversal.reversed_entry_id == entry_id
        assert reversal.amount == Decimal("30.00")
        # El saldo se reconstruye: 100 - 30 + 30 = 100.
        assert container.economy._accounting_balance() == Decimal("100.00")
        # Auditoría en decision_log.
        assert any(l.agent == "economy" and "Reversión" in l.output_summary for l in container.repos.decision_log.recent(20))
    finally:
        container.close()


def test_double_reversal_blocked(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="100.00")
        exp = _expense(container, "10.00")
        entry_id = exp["entry"]["id"]
        container.economy.confirm_expense(entry_id)
        container.economy.reverse_entry(entry_id, reason="Primera reversión")
        with pytest.raises(ConflictError):
            container.economy.reverse_entry(entry_id, reason="Segunda reversión")
        with pytest.raises(ConflictError):
            container.economy.reverse_entry(entry_id, reason="Tercera reversión")
        # Solo existe UNA entrada de reversión.
        reversals = [e for e in container.repos.ledger.list(limit=100) if e.entry_type == "REVERSAL"]
        assert len(reversals) == 1
    finally:
        container.close()


def test_reversal_of_reversal_blocked(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="100.00")
        exp = _expense(container, "10.00")
        entry_id = exp["entry"]["id"]
        container.economy.confirm_expense(entry_id)
        result = container.economy.reverse_entry(entry_id, reason="Reversión original")
        with pytest.raises(ConflictError):
            container.economy.reverse_entry(result["reversal_entry"]["id"], reason="Reversión de la reversión")
    finally:
        container.close()


# ---------------------------------------------------------------------------
# 14-17. Fondos y límites
# ---------------------------------------------------------------------------
def test_insufficient_funds(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="10.00")
        with pytest.raises(BudgetExceededError):
            _expense(container, "20.00")
    finally:
        container.close()


def test_daily_limit(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="100.00", daily="5.00")
        _expense(container, "3.00")
        with pytest.raises(BudgetExceededError) as exc:
            _expense(container, "3.00")  # 3 + 3 > 5
        assert "diario" in str(exc.value)
    finally:
        container.close()


def test_per_opportunity_limit(tmp_path):
    settings = make_settings(tmp_path)  # per_opportunity_budget_usd=0.20
    container = build_container(settings)
    try:
        _start(container, capital="100.00")
        _expense(container, "0.15", opportunity_id=HEX32)
        with pytest.raises(BudgetExceededError) as exc:
            _expense(container, "0.15", opportunity_id=HEX32)  # 0.30 > 0.20
        assert "oportunidad" in str(exc.value)
    finally:
        container.close()


def test_per_experiment_limit(tmp_path):
    settings = make_settings(tmp_path, max_per_experiment_usd=0.5)
    container = build_container(settings)
    try:
        _start(container, capital="100.00")
        _expense(container, "0.40", experiment_id=HEX32)
        with pytest.raises(BudgetExceededError) as exc:
            _expense(container, "0.40", experiment_id=HEX32)  # 0.80 > 0.50
        assert "experimento" in str(exc.value)
    finally:
        container.close()


# ---------------------------------------------------------------------------
# 18-20. Runway y métricas sin denominador
# ---------------------------------------------------------------------------
def test_runway_null_without_history(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="100.00")
        metrics = container.economy.metrics()
        assert metrics["runway_days"]["value"] is None
        assert metrics["runway_days"]["data_quality"] == "unknown"
        assert "historial" in (metrics["runway_days"]["explanation"] or "")
        assert metrics["daily_burn_rate"]["value"] is None
        assert metrics["survival_status"]["status"] == "UNKNOWN"
    finally:
        container.close()


def test_runway_with_confirmed_expenses(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="100.00")
        exp = _expense(container, "10.00")
        container.economy.confirm_expense(exp["entry"]["id"])
        metrics = container.economy.metrics()
        # 1 día de historial: burn = 10/día; disponible = 90 → runway = 9.
        assert metrics["daily_burn_rate"]["value"] == 10.0
        assert metrics["runway_days"]["value"] == 9.0
        assert metrics["survival_status"]["status"] == "HEALTHY"
    finally:
        container.close()


def test_metrics_no_denominator_returns_null(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="100.00")
        metrics = container.economy.metrics()
        # Sin ingresos: margen desconocido (no 0 engañoso).
        assert metrics["gross_margin"]["value"] is None
        assert metrics["gross_margin"]["data_quality"] == "unknown"
        # Sin costes atribuidos: coste por oportunidad desconocido.
        assert metrics["cost_per_opportunity"]["value"] is None
        assert metrics["cost_per_experiment"]["value"] is None
        # Uso de presupuesto con capital definido y sin gastos: 0 real (capital existe).
        assert metrics["budget_utilization"]["value"] == 0.0
    finally:
        container.close()


# ---------------------------------------------------------------------------
# 21-22. Reconciliación
# ---------------------------------------------------------------------------
def test_reconciliation_ok(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="100.00")
        _income(container, "20.00")
        exp = _expense(container, "15.00")
        container.economy.confirm_expense(exp["entry"]["id"])
        result = container.economy.reconcile()
        assert result["reconciled"] is True
        assert result["issues"] == []
        assert result["triggered_pause"] is False
        assert result["summary"]["available_balance"] == "105.00"
        last = container.repos.ledger.last_reconciliation()
        assert last["reconciled"] is True
        assert container.engine.status()["mode"] == OperatingMode.development_and_review.value
    finally:
        container.close()


def test_reconciliation_detects_inconsistency_and_pauses(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="100.00")
        # Inyectamos un asiento inválido directamente (REVERSAL sin original).
        container.repos.ledger.conn.execute(
            """INSERT INTO ledger_entries
               (id, entry_type, direction, amount, currency, status, source_type, description,
                idempotency_key, operating_mode, created_by, created_at, confirmed_at, reversed_entry_id, metadata)
               VALUES (?, 'REVERSAL', 'credit', '1.00', 'USD', 'CONFIRMED', 'bad', 'Reversión huérfana',
                       'orphan-reversal-001', 'development_and_review', 'system', ?, ?, ?, '{}')""",
            ("b" * 32, "2026-08-23T10:00:00+00:00", "2026-08-23T10:00:01+00:00", "0" * 32),
        )
        container.repos.ledger.conn.commit()

        result = container.economy.reconcile()
        assert result["reconciled"] is False
        assert any("REVERSAL" in i for i in result["issues"])
        assert result["triggered_pause"] is True
        # SAFE_PAUSE auditado: transición + evento crítico + bloqueo de gasto.
        status = container.engine.status()
        assert status["mode"] == OperatingMode.safe_pause.value
        assert any(e.event_type == "critical" for e in container.engine.events(20))
        last = container.repos.ledger.last_reconciliation()
        assert last["reconciled"] is False
    finally:
        container.close()


# ---------------------------------------------------------------------------
# 23-25. SAFE_PAUSE y activación de producción
# ---------------------------------------------------------------------------
def test_startup_safe_pause_with_inconsistent_ledger(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    # Corrompemos el ledger desde el primer contenedor.
    container.repos.ledger.conn.execute(
        """INSERT INTO ledger_entries
           (id, entry_type, direction, amount, currency, status, source_type, description,
            idempotency_key, operating_mode, created_by, created_at, confirmed_at, reversed_entry_id, metadata)
           VALUES (?, 'REVERSAL', 'credit', '1.00', 'USD', 'CONFIRMED', 'bad', 'Reversión huérfana',
                   'orphan-startup-001', 'development_and_review', 'system', ?, ?, ?, '{}')""",
        ("c" * 32, "2026-08-23T10:00:00+00:00", "2026-08-23T10:00:01+00:00", "0" * 32),
    )
    container.repos.ledger.conn.commit()
    container.close()

    # Reconstrucción del servicio: el arranque detecta la inconsistencia → SAFE_PAUSE.
    container2 = build_container(settings)
    try:
        status = container2.engine.status()
        assert status["mode"] == OperatingMode.safe_pause.value
        assert any("ledger inconsistente" in (t.reason or "") for t in container2.engine.transitions())
        assert any(e.event_type == "critical" for e in container2.engine.events(20))
    finally:
        container2.close()


def test_production_blocked_through_api_even_with_key(client):
    resp = client.post(
        "/api/engine/mode",
        json={"mode": "autonomous_production", "activation_key": "cualquier-clave", "reason": "intento"},
    )
    assert resp.status_code == 409  # ModeBlockedError (capacidad de producción false)
    assert resp.json()["error"]["code"] == "mode_blocked"
    status = client.get("/api/engine/status").json()
    assert status["mode"] == "development_and_review"
    assert status["production_enabled"] is False
    assert status["production_capability_available"] is False


# ---------------------------------------------------------------------------
# 26-27. API y dashboard
# ---------------------------------------------------------------------------
def test_api_marks_everything_simulated(client):
    resp = client.post(
        "/api/economy/simulation/start",
        json={"initial_capital": 100, "currency": "USD", "simulation_name": "Simulación API"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["simulated"] is True
    assert body["real_money_moved"] is False

    status = client.get("/api/economy/status").json()
    assert status["simulated"] is True
    assert status["real_money_moved"] is False
    assert status["simulation_active"] is True
    assert status["warning"] == "SIMULACIÓN — NO REPRESENTA DINERO REAL"

    ledger = client.get("/api/economy/ledger").json()
    assert ledger["simulated"] is True
    assert ledger["real_money_moved"] is False
    assert ledger["count"] == 1

    metrics = client.get("/api/economy/metrics").json()
    assert metrics["simulated"] is True
    assert metrics["initial_capital"]["value"] == 100.0
    assert metrics["available_balance"]["value"] == 100.0


def test_dashboard_integrates_economy(client):
    # El frontend incluye la sección económica simulada y la API responde.
    resp = client.get("/")
    assert resp.status_code == 200
    # Vista Economía de la iteración 012 (la economía simulada vive en su vista).
    assert 'id="view-economy"' in resp.text
    assert 'id="economy-info"' in resp.text
    assert "SIMULADA" in resp.text
    assert "SIMULACIÓN" in resp.text
    assert client.get("/api/economy/status").status_code == 200
    assert client.get("/api/economy/metrics").status_code == 200
    assert client.get("/api/economy/ledger").status_code == 200


def test_api_expense_confirm_reject_reverse_flow(client):
    """Los endpoints HTTP de confirm/reject/reverse resuelven el id por ruta
    (regresión del dependiente `valid_entry_id`)."""
    r = client.post("/api/economy/simulation/start", json={"initial_capital": 100, "simulation_name": "Flujo API"})
    assert r.status_code == 200

    r = client.post("/api/economy/expense/request", json={"amount": 10, "description": "Gasto A"})
    assert r.status_code == 200
    entry_id = r.json()["entry"]["id"]
    r = client.post(f"/api/economy/expense/{entry_id}/confirm")
    assert r.status_code == 200
    assert r.json()["status"] == "CONFIRMED"
    assert r.json()["simulated"] is True
    assert r.json()["real_money_moved"] is False

    r = client.post("/api/economy/expense/request", json={"amount": 5, "description": "Gasto B"})
    entry_b = r.json()["entry"]["id"]
    r = client.post(f"/api/economy/expense/{entry_b}/reject")
    assert r.status_code == 200
    assert r.json()["status"] == "REJECTED"

    r = client.post(f"/api/economy/ledger/{entry_id}/reverse", json={"reason": "Corrección por API", "actor": "reviewer"})
    assert r.status_code == 200
    assert r.json()["reversed_entry_id"] == entry_id
    assert r.json()["real_money_moved"] is False
    # El saldo vuelve a 100 (10 gastado - 10 revertido).
    metrics = client.get("/api/economy/metrics").json()
    assert metrics["available_balance"]["value"] == 100.0


def test_economy_endpoints_blocked_in_safe_pause(client):
    client.post("/api/engine/mode", json={"mode": "safe_pause", "reason": "mantenimiento"})
    resp = client.post(
        "/api/economy/simulation/start",
        json={"initial_capital": 100, "simulation_name": "Bloqueada"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "mode_blocked"


# ---------------------------------------------------------------------------
# 29-30. Persistencia y flujo completo
# ---------------------------------------------------------------------------
def test_economy_persists_across_restart(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        _start(container, capital="100.00", name="Persistente")
        _income(container, "25.00")
        exp = _expense(container, "10.00")
        container.economy.confirm_expense(exp["entry"]["id"])
    finally:
        container.close()

    container2 = build_container(settings)  # reinicio del servicio
    try:
        assert container2.economy.is_active() is True
        assert container2.repos.ledger.count() == 3
        metrics = container2.economy.metrics()
        assert metrics["available_balance"]["value"] == 115.0
        assert metrics["confirmed_income"]["value"] == 25.0  # solo ingreso ganado
        assert metrics["confirmed_expenses"]["value"] == 10.0
        # Reconstrucción idéntica tras reinicio → mismas métricas.
        assert metrics["accounting_balance"]["value"] == 115.0
    finally:
        container2.close()


def test_full_simulated_economic_flow(tmp_path):
    """Flujo económico simulado completo, idéntico a la validación final
    manual: capital → ingreso → gasto (request/confirm) → verificación →
    reconciliación → persistencia."""
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        start = _start(container, capital="50.00", daily="10.00", name="Ciclo completo")
        assert start["simulation_started"] is True

        inc = _income(container, "15.00", key="flow-income-0001")
        assert inc["created"] is True
        # Idempotente: reintento no duplica.
        assert _income(container, "15.00", key="flow-income-0001")["created"] is False

        exp = _expense(container, "8.00", key="flow-expense-0001")
        assert exp["status"] == "COMMITTED"
        assert container.economy._available_balance() == Decimal("57.00")  # 65 - 8
        container.economy.confirm_expense(exp["entry"]["id"])
        assert container.economy._available_balance() == Decimal("57.00")
        assert container.economy._accounting_balance() == Decimal("57.00")

        metrics = container.economy.metrics()
        assert metrics["available_balance"]["value"] == 57.0
        assert metrics["confirmed_income"]["value"] == 15.0  # solo ingreso ganado (excluye capital)
        assert metrics["initial_capital"]["value"] == 50.0
        assert metrics["confirmed_expenses"]["value"] == 8.0
        assert metrics["survival_status"]["status"] in ("HEALTHY", "WATCH")

        reconciliation = container.economy.reconcile()
        assert reconciliation["reconciled"] is True
        assert reconciliation["triggered_pause"] is False

        # Ningún dinero real se mueve: los asientos son simulados.
        assert all(
            (e.metadata or {}).get("simulated") is True for e in container.repos.ledger.list(limit=100)
        )
    finally:
        container.close()
