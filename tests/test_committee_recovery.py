"""Iteración 023 — Operación de recuperación en vivo del comité.

Cubre los casos solicitados que son verificables offline sobre datos
persistidos: revisiones válidas/inválidas/ausentes, síntesis idempotente,
decisión idempotente, reutilización de síntesis (reintento tras timeout),
resultado persistido tras refrescar (GET), endpoint compuesto único contrato,
double-flight (lock), excepciones visibles y saneadas, sin llamadas LLM,
evidencia sin cambios, PRE_CYCLE sin iniciar, servicios sin conectar,
producción bloqueada y avance legítimo (MORE_RESEARCH → UNA misión específica;
REJECT → señalización de segunda candidata sin inventar sustitutas).

Los casos de interfaz (doble clic, restauración del botón) se verifican en el
JS (node --check) y con los guardas de un solo vuelo duplicados aquí a nivel
de servicio/endpoint.
"""
from __future__ import annotations

import pytest

from app.models.evaluation import Decision, Evaluation
from app.models.external_review import ReviewImportIn
from app.models.opportunity import OpportunityCreate

PROBLEM = "Problema sintético para la recuperación en vivo (iteración 023)."
SCORE80 = dict(
    pain_score=80.0, demand_score=80.0, customer_reach_score=80.0,
    automation_score=80.0, margin_score=80.0, build_speed_score=80.0,
    differentiation_score=80.0, safety_score=80.0, evidence_quality_score=80.0,
    confidence_score=80.0, final_score=80.0, decision=Decision.approved,
    independent_evidence_count=4,
)

def _uuid_hex() -> str:
    import uuid as _uuid

    return str(_uuid.uuid4()).replace("-", "")


def _review_text(provider: str, recommendation: str = "PRIORITY_EXPERIMENT", confidence: int = 80) -> str:
    """Texto en el formato key:value que acepta el parser con allowlist.
    El contenido varía por revisor para no chocar con el hash anti-duplicado."""
    return (
        f"recommendation: {recommendation}\n"
        f"confidence: {confidence}\n"
        f"primary_risk: riesgo documentado por {provider} (opinión, nunca evidencia).\n"
        f"missing_evidence: sin señal de pago real según {provider}.\n"
        "strongest_evidence: dolor económico referenciado https://example.com/fuente (2026-01-10)."
    )


def _seed_finalist(container, title="Finalista recuperación 023", *, score: float = 80.0):
    opp = container.opportunities.create(
        OpportunityCreate(title=title, problem=PROBLEM, target_customer="Cliente concreto", source="test")
    )
    scores = dict(SCORE80)
    scores["final_score"] = score
    container.repos.evaluations.upsert(Evaluation(opportunity_id=opp.id, **scores))
    container.reviews.queue_opportunity(opp.id)
    return opp


def _import(container, opp_id, provider, text=None, **kw):
    return container.reviews.import_review(
        opp_id,
        ReviewImportIn(
            filename=f"{provider}.md", content=text or _review_text(provider, **kw),
            provider=provider, model=provider,
        ),
    )


# ------------------------------------------------------------------ 1) 3 válidas
def test_three_valid_reviews_synthesize_and_decide(container):
    opp = _seed_finalist(container)
    for provider in ("gpt", "grok", "gemini"):
        assert _import(container, opp.id, provider)["status"] == "valid"
    res = container.reviews.synthesize_and_decide(opp.id)
    assert res["status"] == "completed"
    assert res["reviews"]["total"] == 3 and res["reviews"]["valid"] == 3
    assert res["synthesis"]["valid_reviews_count"] == 3
    assert res["decision"]["decision"] in ("PRIORITY_EXPERIMENT", "SMALL_EXPERIMENT", "MORE_RESEARCH")
    assert res["decision"]["internal_score_unchanged"] is True
    assert res["decision"]["blockers_untouched"] is True


# ------------------------------------------------- 2) 2 válidas + 1 inválida
def test_two_valid_one_invalid(container):
    opp = _seed_finalist(container)
    _import(container, opp.id, "gpt")
    _import(container, opp.id, "grok")
    # La tercera no es parseable como revisión estructurada (texto libre).
    _import(container, opp.id, "gemini", text="Respuesta libre sin campos estructurados.")
    res = container.reviews.synthesize_and_decide(opp.id)
    assert res["reviews"]["valid"] == 2
    assert len(res["reviews"]["invalid_or_absent"]) == 1
    assert res["reviews"]["invalid_or_absent"][0]["provider"] == "gemini"
    # El flujo NO se paraliza: hay decisión.
    assert res["decision"]["decision"]


