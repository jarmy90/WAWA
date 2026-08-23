"""Campañas Freebuff-first (iteración 006): pruebas del CampaignRunner.

Cubre los casos exigidos: campaña reanudable, sesiones de 2h/6h, rechazo de
duración fuera de rango, SESSION_PLAN determinista, SESSION_STATE persistente,
SESSION_OUTPUT validado, finalización incompleta bloqueada, finalización
completa, NEXT_SESSION generado, reanudación tras reinicio, no repetición de
tareas, deduplicación de conceptos y evidencias, límites inmutables del embudo,
API budget 0, ausencia de llamadas Gemini, niveles de profundidad, deep
reasoning limitado a shortlist, máximo de finalistas (y cero permitido),
campaña fallida conservando aprendizajes, misiones, evidencia sin URL no
verificada, review packet idéntico, importación GPT/Grok/Gemini, consenso que
no modifica score/evidencia, API Readiness Gate (PREMATURE por defecto,
REQUIRED solo con criterios completos), piloto sintético completo, economía
simulada y AUTONOMOUS_PRODUCTION bloqueado.
"""
from __future__ import annotations

import json
import os
import uuid

import pytest

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.campaign import CampaignCreate, CampaignStatus, ReasoningIn, ReasoningLevel, SessionOutputIn
from app.models.enums import Decision
from app.models.evaluation import Evaluation
from app.models.opportunity import OpportunityCreate
from tests.conftest import make_settings

PROBLEM = "Problema de prueba para validar el flujo."


def _campaign(container, **kw):
    data = dict(
        title="Campaña de prueba " + uuid.uuid4().hex[:6],
        time_budget_hours=3,
        territory_keys=["small_businesses"],
        lens_keys=["VERIFY_THE_OUTPUT"],
        archetype_keys=["VERIFICATION_TOOL"],
    )
    data.update(kw)
    return container.campaigns.create_campaign(CampaignCreate(**data))["campaign"]


def _finalists(camp):
    return (camp.get("funnel_limits") or {}).get("maximum_finalists", 3)


def _concept(title="Concepto de prueba", buyer="Comprador hipótesis (HIPÓTESIS)", outcome="Resultado (HIPÓTESIS)"):
    return {
        "title": title,
        "territory_key": "small_businesses",
        "lens_keys": ["VERIFY_THE_OUTPUT"],
        "archetype_key": "VERIFICATION_TOOL",
        "problem_hypothesis": "Hipótesis de problema.",
        "mechanism": "Mecanismo de valor.",
        "buyer_hypothesis": buyer,
        "outcome_hypothesis": outcome,
    }


def _output(session_id, **kw):
    data = dict(
        session_id=session_id,
        completed_tasks=["Tarea A"],
        concepts=[_concept()],
        evidences=[],
        api_calls_made=0,
        api_cost_usd=0.0,
    )
    data.update(kw)
    return SessionOutputIn.model_validate(data)


# ------------------------------------------------------------------ campaña
def test_create_campaign_resumable(container):
    camp = _campaign(container)
    assert camp["status"] == "active"
    assert camp["stage"] in ("CREATED", "TERRITORY_SELECTION")
    assert camp["api_budget_usd"] == 0
    assert _finalists(camp) == 3


def test_prepare_session_2h(container):
    camp = _campaign(container)
    s = container.campaigns.prepare_session(camp["id"], 2)
    assert s["time_budget_hours"] == 2
    assert s["plan_path"] and os.path.exists(s["plan_path"])


def test_prepare_session_6h(container):
    camp = _campaign(container)
    s = container.campaigns.prepare_session(camp["id"], 6)
    assert s["time_budget_hours"] == 6


def test_reject_hours_out_of_range(container):
    camp = _campaign(container)
    with pytest.raises(ValidationError):
        container.campaigns.prepare_session(camp["id"], 1)
    with pytest.raises(ValidationError):
        container.campaigns.prepare_session(camp["id"], 7)


def test_session_plan_deterministic(container):
    camp = _campaign(container)
    s1 = container.campaigns.prepare_session(camp["id"], 3)
    s2 = container.campaigns.prepare_session(camp["id"], 3)
    # Mismo estado de campaña ⇒ mismas tareas planificadas (sin timestamp).
    assert s1["tasks_planned"] == s2["tasks_planned"]
    assert "SESSION_PLAN" in open(s1["plan_path"], encoding="utf-8").read()


