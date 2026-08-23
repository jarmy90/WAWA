"""BudgetGuard: límites diarios, por oportunidad, evaluaciones profundas y modos."""
from __future__ import annotations

import pytest

from app.core.container import build_container
from app.core.errors import BudgetExceededError
from tests.conftest import make_settings


def test_free_mode_never_blocks(tmp_path):
    settings = make_settings(tmp_path, free_mode=True, simulation_mode=False, daily_budget_usd=0.0)
    container = build_container(settings)
    try:
        container.budget.spend(action="test", estimated_usd=0.5)  # gasta más del "límite" sin bloquear
        assert container.budget.status()["daily"]["spent"] > 0
    finally:
        container.close()


def test_simulation_mode_never_blocks_but_records(tmp_path):
    settings = make_settings(tmp_path, free_mode=False, simulation_mode=True, daily_budget_usd=0.0)
    container = build_container(settings)
    try:
        record = container.budget.spend(action="test", estimated_usd=0.2)
        assert record.simulation is True
        assert record.blocked is False
        assert container.budget.status()["daily"]["reached"] is False  # nunca marca límite en simulación
    finally:
        container.close()


def test_daily_budget_blocks_in_strict_mode(tmp_path):
    settings = make_settings(
        tmp_path,
        free_mode=False,
        simulation_mode=False,
        daily_budget_usd=1.0,
        per_opportunity_budget_usd=10.0,
    )
    container = build_container(settings)
    try:
        container.budget.spend(action="a", estimated_usd=0.6)
        container.budget.spend(action="b", estimated_usd=0.4)
        with pytest.raises(BudgetExceededError):
            container.budget.spend(action="c", estimated_usd=0.1)
        assert container.budget.status()["daily"]["reached"] is True
    finally:
        container.close()


def test_per_opportunity_budget_blocks(tmp_path):
    settings = make_settings(
        tmp_path,
        free_mode=False,
        simulation_mode=False,
        daily_budget_usd=100.0,
        per_opportunity_budget_usd=1.0,
    )
    container = build_container(settings)
    try:
        container.budget.spend(action="a", opportunity_id="opp1", estimated_usd=0.7)
        container.budget.spend(action="b", opportunity_id="opp1", estimated_usd=0.3)
        with pytest.raises(BudgetExceededError):
            container.budget.spend(action="c", opportunity_id="opp1", estimated_usd=0.1)
        # Otra oportunidad no se ve afectada.
        container.budget.spend(action="d", opportunity_id="opp2", estimated_usd=0.1)
    finally:
        container.close()


def test_max_deep_evaluations_per_day(tmp_path):
    settings = make_settings(
        tmp_path,
        free_mode=False,
        simulation_mode=False,
        daily_budget_usd=100.0,
        per_opportunity_budget_usd=100.0,
        max_deep_evaluations_per_day=2,
    )
    container = build_container(settings)
    try:
        container.budget.guard_deep_evaluation("opp1")
        container.budget.guard_deep_evaluation("opp2")
        assert container.budget.status()["deep_evaluations"]["today"] == 2
        with pytest.raises(BudgetExceededError):
            container.budget.guard_deep_evaluation("opp3")
    finally:
        container.close()


def test_manual_lock_blocks(tmp_path):
    settings = make_settings(tmp_path, free_mode=True)
    container = build_container(settings)
    try:
        container.budget.lock()
        with pytest.raises(BudgetExceededError):
            container.budget.spend(action="x", estimated_usd=0.0)
        container.budget.unlock()
        container.budget.spend(action="y", estimated_usd=0.0)
    finally:
        container.close()


def test_costs_recorded_per_action(tmp_path):
    settings = make_settings(tmp_path, free_mode=True)
    container = build_container(settings)
    try:
        container.budget.spend(action="agent:scout", provider="mock", estimated_usd=0.0, cost_method="zero (offline)")
        container.budget.spend(action="agent:researcher", provider="mock", estimated_usd=0.0, cost_method="zero (offline)")
        recent = container.budget.status()["recent"]
        assert {r["action"] for r in recent} >= {"agent:scout", "agent:researcher"}
        assert all(r["cost_method"] for r in recent)  # método siempre indicado
    finally:
        container.close()