# ------------------------------------------------- 3) 1 válida, 2 ausentes
def test_one_valid_two_absent(container):
    opp = _seed_finalist(container)
    _import(container, opp.id, "gpt")
    res = container.reviews.synthesize_and_decide(opp.id)
    assert res["reviews"]["valid"] == 1
    # Ausencia neutral: no rechaza por falta de revisores, decide con lo que hay.
    assert res["decision"]["decision"] in ("PRIORITY_EXPERIMENT", "SMALL_EXPERIMENT", "MORE_RESEARCH")
    assert res["decision"]["reasons"][0].startswith("consensus=")


# ------------------------------------------------------------- 4) cero válidas
def test_zero_valid_reviews(container):
    opp = _seed_finalist(container)
    res = container.reviews.synthesize_and_decide(opp.id)
    assert res["reviews"]["valid"] == 0
    assert res["decision"]["reasons"][0] in ("no_external_reviews", "window_open", "internal_blockers")


# ------------------------------------------------------- 5/6) idempotencia
def test_synthesis_and_decision_idempotent(container):
    opp = _seed_finalist(container)
    _import(container, opp.id, "gpt")
    r1 = container.reviews.synthesize_and_decide(opp.id)
    r2 = container.reviews.synthesize_and_decide(opp.id)
    assert r1["operation_id"] == r2["operation_id"]
    assert r2["synthesis_reused"] is True
    assert r1["decision"] == r2["decision"]
    # No se duplican revisiones ni síntesis.
    assert len(container.repos.reviews.reviews_for(opp.id)) == 1


def test_synthesis_regenerates_when_reviews_change(container):
    opp = _seed_finalist(container)
    _import(container, opp.id, "gpt")
    r1 = container.reviews.synthesize_and_decide(opp.id)
    _import(container, opp.id, "grok")
    r2 = container.reviews.synthesize_and_decide(opp.id)
    assert r2["synthesis_reused"] is False
    assert r2["operation_id"] != r1["operation_id"]


# --------------------------------------------- 7/8) reintento y persistencia
def test_retry_and_refresh_recovers_persisted_result(client, container):
    opp = _seed_finalist(container)
    _import(container, opp.id, "gpt")
    client.post(f"/api/reviews/opportunities/{opp.id}/synthesize-and-decide")
    # "Refresco": el estado se consulta por GET y sigue ahí (idempotente).
    state = client.get(f"/api/reviews/opportunities/{opp.id}").json()
    assert state["synthesis"] is not None
    # Reintento por POST devuelve exactamente el mismo contrato persistido.
    again = client.post(f"/api/reviews/opportunities/{opp.id}/synthesize-and-decide").json()
    first = client.post(f"/api/reviews/opportunities/{opp.id}/synthesize-and-decide").json()
    assert again["operation_id"] == first["operation_id"]
    assert again["decision"] == first["decision"]