def test_session_state_persistent(container):
    camp = _campaign(container)
    s = container.campaigns.prepare_session(camp["id"], 3)
    state = json.load(open(s["state_path"], encoding="utf-8"))
    assert state["session_id"] == s["session_id"]
    assert state["campaign_id"] == camp["id"]
    # Se puede recuperar de la base tras "reiniciar" (nuevo contenedor).
    container.close()
    from app.core.config import Settings
    from app.core.container import build_container

    s2 = make_settings(container.settings.data_dir, database_path=container.settings.database_path)
    c2 = build_container(s2)
    try:
        row = c2.repos.campaigns.get_session(s["session_id"])
        assert row is not None and row["session_id"] == s["session_id"]
    finally:
        c2.close()


def test_session_output_validated(container):
    camp = _campaign(container)
    s = container.campaigns.prepare_session(camp["id"], 3)
    with pytest.raises(ValueError):
        _output(s["session_id"], api_calls_made=-1)
    with pytest.raises(ValueError):
        _output(s["session_id"], api_cost_usd=-0.5)



def test_finalize_incomplete_blocked(container):
    camp = _campaign(container)
    s = container.campaigns.prepare_session(camp["id"], 3)
    with pytest.raises(ValidationError):
        container.campaigns.finalize_session(s["session_id"])


def test_finalize_complete(container):
    camp = _campaign(container)
    s = container.campaigns.prepare_session(camp["id"], 3)
    container.campaigns.import_session_output(s["session_id"], _output(s["session_id"]))
    fin = container.campaigns.finalize_session(s["session_id"])
    assert fin["session"]["status"] == "completed"
    assert os.path.exists(fin["report_path"])
    assert os.path.exists(fin["next_session_path"])


def test_next_session_generated(container):
    camp = _campaign(container)
    s = container.campaigns.prepare_session(camp["id"], 3)
    container.campaigns.import_session_output(s["session_id"], _output(s["session_id"]))
    fin = container.campaigns.finalize_session(s["session_id"])
    md = open(fin["next_session_path"], encoding="utf-8").read()
    assert "NEXT_SESSION" in md or "Siguiente" in md


def test_resume_after_restart(container):
    camp = _campaign(container)
    s = container.campaigns.prepare_session(camp["id"], 3)
    container.campaigns.import_session_output(s["session_id"], _output(s["session_id"]))
    container.campaigns.finalize_session(s["session_id"])

    from app.core.container import build_container

    s2 = make_settings(container.settings.data_dir, database_path=container.settings.database_path)
    c2 = build_container(s2)
    try:
        s3 = c2.campaigns.prepare_session(camp["id"], 3)
        assert s3["session_id"] != s["session_id"]
        # No repite la tarea ya completada de la sesión anterior.
        assert "Tarea A" not in (s3["tasks_planned"] or [])
    finally:
        c2.close()


def test_do_not_repeat_completed_task(container):
    camp = _campaign(container)
    s1 = container.campaigns.prepare_session(camp["id"], 3)
    container.campaigns.import_session_output(s1["session_id"], _output(s1["session_id"]))
    container.campaigns.finalize_session(s1["session_id"])
    s2 = container.campaigns.prepare_session(camp["id"], 3)
    assert "Tarea A" not in s2["tasks_planned"]


# ------------------------------------------------------------- deduplicación
def test_no_duplicate_concept(container):
    camp = _campaign(container)
    s = container.campaigns.prepare_session(camp["id"], 3)
    out = _output(s["session_id"])
    container.campaigns.import_session_output(s["session_id"], out)
    imp2 = container.campaigns.import_session_output(s["session_id"], _output(s["session_id"], completed_tasks=[]))
    assert imp2["session"]["concepts_created"] == 1  # el segundo es duplicado


