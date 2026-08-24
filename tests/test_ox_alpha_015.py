"""Ventana prioritaria OX Alpha (iteración 015).

Cubre: puerta determinista de identificación (OX_ALPHA_UNVERIFIED hasta que el
propietario verifique el slug contra el catálogo real), expiración 2026-08-27,
registro honesto por llamada en llm_call_log, ausencia NEUTRAL en fallo (nunca
mock silencioso ni salida sintética), límite diario, y regla de oro: la salida
del modelo NUNCA es evidencia (no toca proven_demand, evaluaciones ni grupos).
100% offline.
"""
from __future__ import annotations

from datetime import date, timedelta

import json
import pytest

from app.core.errors import ProviderUnavailableError
from app.core.ox_alpha import (
    ALLOWED_OUTPUT_LABELS,
    DEEP_TASKS,
    FORBIDDEN_OUTPUT_LABELS,
    OX_ALPHA_UNVERIFIED,
    build_reformulation_prompt,
    deep_task_gate,
    ox_alpha_status,
)
from app.providers.base import LLMResponse
from tests.conftest import make_settings

FUTURE = (date.today() + timedelta(days=5)).isoformat()
PAST = "2026-08-26"  # antes de hoy (2026-08-23 no; usar fecha ya pasada real)


def _enabled_settings(tmp_path, **overrides):
    base = dict(
        omniroute_enabled=True,
        ox_alpha_slug="test/ox-alpha",
        ox_alpha_expires_at=FUTURE,
    )
    base.update(overrides)
    return make_settings(tmp_path, **base)


# ---------------------------------------------------------------- puerta
def test_default_gateway_disabled_identity_unverified(tmp_path):
    s = make_settings(tmp_path)
    st = ox_alpha_status(s)
    assert st["state"] == "GATEWAY_DISABLED"
    assert st["identity"] == OX_ALPHA_UNVERIFIED
    assert st["can_use"] is False
    assert st["is_evidence"] is False


def test_slug_empty_or_auto_never_counts_as_ox_alpha(tmp_path):
    for slug in ("", "auto", "AUTO"):
        s = _enabled_settings(tmp_path, ox_alpha_slug=slug)
        st = ox_alpha_status(s)
        assert st["state"] == "SLUG_UNVERIFIED"
        assert st["identity"] == OX_ALPHA_UNVERIFIED
        assert st["can_use"] is False
        assert "No se declara uso de OX Alpha" in st["reason"] or "sin verificar" in st["reason"].lower()


def test_window_expiry_closes_gate(tmp_path):
    s = _enabled_settings(tmp_path, ox_alpha_expires_at="2026-08-27")
    st = ox_alpha_status(s, today=date(2026, 8, 28))
    assert st["state"] == "WINDOW_EXPIRED"
    assert st["can_use"] is False
    assert st["identity"] == "test/ox-alpha"  # identidad conocida, pero puerta cerrada


def test_verified_slug_within_window_available(tmp_path):
    s = _enabled_settings(tmp_path)
    st = ox_alpha_status(s)
    assert st["state"] == "AVAILABLE"
    assert st["can_use"] is True
    assert st["identity"] == "test/ox-alpha"


def test_invalid_task_never_uses_window(tmp_path):
    s = _enabled_settings(tmp_path)
    gate = deep_task_gate(s, "discovery")
    assert gate["can_use"] is False
    assert "deterministas" in gate["reason"]
    # Solo las P0 registradas entran por la ventana.
    assert set(DEEP_TASKS) == {"reformulation", "coherence_check", "red_team", "variation_comparison"}


def test_labels_honest_and_forbidden_absent():
    for forbidden in FORBIDDEN_OUTPUT_LABELS:
        assert forbidden not in ALLOWED_OUTPUT_LABELS


# ------------------------------------------------------------- servicio
@pytest.fixture()
def deep_container(tmp_path):
    from app.core.container import build_container

    container = build_container(_enabled_settings(tmp_path))
    yield container
    container.close()


def _stub_ok(container, structured):
    def fake_generate(prompt, **kwargs):
        assert kwargs.get("model") == "test/ox-alpha"  # slug EXACTO, nunca auto
        return LLMResponse(
            text=json.dumps(structured),
            structured=structured,
            model="test/ox-alpha",
            actual_model="upstream/real-model",
            method="omniroute (OpenAI-compatible)",
            cost_estimate_usd=0.0001,
            cost_method="estimated_api",
            reported_cost=None,
            cost_source="LOCAL_ESTIMATE",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            latency_ms=123,
            notes="hipótesis, nunca evidencia",
        )

    container.providers.omniroute.generate = fake_generate


def _noop_placeholder():
    pass


def test_blocked_before_call_logs_nothing_and_returns_no_result(deep_container):
    # Tarea NO reservada: bloqueo ANTES de llamar; nada registrado ni fabricado.
    result = deep_container.deep_reasoning.run_deep_task("classification", {"title": "x"})
    assert result["result"] is None
    assert result["can_use"] is False
    assert result["response_is_synthetic"] is False
    # Sin llamadas registradas (no hubo intento).
    assert len(deep_container.repos.llm_calls.list_recent(10)) == 0


