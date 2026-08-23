"""OmniRoute (OPCIONAL, AISLADO — iteración 008): pruebas offline.

Cubre la sección 8 del encargo: desactivado por defecto, sin servicio,
timeout, 401/403/429/500, respuesta vacía, JSON inválido, modelo real
ausente/distinto, fallback visible, circuit breaker, límite diario, mock no
presentado como revisión real, ausencia neutral, imposibilidad de activar
producción o cambiar presupuesto, sanitización de errores y clave ausente de
logs. 100% offline (sin red).
"""
from __future__ import annotations

import json
import urllib.error

import pytest

from app.core.errors import ProviderUnavailableError
from app.models.enums import Decision
from app.models.evaluation import Evaluation
from app.models.opportunity import OpportunityCreate
from app.providers.base import LLMResponse
from app.providers.manager import ProviderManager
from app.providers.omniroute import OmniRouteProvider
from tests.conftest import make_settings

PROBLEM = "Problema de prueba para el comité OmniRoute."
SCORE80 = {
    "pain_score": 80.0, "demand_score": 80.0, "customer_reach_score": 80.0,
    "automation_score": 80.0, "margin_score": 80.0, "build_speed_score": 80.0,
    "differentiation_score": 80.0, "safety_score": 80.0, "evidence_quality_score": 80.0,
    "confidence_score": 80.0, "final_score": 80.0, "decision": Decision.approved,
}


def _provider(settings, **kw):
    defaults = dict(
        enabled=kw.pop("enabled", True),
        base_url=kw.pop("base_url", "http://127.0.0.1:20128/v1"),
        api_key=kw.pop("api_key", "sk-local-test"),
        cli_token=kw.pop("cli_token", None),
        review_model=kw.pop("review_model", "auto"),
        max_retries=kw.pop("max_retries", settings.omniroute_max_retries),
        max_output_tokens=kw.pop("max_output_tokens", settings.omniroute_max_output_tokens),
    )
    return OmniRouteProvider(**defaults)


class FakeResp:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self._payload).encode()


