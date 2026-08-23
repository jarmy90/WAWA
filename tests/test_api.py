"""Pruebas de la API local y del frontend servido por FastAPI."""
from __future__ import annotations

import json


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["providers"]["primary"]["name"] == "mock"
    assert body["budget"]["free_mode"] is True


def test_config_endpoint(client):
    resp = client.get("/api/config")
    body = resp.json()
    assert sum(body["scoring_weights"].values()) == 1.0
    assert len(body["decision_bands"]) == 4


def test_create_and_list(client):
    resp = client.post(
        "/api/opportunities",
        json={
            "title": "Oportunidad API",
            "problem": "Problema de prueba creado desde la API con suficiente detalle.",
            "proposed_solution": "Solución.",
            "target_customer": "Cliente.",
            "sector": "pruebas",
        },
    )
    assert resp.status_code == 200
    opp = resp.json()["opportunity"]
    assert opp["status"] == "draft"

    resp = client.get("/api/opportunities")
    items = resp.json()["items"]
    assert any(i["id"] == opp["id"] for i in items)

    # Filtro por estado
    resp = client.get("/api/opportunities?status=draft")
    assert resp.json()["count"] >= 1
    resp = client.get("/api/opportunities?status=approved")
    assert resp.json()["count"] == 0


def test_discover_endpoint(client):
    resp = client.post(
        "/api/opportunities/discover",
        json={"problem": "Los traders MQL5 necesitan auditar sus Expert Advisors automáticamente."},
    )
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


def test_evaluate_endpoint(client):
    created = client.post(
        "/api/opportunities",
        json={
            "title": "Para evaluar",
            "problem": "Problema de prueba para evaluar desde la API con detalle suficiente.",
            "target_customer": "Cliente.",
            "sector": "pruebas",
        },
    ).json()["opportunity"]
    resp = client.post(f"/api/opportunities/{created['id']}/evaluate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["evaluation"]["final_score"] >= 0
    assert body["detail"]["decision_log"]


def test_manual_decision_endpoint(client):
    created = client.post(
        "/api/opportunities",
        json={
            "title": "Decisión manual",
            "problem": "Problema de prueba para decidir manualmente desde la API.",
            "target_customer": "Cliente.",
            "sector": "pruebas",
        },
    ).json()["opportunity"]
    resp = client.post(f"/api/opportunities/{created['id']}/decision", json={"decision": "deferred", "note": "Por decisión del equipo."})
    assert resp.status_code == 200
    assert resp.json()["opportunity"]["status"] == "deferred"
    assert any(l["agent"] == "human" for l in resp.json()["detail"]["decision_log"])

    # 'blocked' no es una decisión manual válida.
    resp = client.post(f"/api/opportunities/{created['id']}/decision", json={"decision": "blocked"})
    assert resp.status_code == 422


def test_import_and_reevaluate(client):
    created = client.post(
        "/api/opportunities",
        json={
            "title": "Importable",
            "problem": "Problema que recibirá evidencias importadas desde la API.",
            "target_customer": "Cliente.",
            "sector": "pruebas",
        },
    ).json()["opportunity"]
    payload = {
        "opportunity_id": created["id"],
        "evidences": [
            {
                "evidence_type": "demand_signal",
                "source_name": "Encuesta",
                "summary": "Evidencia importada por API para la oportunidad de prueba.",
                "reliability_score": 0.8,
                "independence_group": "api",
                "verified": False,
            }
        ],
        "competitors": [{"name": "Competidor A", "observed_price": 99.0, "weaknesses": "Lento"}],
    }
    resp = client.post("/api/import", json=payload, params={"filename": "research.json"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["evidences_imported"] == 1
    assert body["competitors_imported"] == 1
    assert body["reevaluated"] is True
    assert body["evaluation"]["final_score"] > 0

    detail = client.get(f"/api/opportunities/{created['id']}").json()
    assert len(detail["evidences"]) >= 1
    assert detail["competitors"][0]["name"] == "Competidor A"


def test_import_creates_new_opportunity(client):
    payload = {
        "opportunity": {
            "title": "Importada nueva",
            "problem": "Oportunidad creada por importación con descripción suficientemente larga.",
            "proposed_solution": "Solución.",
            "sector": "pruebas",
        },
        "evidences": [{"summary": "Evidencia inicial de la oportunidad importada.", "reliability_score": 0.6}],
    }
    resp = client.post("/api/import", json=payload)
    assert resp.status_code == 200
    assert resp.json()["created"] is True
    assert resp.json()["reevaluated"] is False  # oportunidad nueva: no reevalúa sola


def test_export_endpoints(client):
    created = client.post(
        "/api/opportunities",
        json={
            "title": "Exportable API",
            "problem": "Problema de prueba para exportar desde la API con detalle.",
            "target_customer": "Cliente.",
            "sector": "pruebas",
        },
    ).json()["opportunity"]
    client.post(f"/api/opportunities/{created['id']}/evaluate")

    rj = client.get(f"/api/opportunities/{created['id']}/export?format=json")
    assert rj.status_code == 200
    assert rj.headers["content-type"].startswith("application/json")
    json.loads(rj.content)

    rm = client.get(f"/api/opportunities/{created['id']}/export?format=md")
    assert rm.status_code == 200
    assert rm.headers["content-type"].startswith("text/markdown")
    assert "# " in rm.text


def test_demo_endpoint(demo_client):
    # El fixture demo_client ya cargó 4 oportunidades; cargar de nuevo es idempotente.
    resp = demo_client.post("/api/demo/load?evaluate=false")
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 0
    assert body["skipped"] == 4
    list_resp = demo_client.get("/api/opportunities").json()
    assert list_resp["count"] == 4
    # Existe al menos una oportunidad MQL5 de demostración.
    assert any("MQL5" in i["title"] for i in list_resp["items"])


def test_demo_endpoint_creates_when_empty(client):
    resp = client.post("/api/demo/load?evaluate=true")
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 4
    assert body["evaluated"] == 4
    list_resp = client.get("/api/opportunities").json()
    assert list_resp["count"] == 4
    assert any(i["final_score"] is not None for i in list_resp["items"])


def test_frontend_served(demo_client):
    resp = demo_client.get("/")
    assert resp.status_code == 200
    assert "Autonomous Business Lab" in resp.text
    assert demo_client.get("/styles.css").status_code == 200
    assert demo_client.get("/app.js").status_code == 200


def test_score_filter(demo_client):
    all_items = demo_client.get("/api/opportunities").json()["items"]
    scores = [i["final_score"] for i in all_items if i["final_score"] is not None]
    if scores:
        threshold = max(0.0, min(scores))
        filtered = demo_client.get(f"/api/opportunities?min_score={threshold}").json()
        assert filtered["count"] >= 1