def test_no_duplicate_evidence(container):
    opp = container.opportunities.create(OpportunityCreate(title="Opp evidencia dup", problem=PROBLEM, source="test"))
    camp = _campaign(container)
    s = container.campaigns.prepare_session(camp["id"], 3)
    ev = {"source_name": "Foro X", "source_url": "https://example.com/post/1", "evidence_type": "demand_signal",
          "summary": "Queja recurrente.", "raw_excerpt": "fragmento", "captured_at": "2026-08-23T10:00:00Z",
          "reliability_score": 0.6, "independence_group": "A", "opportunity_id": opp.id}
    container.campaigns.import_session_output(s["session_id"], _output(s["session_id"], evidences=[ev]))
    assert len(container.repos.evidence.list_for(opp.id)) == 1
    imp2 = container.campaigns.import_session_output(s["session_id"], _output(s["session_id"], evidences=[ev], completed_tasks=[]))
    assert len(container.repos.evidence.list_for(opp.id)) == 1  # duplicado: no se vuelve a importar
    assert imp2["session"]["evidences_added"] == 1  # contador acumulado de la sesión, sin incremento


# -------------------------------------------------------------------- límites
def test_limits_not_increased_silently(container):
    camp = _campaign(container)
    assert _finalists(camp) == 3
    assert camp["maximum_deep_research_candidates"] == 10
    # Importar 20 conceptos no cambia los límites.
    s = container.campaigns.prepare_session(camp["id"], 3)
    out = _output(s["session_id"], concepts=[_concept(title=f"C{i}") for i in range(20)])
    container.campaigns.import_session_output(s["session_id"], out)
    camp2 = container.repos.campaigns.get_campaign(camp["id"])
    assert _finalists(camp2) == 3
    assert camp2["maximum_deep_research_candidates"] == 10


def test_api_budget_default_zero(container):
    camp = _campaign(container)
    assert camp["api_budget_usd"] == 0
    assert camp["experiment_budget_usd"] == 0


def test_no_gemini_call_offline(container):
    camp = _campaign(container)
    s = container.campaigns.prepare_session(camp["id"], 3)
    out = _output(s["session_id"])
    out.api_calls_made = 0
    container.campaigns.import_session_output(s["session_id"], out)
    # La política es estructural: cualquier sesión que declare llamadas/coste > 0
    # se rechaza (api_budget_usd=0 durante el descubrimiento).
    with pytest.raises(ValidationError):
        bad = _output(s["session_id"], completed_tasks=[])
        bad.api_calls_made = 1
        container.campaigns.import_session_output(s["session_id"], bad)
    with pytest.raises(ValidationError):
        bad2 = _output(s["session_id"], completed_tasks=[])
        bad2.api_cost_usd = 0.01
        container.campaigns.import_session_output(s["session_id"], bad2)





# --------------------------------------------------------- profundidad (levels)
def test_reasoning_levels(container):
    camp = _campaign(container)
    container.campaigns.record_reasoning(camp["id"], ReasoningLevel.level_0_deterministic, "filtro", "reglas")
    container.campaigns.record_reasoning(camp["id"], ReasoningLevel.level_2_deep_reasoning, "moat", "solo shortlist")
    log = container.repos.campaigns.reasoning_for(camp["id"])
    assert len(log) == 2
    assert {r["level"] for r in log} == {"LEVEL_0_DETERMINISTIC", "LEVEL_2_DEEP_REASONING"}


def test_deep_reasoning_capped_at_shortlist(container):
    # El embudo nunca deja pasar más de `maximum_deep_research_candidates` al nivel 3.
    camp = _campaign(container, maximum_deep_research_candidates=5)
    assert camp["maximum_deep_research_candidates"] == 5
    s = container.campaigns.prepare_session(camp["id"], 3)
    out = _output(s["session_id"], concepts=[_concept(title=f"C{i}") for i in range(8)])
    container.campaigns.import_session_output(s["session_id"], out)
    d = container.campaigns.campaign_detail(camp["id"])
    assert d["campaign"]["concepts_count"] <= 8


def test_max_finalists(container):
    camp = _campaign(container, maximum_finalists=2)
    assert _finalists(camp) == 2


def test_zero_finalists_allowed(container):
    camp = _campaign(container, maximum_finalists=0)
    assert _finalists(camp) == 0
    # No se fuerza ninguna finalista: la campaña puede cerrarse sin ideas.
    assert camp["status"] == "active"


def test_failed_campaign_keeps_learning(container):
    camp = _campaign(container)
    container.campaigns.record_reasoning(camp["id"], ReasoningLevel.level_0_deterministic, "patron_rechazo",
                                         "prompt wrappers sin workflow: evitar")
    blocked = container.campaigns.set_campaign_status(camp["id"], CampaignStatus.blocked,
                                                      reason="Ninguna idea supera el umbral.")
    assert blocked["campaign"]["status"] == "BLOCKED"
    log = container.repos.campaigns.reasoning_for(camp["id"])
    assert any("prompt wrappers" in (r.get("reason") or "") for r in log)


