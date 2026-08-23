"""OpenRouter para el comité de contraste (iteración 007): pruebas offline.

Cubre: sin clave no disponible y fallback neutral (sin fabricar revisión);
retries acotados sin bucle infinito; topes de tokens; requested vs actual
model; costes honestos (reported_cost None + billing_verified False cuando no
hay coste verificable, nunca cero fabricado); guards de auto_review (máx 1 por
oportunidad, límites diario/mensual, circuit breaker); ausencia de revisión
neutral; y persistencia del llm_call_log. 100% offline (sin red).
"""
from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from app.core.errors import ProviderUnavailableError
from app.models.enums import Decision
from app.models.evaluation import Evaluation
from app.models.external_review import ReviewImportIn
from app.models.llm_call import CostSource
from app.models.opportunity import OpportunityCreate
from app.providers.base import LLMResponse
from app.providers.manager import ProviderManager
from app.providers.mock import MockProvider
from app.providers.openrouter import OpenRouterProvider
from app.services.reviews import _sha256
from tests.conftest import make_settings

PROBLEM = "Problema de prueba para validar el comité."
SCORE80 = {
    "pain_score": 80.0, "demand_score": 80.0, "customer_reach_score": 80.0,
    "automation_score": 80.0, "margin_score": 80.0, "build_speed_score": 80.0,
    "differentiation_score": 80.0, "safety_score": 80.0, "evidence_quality_score": 80.0,
    "confidence_score": 80.0, "final_score": 80.0, "decision": Decision.approved,
}


def _provider(settings, **kw):
    return OpenRouterProvider(
        settings.openrouter_api_key,
        review_model=kw.pop("review_model", settings.openrouter_review_model),
        fallback_model=kw.pop("fallback_model", settings.openrouter_fallback_model),
        timeout=kw.pop("timeout", settings.openrouter_timeout_seconds),
        max_retries=kw.pop("max_retries", settings.openrouter_max_retries),
        max_input_tokens=kw.pop("max_input_tokens", settings.openrouter_max_input_tokens),
        max_output_tokens=kw.pop("max_output_tokens", settings.openrouter_max_output_tokens),
    )


def _seed_finalist(container, title="Finalista auto de prueba"):
    opp = container.opportunities.create(
        OpportunityCreate(title=title, problem=PROBLEM, target_customer="Cliente concreto", source="test")
    )
    container.repos.evaluations.upsert(Evaluation(opportunity_id=opp.id, **SCORE80))
    return opp


def _configure_key(container) -> None:
    """Activa la clave en el proveedor construido por el contenedor."""
    container.settings.openrouter_api_key = "sk-or-v1-test"
    container.providers.openrouter.api_key = "sk-or-v1-test"


# ------------------------------------------------------------------ provider
def test_unavailable_without_key(settings):
    p = _provider(settings, review_model="openai/gpt-4o-mini")
    p.api_key = None
    assert p.available() is False
    with pytest.raises(ProviderUnavailableError):
        p.generate("hola")


def test_configured_available(settings):
    settings.openrouter_api_key = "sk-or-v1-test"
    p = _provider(settings)
    assert p.available() is True