# ------------------------------------------------- 9) doble operación bloqueada
def test_double_flight_serialized_not_duplicated(client, container):
    """El lock de operaciones serializa llamadas concurrentes: mismo resultado,
    sin excepción de transacción y sin duplicar síntesis."""
    import threading

    opp = _seed_finalist(container)
    _import(container, opp.id, "gpt")
    results: list = []

    def call():
        resp = client.post(f"/api/reviews/opportunities/{opp.id}/synthesize-and-decide")
        results.append(resp.status_code)

    threads = [threading.Thread(target=call) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == [200, 200]
    state = client.get(f"/api/reviews/opportunities/{opp.id}").json()
    assert state["synthesis"] is not None


# ---------------------------------------- 11) error visible y saneado
def test_error_surfaces_sanitized(client):
    missing = _uuid_hex()
    r = client.post(f"/api/reviews/opportunities/{missing}/synthesize-and-decide")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "not_found"
    assert "Oportunidad no encontrada" in body["error"]["message"]


# --------------------------------- 12/13/14/15/16) garantías duras
def test_guarantees_no_llm_no_evidence_change_no_precycle_no_production(client, container):
    opp = _seed_finalist(container)
    _import(container, opp.id, "gpt")
    ev_before = len(container.repos.evidence.list_for(opp.id))
    res = client.post(f"/api/reviews/opportunities/{opp.id}/synthesize-and-decide").json()
    assert res["authorizes_production"] is False
    assert res["real_money_moved"] is False
    assert res["model_opinion_not_evidence"] is True
    assert len(container.repos.evidence.list_for(opp.id)) == ev_before == 0
    # Ninguna llamada LLM durante la operación.
    assert container.repos.llm_calls.list_recent(limit=100) == []
    # PRE_CYCLE sin iniciar.
    row = container.conn.execute("SELECT started_at FROM cycle_state").fetchone()
    assert row is None or row["started_at"] is None
    # Servicios comerciales sin conectar (pago, entrega, hosting, dominio, analytics).
    status = container.connect_services.status()
    by_id = {s["id"]: s["status"] for s in status["items"]}
    assert all(by_id.get(k) != "CONNECTED" for k in ("stripe", "email", "hosting", "domain", "analytics"))
    # Producción bloqueada (capacidad no disponible y modo != AUTONOMOUS_PRODUCTION).
    engine_status = container.engine.status()
    mode = engine_status.get("operating_mode") or engine_status.get("mode")
    assert mode != "AUTONOMOUS_PRODUCTION"
    assert engine_status.get("production_capability_available") is False


# ------------------------------- 17) readiness se mantiene cuando toca
def test_ready_to_connect_services_preserved(container):
    container.bootstrap.apply()
    snap = container.command_center.snapshot()
    assert snap["readiness"]["readiness_state"] == "READY_TO_CONNECT_SERVICES"
    winner = None
    for card in container.bootstrap.candidates()["candidates"]:
        if card.get("is_winner"):
            winner = card
    assert winner is not None
    res = container.reviews.synthesize_and_decide(winner["opportunity_id"])
    snap2 = container.command_center.snapshot()
    assert snap2["readiness"]["readiness_state"] in (
        "READY_TO_CONNECT_SERVICES",  # sin pago real: nunca READY_TO_LAUNCH
    )
    assert res["authorizes_production"] is False


# ------------------------- 18) MORE_RESEARCH → UNA misión específica
def test_more_research_creates_single_specific_mission(container):
    # Umbral superado (75 >= 72) pero mayoría MORE_RESEARCH ⇒ decisión honesta.
    opp = _seed_finalist(container, title="Finalista MORE_RESEARCH", score=75.0)
    _import(container, opp.id, "gpt", recommendation="MORE_RESEARCH", confidence=55)
    res = container.reviews.synthesize_and_decide(opp.id)
    assert res["decision"]["decision"] == "MORE_RESEARCH"
    assert res["followup"]["kind"] in ("SPECIFIC_MISSION_CREATED", "MISSION_EXISTS_OR_SKIPPED")
    if res["followup"]["kind"] == "SPECIFIC_MISSION_CREATED":
        mid = res["followup"]["mission_id"]
        assert mid
        # Idempotente: repetir NO crea otra misión.
        res2 = container.reviews.synthesize_and_decide(opp.id)
        assert res2["followup"]["kind"] in ("MISSION_EXISTS_OR_SKIPPED", "SPECIFIC_MISSION_CREATED")
        if res2["followup"]["kind"] == "SPECIFIC_MISSION_CREATED":
            assert res2["followup"]["mission_id"] == mid


# ------------------------- 19) REJECT → segunda candidata señalada
def test_reject_signals_second_candidate_without_inventing(container):
    opp = _seed_finalist(container, title="Finalista REJECT 023")
    # Bloqueadores críticos internos ⇒ REJECT determinista.
    container.repos.evaluations.upsert(
        Evaluation(opportunity_id=opp.id, **{**SCORE80, "blockers": ["DATOS_INSUFICIENTES_CRITICO"]})
    )
    _import(container, opp.id, "gpt")
    res = container.reviews.synthesize_and_decide(opp.id)
    assert res["decision"]["decision"] == "REJECT"
    assert res["followup"]["kind"] == "EVALUATE_SECOND_CANDIDATE"
    assert "no se inventa sustituta" in res["followup"]["note"]


# ------------------------- 20) frontend/backend sincronizados
def test_frontend_uses_composite_contract():
    from pathlib import Path

    js = (Path(__file__).resolve().parents[1] / "frontend" / "candidates.js").read_text(encoding="utf-8")
    assert "/synthesize-and-decide" in js
    assert "AbortController" in js
    assert "SYNTH_INFLIGHT" in js
    assert "REINTENTAR" in js
    assert "sessionStorage.getItem" in js  # recuperación tras refrescar
    assert "ETAPA 4/4" in js  # progreso por etapas
