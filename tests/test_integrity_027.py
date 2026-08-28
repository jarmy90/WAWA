"""Regresiones de integridad de la iteración 027."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.core.container import build_container
from app.models.opportunity import OpportunityCreate
from tests.conftest import make_settings


def _dental(container):
    return container.opportunities.create(
        OpportunityCreate(
            title="Benchmark de tarifas de ortodoncia",
            problem="Las clínicas dentales comparan tarifas de ortodoncia con dificultad.",
            proposed_solution="Informe anónimo de estructura de oferta.",
            target_customer="Gerentes de clínicas dentales de 2 a 5 dentistas.",
            sector="servicios para clínicas dentales",
            source="test",
        )
    )


def test_dental_evaluation_never_contains_trading_context(tmp_path: Path):
    c = build_container(make_settings(tmp_path))
    try:
        opp = _dental(c)
        evaluation = c.pipeline.evaluate(opp.id, clear_existing=False)
        text = str(evaluation.model_dump()).lower()
        assert "mql5" not in text
        assert "metatrader" not in text
        assert "trading" not in text
    finally:
        c.close()


def test_mission_with_zero_evidence_does_not_change_score(tmp_path: Path):
    c = build_container(make_settings(tmp_path))
    try:
        mission = c.repos.discovery.save_mission({
            "mission_id": "integrity-mission-027",
            "kind": "DEMAND_REALITY_CHECK",
            "target": {},
            "export_payload": {},
            "status": "exported",
        })
        c.repos.discovery.save_mission_result(
            mission["mission_id"],
            {"raw": {}, "evidences": [], "competitors": [], "verified": False,
             "verification_notes": "BLOCKED_BY_CONNECTOR"},
        )
        assert c.repos.discovery.mission_results(mission["mission_id"])[0]["verified"] == 0
        assert c.repos.discovery.mission_results(mission["mission_id"])[0]["evidences"] == []
    finally:
        c.close()


def test_contaminated_dental_opportunity_is_rejected_before_evaluation(tmp_path: Path):
    c = build_container(make_settings(tmp_path))
    try:
        opp = c.opportunities.create(
            OpportunityCreate(
                title="Benchmark dental MQL5",
                problem="Problema dental de ortodoncia.",
                proposed_solution="Informe.",
                target_customer="Gerente de clínica dental.",
                sector="clínica dental trading MQL5",
                source="test",
            )
        )
        with pytest.raises(ValueError, match="Integridad bloqueada"):
            c.pipeline.evaluate(opp.id, clear_existing=False)
    finally:
        c.close()
