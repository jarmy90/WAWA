"""Exportación JSON y Markdown."""
from __future__ import annotations

import json

from app.core.container import build_container
from app.models.opportunity import OpportunityCreate
from tests.conftest import make_settings


def _seeded_container(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    opp = container.opportunities.create(
        OpportunityCreate(
            title="Oportunidad exportable",
            problem="Problema con evidencias para exportar y documentar.",
            proposed_solution="Solución exportable.",
            target_customer="Cliente concreto.",
            sector="pruebas",
        )
    )
    container.pipeline.evaluate(opp.id, clear_existing=False)
    return container, opp.id


def test_export_json_complete(tmp_path):
    container, opp_id = _seeded_container(tmp_path)
    try:
        data = container.exports.export_json(opp_id)
        assert data["schema_version"] == "1.0"
        assert data["opportunity"]["id"] == opp_id
        assert isinstance(data["evidences"], list)
        assert isinstance(data["competitors"], list)
        assert data["evaluation"] is not None
        assert data["evaluation"]["final_score"] >= 0
        assert isinstance(data["decision_log"], list)
        # Debe serializarse a JSON sin errores.
        json.dumps(data)
    finally:
        container.close()


def test_export_markdown_contains_sections(tmp_path):
    container, opp_id = _seeded_container(tmp_path)
    try:
        md = container.exports.export_markdown(opp_id)
        for section in ("# ", "## Problema", "## Puntuación", "## Evidencias", "## Competidores"):
            assert section in md
    finally:
        container.close()


def test_export_markdown_roundtrip_fields(tmp_path):
    container, opp_id = _seeded_container(tmp_path)
    try:
        data = container.exports.export_json(opp_id)
        md = container.exports.export_markdown(opp_id)
        ev = data["evaluation"]
        assert f"{ev['final_score']}" in md
        assert ev["decision"] in md
    finally:
        container.close()


def test_export_unknown_opportunity_raises(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        from app.core.errors import NotFoundError

        try:
            container.exports.export_json("0" * 32)
            assert False, "debería lanzar NotFoundError"
        except NotFoundError:
            pass
    finally:
        container.close()