def test_retries_capped_no_infinite_loop(settings, monkeypatch):
    """429 transitorio: reintenta hasta max_retries y luego falla (sin bucle infinito)."""
    settings.openrouter_api_key = "sk-or-v1-test"
    settings.openrouter_max_retries = 2
    p = _provider(settings)

    calls = {"n": 0}

    def fake_urlopen(request, timeout=None):
        calls["n"] += 1
        raise urllib.error.HTTPError("url", 429, "Too Many", None, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(ProviderUnavailableError):
        p.generate("hola")
    assert calls["n"] == 1 + settings.openrouter_max_retries  # 1 inicial + reintentos


def test_retries_succeed_and_record_count(settings, monkeypatch):
    """2 fallos transitorios y luego éxito: retry_count = 2 en la respuesta."""
    settings.openrouter_api_key = "sk-or-v1-test"
    settings.openrouter_max_retries = 3
    p = _provider(settings)
    attempts = {"n": 0}

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(
                {
                    "model": "openai/gpt-4o-mini",
                    "choices": [{"message": {"content": "recommendation: SMALL_EXPERIMENT\nconfidence: 60"}}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                }
            ).encode()

    def fake_urlopen(request, timeout=None):
        attempts["n"] += 1
        if attempts["n"] <= 2:
            raise urllib.error.HTTPError("url", 503, "Unavailable", None, None)
        return FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    resp = p.generate("hola")
    assert resp.retry_count == 2
    assert resp.text.startswith("recommendation:")


def test_usage_and_models_recorded(settings, monkeypatch):
    settings.openrouter_api_key = "sk-or-v1-test"
    p = _provider(settings)

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(
                {
                    "model": "openai/gpt-4o-2024-08",  # el router devolvió OTRO modelo
                    "choices": [{"message": {"content": "OK"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                }
            ).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout=None: FakeResp())
    resp = p.generate("hola")
    assert resp.model == settings.openrouter_review_model  # solicitado (fijo)
    assert resp.actual_model == "openai/gpt-4o-2024-08"  # realmente usado
    assert resp.usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


def test_cost_honest_no_fabricated_zero(settings, monkeypatch):
    """Sin coste en la respuesta => reported_cost None, nunca 0 fabricado."""
    settings.openrouter_api_key = "sk-or-v1-test"
    p = _provider(settings)

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(
                {
                    "model": "openrouter/free",
                    "choices": [{"message": {"content": "OK"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                }
            ).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout=None: FakeResp())
    resp = p.generate("hola")
    assert resp.reported_cost is None  # coste desconocido => null, no 0
    assert resp.billing_verified is False
    assert resp.cost_source == CostSource.free_tier.value  # router gratuito, sin verificar
    assert resp.cost_estimate_usd >= 0  # estimación etiquetada aparte


def test_provider_cost_from_response(settings, monkeypatch):
    settings.openrouter_api_key = "sk-or-v1-test"
    p = _provider(settings)

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(
                {
                    "model": "openai/gpt-4o-mini",
                    "choices": [{"message": {"content": "OK"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "total_cost": 0.0001},
                }
            ).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout=None: FakeResp())
    resp = p.generate("hola")
    assert resp.reported_cost == 0.0001
    assert resp.cost_source == CostSource.provider_response.value
    assert resp.billing_verified is False  # sin reconciliación con facturación


def test_max_output_tokens_passed(settings, monkeypatch):
    settings.openrouter_api_key = "sk-or-v1-test"
    settings.openrouter_max_output_tokens = 321
    p = _provider(settings)
    sent = {}

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"model": "m", "choices": [{"message": {"content": "OK"}}]}).encode()

    def fake_urlopen(request, timeout=None):
        sent["body"] = json.loads(request.data)
        return FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    p.generate("hola")
    assert sent["body"]["max_tokens"] == 321


def test_prompt_truncated_to_input_limit(settings, monkeypatch):
    settings.openrouter_api_key = "sk-or-v1-test"
    settings.openrouter_max_input_tokens = 10  # 40 caracteres aprox
    p = _provider(settings)
    sent = {}

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"model": "m", "choices": [{"message": {"content": "OK"}}]}).encode()

    def fake_urlopen(request, timeout=None):
        sent["body"] = json.loads(request.data)
        return FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    p.generate("x" * 5_000)
    assert "TRUNCADO" in sent["body"]["messages"][-1]["content"]


# ------------------------------------------------------ revisión automática
def test_auto_review_without_key_neutral(container):
    opp = _seed_finalist(container)
    res = container.reviews.auto_review(opp.id)
    assert res["status"] == "skipped"
    assert res["reason"] == "provider_not_configured"
    assert res["review_created"] is False
    # Sin clave no se fabrica ninguna revisión.
    assert len(container.repos.reviews.reviews_for(opp.id)) == 0


def test_auto_review_max_one_per_opportunity(container):
    opp = _seed_finalist(container)
    # Simular que ya existe una revisión automática.
    container.repos.reviews.create_review(
        __import__("app.models.external_review", fromlist=["ExternalReview"]).ExternalReview(
            opportunity_id=opp.id, provider="openrouter", model="m", execution_mode="API_AUTOMATIC",
            raw_response="x", file_hash=_sha256("x"),
        )
    )
    res = container.reviews.auto_review(opp.id)
    assert res["status"] == "blocked"
    assert res["reason"] == "max_reviews_per_opportunity"


def test_auto_review_daily_request_limit(container):
    opp = _seed_finalist(container)
    container.settings.openrouter_daily_request_limit = 0
    _configure_key(container)
    res = container.reviews.auto_review(opp.id)
    assert res["status"] == "blocked"
    assert res["reason"] == "daily_request_limit"


def test_auto_review_circuit_breaker(container):
    opp = _seed_finalist(container)
    container.settings.openrouter_circuit_breaker_failures = 2
    container.settings.openrouter_circuit_breaker_cooldown_seconds = 60_000
    _configure_key(container)
    from app.models.llm_call import LLMCallRecord

    for _ in range(2):
        container.repos.llm_calls.create(LLMCallRecord(
            provider="openrouter", response_status="error", requested_model="m",
            notes="fallo simulado",
        ))
    res = container.reviews.auto_review(opp.id)
    assert res["status"] == "blocked"
    assert res["reason"] == "circuit_breaker_open"


def test_auto_review_failure_no_fabrication(container, monkeypatch):
    """Fallo del proveedor => sin revisión, neutral, y llamada registrada en el log."""
    opp = _seed_finalist(container)
    _configure_key(container)

    def boom(*a, **k):
        raise ProviderUnavailableError("cuota agotada (simulado)")

    monkeypatch.setattr(container.providers.openrouter, "generate", boom)
    res = container.reviews.auto_review(opp.id)
    assert res["status"] == "failed"
    assert res["review_created"] is False
    assert len(container.repos.reviews.reviews_for(opp.id)) == 0  # nada fabricado
    log = container.repos.llm_calls.list_recent()
    assert log and log[0]["response_status"] == "error"


def test_auto_review_bypasses_manager_no_mock_fabrication(container, monkeypatch):
    """auto_review llama DIRECTAMENTE a openrouter: el manager (que podría
    resolver a mock según LLM_PROVIDER) nunca interviene ni fabrica revisión."""
    opp = _seed_finalist(container)
    _configure_key(container)
    container.settings.llm_provider = "mock"  # el manager resolvería mock si se usara

    def manager_must_not_be_called(*a, **k):
        raise AssertionError("el manager NO debe usarse en auto_review")

    def openrouter_ok(*a, **k):
        return LLMResponse(
            text="recommendation: SMALL_EXPERIMENT\nconfidence: 60\n",
            model="openai/gpt-4o-mini", actual_model="openai/gpt-4o-mini",
            method="openrouter (API)", cost_estimate_usd=0.0, cost_method="estimated_api",
            reported_cost=None, cost_source=CostSource.unknown.value, billing_verified=False,
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            latency_ms=500, retry_count=0, verified=False,
        )

    monkeypatch.setattr(container.providers, "generate", manager_must_not_be_called)
    monkeypatch.setattr(container.providers.openrouter, "generate", openrouter_ok)
    res = container.reviews.auto_review(opp.id)
    assert res["status"] == "ok"
    assert res["review"]["provider"] == "openrouter"
    assert res["review"]["model"] == "openai/gpt-4o-mini"


def test_auto_review_success_path(container, monkeypatch):
    """Éxito: revisión API_AUTOMATIC guardada con modelo real y log honesto."""
    opp = _seed_finalist(container)
    _configure_key(container)

    def fake_generate(*a, **k):
        return LLMResponse(
            text="recommendation: SMALL_EXPERIMENT\nconfidence: 62\nprimary_risk: validación lenta\n",
            model="openai/gpt-4o-mini",  # solicitado
            actual_model="openai/gpt-4o-mini",  # usado
            method="openrouter (API)",
            cost_estimate_usd=0.00001,
            cost_method="estimated_api",
            reported_cost=None,
            cost_source=CostSource.unknown.value,
            billing_verified=False,
            usage={"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140},
            latency_ms=800,
            retry_count=0,
            verified=False,
        )

    monkeypatch.setattr(container.providers.openrouter, "generate", fake_generate)
    res = container.reviews.auto_review(opp.id)
    assert res["status"] == "ok"
    assert res["review_created"] is True
    assert res["billing_verified"] is False
    rev = res["review"]
    assert rev["execution_mode"] == "API_AUTOMATIC"
    assert rev["model"] == "openai/gpt-4o-mini"
    assert rev["recommendation"] == "SMALL_EXPERIMENT"
    log = container.repos.llm_calls.list_recent()
    assert log and log[0]["requested_model"] == "openai/gpt-4o-mini"
    assert log[0]["billing_verified"] is False
    assert log[0]["reported_cost"] is None  # coste desconocido, no cero


def test_auto_status_reflects_limits(container):
    st = container.reviews.auto_status()
    assert st["max_reviews_per_opportunity"] == 1
    assert st["usage_today"]["limit"] == container.settings.openrouter_daily_request_limit
    assert st["circuit_breaker"]["open"] is False


def test_llm_call_log_persists(container):
    from app.models.llm_call import LLMCallRecord

    container.repos.llm_calls.create(LLMCallRecord(
        provider="openrouter", requested_model="m", actual_model="m2",
        reported_cost=None, cost_source="UNKNOWN", billing_verified=False,
        response_status="ok",
    ))
    rows = container.repos.llm_calls.list_recent()
    assert len(rows) == 1
    assert rows[0]["actual_model"] == "m2"
    assert rows[0]["billing_verified"] is False