def test_success_records_all_fields_and_labels_hypothesis(deep_container):
    structured = {"variants": [{"specific_name": "Benchmark tarifas clínicas"}]}
    _stub_ok(deep_container, structured)

    result = deep_container.deep_reasoning.run_deep_task(
        "reformulation", {"title": "Concepto abstracto"}, opportunity_id=None
    )
    assert result["status"] == "OK"
    assert result["used_model"] == "upstream/real-model"
    assert result["requested_model"] == "test/ox-alpha"
    assert result["routing_strategy"] == "omniroute-deep-priority"
    assert result["fallback_used"] is False or "fallback_used" not in result
    assert result["is_evidence"] is False
    assert result["output_label"] == "REFORMULACIÓN DE MODELO"
    for v in result["result"]["variants"]:
        assert v["provenance_label"] == "HIPÓTESIS SIN VERIFICAR"

    rows = deep_container.repos.llm_calls.list_recent(5)
    assert len(rows) == 1
    row = rows[0]
    for field in ("requested_model", "actual_model", "actual_provider", "routing_strategy",
                  "latency_ms", "cost_source", "billing_verified"):
        assert field in row
    assert row["requested_model"] == "test/ox-alpha"
    assert row["actual_model"] == "upstream/real-model"
    assert row["billing_verified"] is False
    assert row["fallback_used"] is False
    assert row["response_is_external"] is True
    assert row["response_is_synthetic"] is False
    assert row["prompt_tokens"] == 100


def test_failure_is_neutral_no_mock_substitution(deep_container):
    def failing_generate(prompt, **kwargs):
        raise ProviderUnavailableError("gateway caído", details={"provider": "omniroute"})

    deep_container.providers.omniroute.generate = failing_generate
    result = deep_container.deep_reasoning.run_deep_task("coherence_check", {"title": "x"})
    assert result["status"] == "UNAVAILABLE"
    assert result["result"] is None
    assert result["response_is_synthetic"] is False
    assert result["reason"].startswith("OX Alpha no disponible")
    assert "NEUTRAL" in result["reason"]

    rows = deep_container.repos.llm_calls.list_recent(5)
    assert len(rows) == 1
    row = rows[0]
    assert row["response_status"] == "error"
    assert row["fallback_used"] is False
    assert row["response_is_synthetic"] is False
    assert row["actual_model"] is None


def test_daily_limit_blocks_with_neutral_absence(deep_container, tmp_path):
    _stub_ok(deep_container, {"variants": []})
    limit = int(deep_container.settings.ox_alpha_daily_task_limit)
    for i in range(limit):
        deep_container.deep_reasoning.run_deep_task("red_team", {"title": f"c{i}"})
    over = deep_container.deep_reasoning.run_deep_task("red_team", {"title": "extra"})
    assert over["status"] == "DAILY_LIMIT_REACHED"
    assert over["result"] is None
    assert "neutral" in over["reason"].lower()


def test_daily_limit_configurable_to_zero_blocks_immediately(tmp_path):
    from app.core.container import build_container

    container = build_container(make_settings(
        tmp_path, omniroute_enabled=True, ox_alpha_slug="t/a",
        ox_alpha_expires_at=FUTURE, ox_alpha_daily_task_limit=0,
    ))
    try:
        res = container.deep_reasoning.run_deep_task("reformulation", {})
        assert res["status"] == "DAILY_LIMIT_REACHED"
    finally:
        container.close()


def test_model_output_never_touches_evidence_or_scores(deep_container, tmp_path):
    from app.models.opportunity import OpportunityCreate

    _stub_ok(deep_container, {
        "variants": [{
            "buyer": "Comprador inventado por el modelo",
            "expected_price_hypothesis": "999 USD (¡confirmadísimo!)",
            "proven_demand": 100,
        }]
    })
    opp = deep_container.opportunities.create(OpportunityCreate(
        title="Sin evidencia", problem="Problema descrito con detalle suficiente.",
        proposed_solution="Solución.", sector="t",
    ))
    before = deep_container.pipeline.evaluate(opp.id, clear_existing=False)
    # El pipeline ya deja su marcador honesto "DESCONOCIDO"; lo que NO puede
    # ocurrir es que la salida del modelo añada MÁS evidencia.
    evs_before = deep_container.repos.evidence.list_for(opp.id)
    n_evidence_before = len(evs_before)

    result = deep_container.deep_reasoning.run_deep_task(
        "reformulation", {"title": "Sin evidencia"}, opportunity_id=opp.id
    )
    assert result["status"] == "OK"

    after = deep_container.repos.evaluations.get(opp.id)
    evs_after = deep_container.repos.evidence.list_for(opp.id)
    assert len(evs_after) == n_evidence_before  # ninguna evidencia nueva
    assert after.demand_score <= 10  # proven_demand sigue en 0-ish: la salida NO sube demanda
    assert after.final_score < 60
    assert after.independent_evidence_count == 0


def test_reformulation_prompt_requires_concrete_brief_fields():
    prompt, schema = build_reformulation_prompt({"title": "x"})
    for field in ("buyer", "observable_problem", "test_in_48_hours", "first_distribution_channel"):
        assert field in prompt
    assert "3 y 5" in prompt  # entre 3 y 5 variantes realmente diferentes


# ---------------------------------------------------------------- API
def test_api_status_and_task_endpoints(client):
    r = client.get("/api/oxalpha/status")
    assert r.status_code == 200
    data = r.json()
    assert data["identity"] == OX_ALPHA_UNVERIFIED
    assert data["is_evidence"] is False
    assert data["ox_alpha_is_evidence"] is False

    payload = {"task": "reformulation", "concept": {"title": "x"}}
    r2 = client.post("/api/oxalpha/task", json=payload)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["status"] in ("GATEWAY_DISABLED", "SLUG_UNVERIFIED", "WINDOW_EXPIRED")
    assert d2["result"] is None

    r3 = client.post("/api/oxalpha/task", json={"task": "discovery", "concept": {}})
    assert r3.status_code == 200
    assert r3.json()["can_use"] is False

    r4 = client.post("/api/oxalpha/catalog-check", json={})
    assert r4.status_code == 200
    assert r4.json()["verified"] is False