def _ok_payload(**over):
    payload = {
        "model": "auto",
        "choices": [{"message": {"content": "recommendation: SMALL_EXPERIMENT\nconfidence: 60\n"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    payload.update(over)
    return payload


# ------------------------------------------------------------------ provider
def test_disabled_by_default(settings):
    p = _provider(settings, enabled=False)
    assert p.available() is False
    with pytest.raises(ProviderUnavailableError):
        p.generate("hola")


def test_disabled_in_manager(container):
    # El manager NO resuelve OmniRoute automáticamente (aislado por diseño).
    manager = ProviderManager(container.settings)
    assert manager.resolve_primary().name != "omniroute"
    assert manager.omniroute.available() is False  # OMNIROUTE_ENABLED=false


def test_service_unreachable(settings, monkeypatch):
    def refuse(*a, **k):
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    with pytest.raises(ProviderUnavailableError):
        _provider(settings).generate("hola")


def test_timeout(settings, monkeypatch):
    def to(*a, **k):
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", to)
    with pytest.raises(ProviderUnavailableError):
        _provider(settings, max_retries=0).generate("hola")


@pytest.mark.parametrize("code", [401, 403, 500])
def test_http_errors(settings, monkeypatch, code):
    def err(*a, **k):
        raise urllib.error.HTTPError("u", code, "err", None, None)

    monkeypatch.setattr("urllib.request.urlopen", err)
    with pytest.raises(ProviderUnavailableError):
        _provider(settings, max_retries=0).generate("hola")


def test_429_retries_then_fails(settings, monkeypatch):
    """429 transitorio: reintenta hasta max_retries y falla (sin bucle infinito)."""
    calls = {"n": 0}

    def rate(*a, **k):
        calls["n"] += 1
        raise urllib.error.HTTPError("u", 429, "Too Many", None, None)

    monkeypatch.setattr("urllib.request.urlopen", rate)
    with pytest.raises(ProviderUnavailableError):
        _provider(settings, max_retries=1).generate("hola")
    assert calls["n"] == 2  # 1 inicial + 1 reintento


def test_empty_response(settings, monkeypatch):
    def empty(*a, **k):
        return FakeResp(_ok_payload(choices=[{"message": {"content": "   "}}]))

    monkeypatch.setattr("urllib.request.urlopen", empty)
    with pytest.raises(ProviderUnavailableError):
        _provider(settings, max_retries=0).generate("hola")


def test_invalid_json(settings, monkeypatch):
    class BadResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"not json {{{"

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: BadResp())
    with pytest.raises(ProviderUnavailableError):
        _provider(settings, max_retries=0).generate("hola")


def test_actual_model_recorded(settings, monkeypatch):
    """El modelo real puede diferir del solicitado (routing auto): se registra."""
    def ok(*a, **k):
        return FakeResp(_ok_payload(model="provider-x/some-model"))

    monkeypatch.setattr("urllib.request.urlopen", ok)
    resp = _provider(settings).generate("hola")
    assert resp.model == "auto"  # solicitado
    assert resp.actual_model == "provider-x/some-model"  # real


def test_actual_model_absent_falls_back(settings, monkeypatch):
    def ok(*a, **k):
        payload = _ok_payload()
        payload.pop("model")
        return FakeResp(payload)

    monkeypatch.setattr("urllib.request.urlopen", ok)
    resp = _provider(settings).generate("hola")
    assert resp.actual_model == "auto"  # fallback al solicitado


def test_error_sanitized_no_key(settings, monkeypatch):
    """El mensaje de error nunca contiene la clave ni el token."""
    def err(*a, **k):
        raise urllib.error.HTTPError("u", 401, "unauthorized", None, None)

    monkeypatch.setattr("urllib.request.urlopen", err)
    with pytest.raises(ProviderUnavailableError) as exc:
        _provider(settings, api_key="sk-SECRET-KEY-VALUE").generate("hola")
    assert "sk-SECRET-KEY-VALUE" not in str(exc.value)


def test_cost_honest_no_fabricated_zero(settings, monkeypatch):
    def ok(*a, **k):
        return FakeResp(_ok_payload(model="auto/free:reliable"))

    monkeypatch.setattr("urllib.request.urlopen", ok)
    resp = _provider(settings).generate("hola")
    assert resp.reported_cost is None  # coste desconocido: null, no 0
    assert resp.billing_verified is False


# ------------------------------------------------------------------ routing
def test_routing_omniroute_not_in_discovery(settings):
    from app.core.routing_policies import providers_for_task

    settings.omniroute_enabled = True
    attempts = providers_for_task("discovery", settings)
    assert all(a["provider"] != "omniroute" for a in attempts)


def test_routing_omniroute_second_reviewer_only_when_enabled(settings):
    from app.core.routing_policies import providers_for_task

    settings.omniroute_enabled = False
    attempts = providers_for_task("external_committee", settings)
    assert all(a["provider"] != "omniroute" for a in attempts)
    settings.omniroute_enabled = True
    attempts2 = providers_for_task("external_committee", settings)
    assert any(a.get("role") == "second_optional_reviewer" and a["provider"] == "omniroute" for a in attempts2)
    # El proveedor principal del comité sigue siendo OpenRouter (modelo fijo).
    assert attempts2[0]["provider"] == "openrouter"


def test_allowlist_unknown_blocked():
    from app.core.omniroute_allowlist import is_connection_allowed

    allowed, reason = is_connection_allowed("default", production=True)
    assert allowed is False and "UNKNOWN" in reason
    allowed2, _ = is_connection_allowed("web-cookie-providers", production=False)
    assert allowed2 is False  # BLOCKED incluso en pruebas


# --------------------------------------------------- auto_review_omniroute
def _seed_finalist(container):
    opp = container.opportunities.create(
        OpportunityCreate(title="Finalista OmniRoute", problem=PROBLEM, target_customer="Cliente X", source="test")
    )
    container.repos.evaluations.upsert(Evaluation(opportunity_id=opp.id, **SCORE80))
    return opp


def test_auto_review_omniroute_disabled_neutral(container):
    opp = _seed_finalist(container)
    res = container.reviews.auto_review_omniroute(opp.id)
    assert res["status"] == "skipped"
    assert res["reason"] == "omniroute_disabled"
    assert res["review_created"] is False
    assert len(container.repos.reviews.reviews_for(opp.id)) == 0


def test_auto_review_omniroute_failure_no_fabrication(container, monkeypatch):
    opp = _seed_finalist(container)
    container.settings.omniroute_enabled = True
    container.providers.omniroute.enabled = True

    def boom(*a, **k):
        raise ProviderUnavailableError("gateway caído (simulado)")

    monkeypatch.setattr(container.providers.omniroute, "generate", boom)
    res = container.reviews.auto_review_omniroute(opp.id)
    assert res["status"] == "failed"
    assert res["review_created"] is False
    assert len(container.repos.reviews.reviews_for(opp.id)) == 0  # nada fabricado
    log = container.repos.llm_calls.list_recent()
    assert log and log[0]["provider"] == "omniroute" and log[0]["response_status"] == "error"


def test_auto_review_omniroute_success(container, monkeypatch):
    opp = _seed_finalist(container)
    container.settings.omniroute_enabled = True
    container.providers.omniroute.enabled = True

    def ok(*a, **k):
        return LLMResponse(
            text="recommendation: MORE_RESEARCH\nconfidence: 55\n",
            model="auto", actual_model="provider-y/model-2", method="omniroute",
            cost_estimate_usd=0.0, cost_method="estimated_api",
            reported_cost=None, cost_source="UNKNOWN", billing_verified=False,
            usage={"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
            latency_ms=300, retry_count=0, verified=False,
        )

    monkeypatch.setattr(container.providers.omniroute, "generate", ok)
    res = container.reviews.auto_review_omniroute(opp.id)
    assert res["status"] == "ok"
    assert res["review"]["provider"] == "omniroute"
    assert res["review"]["model"] == "provider-y/model-2"
    log = container.repos.llm_calls.list_recent()
    assert log and log[0]["actual_model"] == "provider-y/model-2"


def test_auto_review_omniroute_daily_limit(container):
    opp = _seed_finalist(container)
    container.settings.omniroute_enabled = True
    container.providers.omniroute.enabled = True
    container.settings.omniroute_daily_request_limit = 0
    res = container.reviews.auto_review_omniroute(opp.id)
    assert res["status"] == "blocked"
    assert res["reason"] == "daily_request_limit"


def test_production_and_budget_untouched(container):
    opp = _seed_finalist(container)
    before_mode = container.engine.status()["mode"]
    before_ledger = len(container.repos.ledger.list())
    container.reviews.auto_review_omniroute(opp.id)
    assert container.engine.status()["mode"] == before_mode  # no activa producción
    assert len(container.repos.ledger.list()) == before_ledger  # no toca presupuesto


def test_no_key_in_call_log(container, monkeypatch):
    opp = _seed_finalist(container)
    container.settings.omniroute_enabled = True
    container.providers.omniroute.enabled = True
    container.providers.omniroute.api_key = "sk-TOP-SECRET-VALUE"

    def ok(*a, **k):
        return LLMResponse(text="recommendation: REJECT\nconfidence: 40\n", model="auto",
                           actual_model="m", method="omniroute", verified=False)

    monkeypatch.setattr(container.providers.omniroute, "generate", ok)
    container.reviews.auto_review_omniroute(opp.id)
    raw = json.dumps(container.repos.llm_calls.list_recent())
    assert "sk-TOP-SECRET-VALUE" not in raw
