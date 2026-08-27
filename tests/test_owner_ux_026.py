from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.core.container import build_container
from app.main import create_app
from fastapi.testclient import TestClient


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        database_path=tmp_path / "owner.db",
        logs_dir=tmp_path / "logs",
        manual_research_dir=tmp_path / "manual",
        frontend_dir=Path(__file__).parents[1] / "frontend",
        llm_provider="mock",
        review_allowed_extensions=(".txt", ".md", ".markdown", ".json"),
    )


def _client(tmp_path: Path):
    container = build_container(_settings(tmp_path))
    app = create_app(container)
    return container, TestClient(app)


def _opportunity(client):
    response = client.post("/api/opportunities", json={
        "title": "Prueba de importación",
        "problem": "Un problema observable para validar revisiones externas.",
        "proposed_solution": "Entrega concierge verificable.",
        "target_customer": "Comprador concreto",
        "source": "test",
    })
    assert response.status_code == 200
    return response.json()["opportunity"]["id"]


def test_simple_grok_without_header_is_imported(tmp_path):
    container, client = _client(tmp_path)
    try:
        oid = _opportunity(client)
        response = client.post(f"/api/reviews/opportunities/{oid}/import", json={
            "filename": "valoracion_grok.txt",
            "provider": "grok",
            "content": "recommendation: REJECT\nconfidence: 91\nprimary_risk: sustituto gratuito\nmissing_evidence: pago real",
        })
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "valid"
        assert body["review"]["provider"] == "grok"
        assert body["review"]["status"] == "valid"
    finally:
        container.close()


def test_simple_gpt_infers_provider_from_filename(tmp_path):
    container, client = _client(tmp_path)
    try:
        oid = _opportunity(client)
        response = client.post(f"/api/reviews/opportunities/{oid}/import", json={
            "filename": "revision-gpt.md",
            "content": "recommendation: MORE_RESEARCH\nconfidence: 70",
        })
        assert response.status_code == 200
        assert response.json()["review"]["provider"] == "gpt"
    finally:
        container.close()


def test_combined_and_simple_reviews_synthesize_without_evidence(tmp_path):
    container, client = _client(tmp_path)
    try:
        oid = _opportunity(client)
        for filename, provider, recommendation in (("grok.txt", "grok", "REJECT"), ("gpt.txt", "gpt", "MORE_RESEARCH")):
            assert client.post(f"/api/reviews/opportunities/{oid}/import", json={
                "filename": filename, "provider": provider,
                "content": f"recommendation: {recommendation}\nconfidence: 80\nprimary_risk: riesgo repetido",
            }).status_code == 200
        assert client.post(f"/api/opportunities/{oid}/evaluate").status_code == 200
        # El comité exige una oportunidad finalista; para este test aislamos
        # la síntesis directamente, sin alterar la regla de entrada a cola.
        result = client.post(f"/api/reviews/opportunities/{oid}/synthesize-and-decide")
        assert result.status_code in (200, 404)
        if result.status_code == 404:
            result = client.post(f"/api/reviews/opportunities/{oid}/synthesize")
        body = result.json()
        assert body["synthesis"]["valid_reviews_count"] == 2
        assert body["synthesis"]["internal_score_after"] == body["synthesis"]["internal_score_before"]
        assert body["synthesis"]["consensus_level"] in ("LOW", "MEDIUM", "OPINION_CONSENSUS", "HIGH")
    finally:
        container.close()


def test_owner_summary_is_honest_and_contains_no_secret(tmp_path):
    container, client = _client(tmp_path)
    try:
        response = client.get("/api/owner/summary")
        assert response.status_code == 200
        body = response.json()
        assert body["simulated"] is True
        assert body["real_money_moved"] is False
        assert "api_key" not in str(body).lower()
        assert body["winner"] is None
    finally:
        container.close()
