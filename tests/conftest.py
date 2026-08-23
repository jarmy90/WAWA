"""Fixtures comunes: configuración aislada, contenedor y cliente de prueba.

Cada test usa una base de datos SQLite temporal y directorios propios,
de modo que la suite es 100% offline y reproducible.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.container import AppContainer, build_container
from app.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def make_settings(tmp_path: Path, **overrides) -> Settings:
    base = dict(
        data_dir=tmp_path,
        database_path=tmp_path / "test.db",
        logs_dir=tmp_path / "logs",
        manual_research_dir=tmp_path / "manual_research",
        frontend_dir=FRONTEND_DIR,
        llm_provider="mock",
        free_mode=True,
        simulation_mode=True,
        daily_budget_usd=0.50,
        per_opportunity_budget_usd=0.20,
        max_deep_evaluations_per_day=5,
        max_upload_bytes=100_000,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def container(settings) -> AppContainer:
    c = build_container(settings)
    yield c
    c.close()


@pytest.fixture
def client(container):
    app = create_app(container)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def demo_client(settings):
    """Cliente con datos de demostración ya cargados."""
    container = build_container(settings)
    from app.workflows.demo import DemoSeeder

    DemoSeeder(container.settings, container.repos, container.pipeline).seed(evaluate=True)
    app = create_app(container)
    with TestClient(app) as c:
        yield c
    container.close()