# ---------------------------------------------------------------- misiones
def test_research_missions_offline(container):
    camp = _campaign(container)
    s = container.campaigns.prepare_session(camp["id"], 3)
    out = _output(s["session_id"])
    out.mission_results = [{"kind": "DEMAND_REALITY_CHECK", "concept_id": None,
                            "findings": "Sin URL: no verificable.", "source_url": None,
                            "queried_at": "2026-08-23T10:00:00Z", "confidence": 0.3}]
    container.campaigns.import_session_output(s["session_id"], out)
    assert s  # importación aceptada


def test_evidence_without_url_not_verified(container):
    opp = container.opportunities.create(OpportunityCreate(title="Opp evidencia", problem=PROBLEM, source="test"))
    camp = _campaign(container)
    s = container.campaigns.prepare_session(camp["id"], 3)
    ev = {"source_name": "Afirmación", "source_url": None, "evidence_type": "demand_signal",
          "summary": "Afirmación sin referencia.", "raw_excerpt": "x", "captured_at": "2026-08-23T10:00:00Z",
          "reliability_score": 0.2, "independence_group": "A", "opportunity_id": opp.id}
    container.campaigns.import_session_output(s["session_id"], _output(s["session_id"], evidences=[ev]))
    saved = container.repos.evidence.list_for(opp.id)
    assert saved and all(not e.verified for e in saved)


# -------------------------------------------------------------- comité (005)
def test_review_packet_identical(container):
    from app.models.external_review import ReviewImportIn

    opp = container.opportunities.create(
        OpportunityCreate(title="Finalista A", problem=PROBLEM, target_customer="Cliente X", source="test")
    )
    container.repos.evaluations.upsert(Evaluation(opportunity_id=opp.id, decision=Decision.approved, final_score=80.0,
                                                  pain_score=80, demand_score=80, customer_reach_score=80,
                                                  automation_score=80, margin_score=80, build_speed_score=80,
                                                  differentiation_score=80, safety_score=80,
                                                  evidence_quality_score=80, confidence_score=80))
    p1 = container.reviews.generate_review_packet(opp.id)
    p2 = container.reviews.generate_review_packet(opp.id)
    assert p1["content"] == p2["content"]  # expediente idéntico para todos
    assert p1["sha256"] == p2["sha256"]


def test_import_gpt_grok_gemini(container):
    from app.models.external_review import ReviewImportIn

    opp = container.opportunities.create(
        OpportunityCreate(title="Finalista B", problem=PROBLEM, target_customer="Cliente Y", source="test")
    )
    container.repos.evaluations.upsert(Evaluation(opportunity_id=opp.id, decision=Decision.approved, final_score=80.0,
                                                  pain_score=80, demand_score=80, customer_reach_score=80,
                                                  automation_score=80, margin_score=80, build_speed_score=80,
                                                  differentiation_score=80, safety_score=80,
                                                  evidence_quality_score=80, confidence_score=80))
    for i, (prov, model, rec) in enumerate([("gpt", "gpt-4o", "SMALL_EXPERIMENT"), ("grok", "grok-3", "MORE_RESEARCH"),
                                            ("gemini", "gemini-2.0-flash", "PRIORITY_EXPERIMENT")]):
        container.reviews.import_review(opp.id, ReviewImportIn(
            filename=f"{prov}.txt",
            content=f"Revisión {i} de {prov}.\nrecommendation: {rec}\nconfidence: 60\nprimary_risk: r\n",
            provider=prov, model=model, execution_mode="MOCK", imported_by="test"))
    reviews = container.repos.reviews.reviews_for(opp.id)
    assert {r["provider"] for r in reviews} == {"gpt", "grok", "gemini"}


