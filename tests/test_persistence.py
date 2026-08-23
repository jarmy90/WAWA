"""Persistencia en SQLite: los datos sobreviven a reconexiones."""
from __future__ import annotations

import sqlite3

from app.core.container import build_container
from app.models.opportunity import OpportunityCreate
from tests.conftest import make_settings


def test_data_survives_reconnect(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    opp = container.opportunities.create(
        OpportunityCreate(
            title="Persistente",
            problem="Problema que debe sobrevivir a reconexiones de base de datos.",
            proposed_solution="Solución.",
            target_customer="Cliente.",
            sector="pruebas",
        )
    )
    opp_id = opp.id
    container.pipeline.evaluate(opp.id, clear_existing=False)
    container.close()

    # Nueva conexión al mismo archivo SQLite.
    container2 = build_container(settings)
    try:
        reloaded = container2.opportunities.get(opp_id)
        assert reloaded is not None
        assert reloaded.title == "Persistente"
        evaluation = container2.repos.evaluations.get(opp_id)
        assert evaluation is not None
        assert container2.repos.evidence.count_for(opp_id) >= 1
        assert container2.repos.decision_log.list_for(opp_id)
    finally:
        container2.close()


def test_schema_initialized_automatically(tmp_path):
    settings = make_settings(tmp_path)
    build_container(settings).close()
    conn = sqlite3.connect(settings.database_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    for expected in ("opportunities", "evidence", "competitors", "evaluations", "experiments", "decision_log", "costs"):
        assert expected in tables


def test_evaluation_replaced_on_reevaluate_but_log_kept(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        opp = container.opportunities.create(
            OpportunityCreate(
                title="Reevaluación",
                problem="Problema para probar que la reevaluación sustituye la evaluación anterior.",
                proposed_solution="Solución.",
                target_customer="Cliente.",
                sector="pruebas",
            )
        )
        container.pipeline.evaluate(opp.id, clear_existing=False)
        n_logs_before = len(container.repos.decision_log.list_for(opp.id))
        container.pipeline.evaluate(opp.id, clear_existing=False)
        n_logs_after = len(container.repos.decision_log.list_for(opp.id))
        assert n_logs_after > n_logs_before  # el log es append-only
    finally:
        container.close()
