"""Gemini opcional: fallos, cuota agotada y ausencia de clave no rompen nada."""
from __future__ import annotations

import pytest

from app.core.errors import ProviderUnavailableError
from app.core.container import build_container
from app.models.opportunity import OpportunityCreate
from app.providers.gemini import GeminiProvider
from tests.conftest import make_settings


class _FakeClient:
    def __init__(self, error=None):
        self._error = error

    def generate_content(self, *args, **kwargs):
        if self._error:
            raise self._error
        return type("R", (), {"text": '{"ok": true}'})()


def test_gemini_without_key_not_available():
    provider = GeminiProvider(api_key=None)
    assert provider.available() is False


def test_gemini_import_failure_not_available(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "google.generativeai":
            raise ImportError("google.generativeai no instalado")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    provider = GeminiProvider(api_key="fake-key")
    assert provider.available() is False


def test_gemini_generate_raises_provider_unavailable():
    provider = GeminiProvider(api_key="fake-key")
    provider._client = _FakeClient(error=Exception("quota 429 exceeded"))
    with pytest.raises(ProviderUnavailableError):
        provider.generate("hola", task="scout", output_schema={})


def test_quota_exhausted_falls_back_to_mock(tmp_path, monkeypatch):
    settings = make_settings(tmp_path, llm_provider="gemini", gemini_api_key="fake-key")
    container = build_container(settings)

    # Forzamos que Gemini falle siempre (cuota) pero que "exista".
    monkeypatch.setattr(container.providers.gemini, "available", lambda: True)
    monkeypatch.setattr(container.providers.gemini, "_client", _FakeClient(error=Exception("429 quota exhausted")))

    try:
        call = container.providers.generate("problema de prueba", task="scout", system="problema")
        assert call.fallback_used is True
        assert call.errors, "Debe registrar el error del proveedor"
        assert call.response.method.startswith("mock")
    finally:
        container.close()


def test_pipeline_survives_gemini_failure(tmp_path, monkeypatch):
    settings = make_settings(tmp_path, llm_provider="gemini", gemini_api_key="fake-key")
    container = build_container(settings)
    monkeypatch.setattr(container.providers.gemini, "available", lambda: True)
    monkeypatch.setattr(container.providers.gemini, "_client", _FakeClient(error=Exception("429 quota exhausted")))

    try:
        opp = container.opportunities.create(
            OpportunityCreate(
                title="Con Gemini roto",
                problem="Problema de prueba con Gemini caído por cuota.",
                proposed_solution="Solución.",
                target_customer="Cliente concreto.",
                sector="pruebas",
            )
        )
        # No debe lanzar: hace fallback a mock y registra errores.
        evaluation = container.pipeline.evaluate(opp.id, clear_existing=False)
        assert evaluation.final_score >= 0
        logs = container.repos.decision_log.list_for(opp.id)
        assert logs, "Debe haber registros de decisión"
        # Al menos un paso registró el error del proveedor.
        assert any(l.errors for l in logs)
    finally:
        container.close()