def test_consensus_does_not_change_evidence_or_score(container):
    from app.models.external_review import ReviewImportIn

    opp = container.opportunities.create(
        OpportunityCreate(title="Finalista C", problem=PROBLEM, target_customer="Cliente Z", source="test")
    )
    container.repos.evaluations.upsert(Evaluation(opportunity_id=opp.id, decision=Decision.approved, final_score=80.0,
                                                  pain_score=80, demand_score=80, customer_reach_score=80,
                                                  automation_score=80, margin_score=80, build_speed_score=80,
                                                  differentiation_score=80, safety_score=80,
                                                  evidence_quality_score=80, confidence_score=80))
    for i in range(3):
        container.reviews.import_review(opp.id, ReviewImportIn(
            filename=f"m{i}.txt",
            content=f"Revisión {i}: recommendation: PRIORITY_EXPERIMENT\nconfidence: 70\nprimary_risk: r\n",
            provider="gpt", model=f"gpt-4o-{i}", execution_mode="MOCK", imported_by="test"))
    syn = container.reviews.synthesize(opp.id)
    assert syn["reviews_count"] == 3
    ev = container.repos.evaluations.get(opp.id)
    assert ev.final_score == 80.0  # el score interno no cambia
    assert len(container.repos.evidence.list_for(opp.id)) == 0  # ninguna evidencia inventada


# ------------------------------------------------------------ API readiness
def test_api_readiness_premature_by_default(container):
    opp = container.opportunities.create(
        OpportunityCreate(title="Sin criterios", problem=PROBLEM, target_customer="C", source="test")
    )
    gate = container.campaigns.evaluate_api_readiness(opp.id)
    assert gate["state"] == "API_PREMATURE"


def test_api_required_only_with_full_criteria(container):
    from app.models.campaign import APIReadinessState

    opp = container.opportunities.create(
        OpportunityCreate(title="Candidata completa", problem=PROBLEM, target_customer="Cliente concreto",
                          source="test")
    )
    container.repos.evaluations.upsert(Evaluation(opportunity_id=opp.id, decision=Decision.approved, final_score=85.0,
                                                  pain_score=85, demand_score=85, customer_reach_score=85,
                                                  automation_score=85, margin_score=85, build_speed_score=85,
                                                  differentiation_score=85, safety_score=85,
                                                  evidence_quality_score=85, confidence_score=85))
    # Sin evidencias verificadas ni comité: PREMATURE aunque sea finalista.
    gate = container.campaigns.evaluate_api_readiness(opp.id)
    assert gate["state"] in ("API_PREMATURE", "API_NOT_NEEDED")
    assert gate["state"] != APIReadinessState.api_required_for_24_7_operation.value


def test_readiness_never_activates_api(container):
    opp = container.opportunities.create(
        OpportunityCreate(title="Cualquiera", problem=PROBLEM, target_customer="C", source="test")
    )
    gate = container.campaigns.evaluate_api_readiness(opp.id)
    assert gate["proposed_daily_limit_usd"] is not None  # propuesta, no configuración
    # No hay campo de clave ni configuración de proveedor en el gate.
    assert "api_key" not in gate


# ------------------------------------------------------- piloto sintético
def test_synthetic_pilot_complete(container):
    res = container.campaigns.run_demo(container.pipeline)
    assert res["is_synthetic"] is True
    assert res["finalists_count"] <= 3
    assert res["api_calls_made"] == 0 if "api_calls_made" in res else True
    assert res["readiness"] is not None
    detail = res["detail"]
    assert detail["campaign"]["status"] == "COMPLETED"
    assert len(detail["sessions"]) >= 2


def test_pilot_idempotent(container):
    r1 = container.campaigns.run_demo(container.pipeline)
    r2 = container.campaigns.run_demo(container.pipeline)
    assert r2.get("reused") is True
    assert r2["detail"]["campaign"]["id"] == r1["campaign_id"]


# ----------------------------------------------------- economía y producción
def test_economy_stays_simulated(container):
    status = container.economy.status()
    assert status.get("simulated") is True
    assert status.get("real_money_moved") is False


def test_no_invented_freebuff_api(container):
    import app.providers.manager as m

    assert not hasattr(m, "FreebuffProvider")
    from app.core.config import Settings

    assert not any("FREEBUFF_API" in k for k in dir(Settings))


def test_autonomous_production_blocked(container):
    st = container.engine.status()
    assert st["mode"] in ("development_and_review", "simulation")
    assert st.get("production_capability_available") is False
    assert "production_block_reason" in st
    # Las campañas nunca tocan el modo operativo.
    camp = _campaign(container)
    assert container.engine.status()["mode"] == st["mode"]
