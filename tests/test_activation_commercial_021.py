"""Iteración 021 — Activación comercial: trazabilidad concepto→oportunidad,
importación de investigación verificada, contrato de telemetría de lanzamiento
y readiness honesto. Offline y determinista (sin LLM)."""
from __future__ import annotations

import json

from app.models.enums import Decision
from app.models.evaluation import Evaluation
from app.models.orchestrator import ExperimentPlan


def _verified_evidence() -> dict:
    return {
        "evidence_type": "demand_signal",
        "source_name": "Fuente de prueba",
        "source_url": "https://example.com/fuente",
        "captured_at": "2026-08-26",
        "summary": "Dispersión documentada.",
        "raw_excerpt": "fragmento textual original",
        "reliability_score": 0.8,
        "independence_group": "demand_evidence",
        "verified": True,
        "verification_notes": "URL + fecha + fragmento.",
    }


def _campaign_with_promoted(container) -> tuple[str, str, str]:
    """Campaña real avanzada + reformulación portable (camino documentado 017):
    deja una candidata RESEARCH_PENDING con misiones y oportunidad local."""
    from app.services.reformulation_import import apply_reformulation_plan
    from tests.test_reformulation_import_017 import _valid_brief

    d = container.orchestrator.create_real_campaign()
    rid = d["run"]["id"]
    container.orchestrator.advance(rid)
    dcid = d["run"]["discovery_campaign_id"]
    concepts = container.discovery.campaign_detail(dcid)["concepts"]
    targets = [c for c in concepts if c["status"] == "NEEDS_REFORMULATION"]
    assert targets, "la campaña debe dejar direcciones reformulables"
    plan = {"briefs": [{"concept_id": "foraneo-021", "direccion_original": targets[0]["title"], "brief": _valid_brief()}]}
    applied = apply_reformulation_plan(container, plan, run_id=rid, preview=False)
    assert applied["applied"] == 1, applied
    promoted = [c for c in container.discovery.campaign_detail(dcid)["concepts"] if c["status"] == "RESEARCH_PENDING"]
    assert promoted, "la reformulación debe dejar candidatas RESEARCH_PENDING"
    return dcid, promoted[0]["id"], rid


# ---------------------------------------------------------------------------
# 1. Trazabilidad concepto → oportunidad (get_by_concept por título)
# ---------------------------------------------------------------------------
def test_get_by_concept_resolves_promoted_opportunity(container):
    dcid, concept_id, _rid = _campaign_with_promoted(container)
    concept = container.repos.discovery.get_concept(concept_id)
    opp = container.repos.opportunities.get_by_concept(concept_id)
    assert opp is not None, "la oportunidad promovida debe resolverse por título normalizado"
    # Mismo título normalizado y misma campaña (source discovery:<campaign>).
    import re
    import unicodedata

    def norm(t: str) -> str:
        t = unicodedata.normalize("NFKD", t.lower())
        t = "".join(c for c in t if not unicodedata.combining(c))
        return re.sub(r"[^a-z0-9]+", " ", t).strip()

    assert norm(opp.title) == norm(concept["title"])
    assert opp.source == f"discovery:{dcid}"
    # Sin concepto válido → None (nunca inventa asociación).
    assert container.repos.opportunities.get_by_concept("no-existe") is None


# ---------------------------------------------------------------------------
# 2. Target de misión con opportunity_id (readiness inequívoco)
# ---------------------------------------------------------------------------
def test_update_mission_target_persists_opportunity_id(container):
    dcid, concept_id, _rid = _campaign_with_promoted(container)
    missions = container.repos.discovery.missions_by_campaign(dcid)
    m = next(m for m in missions if (m.get("target") or {}).get("concept_id") == concept_id)
    opp = container.repos.opportunities.get_by_concept(concept_id)
    target = dict(m["target"])
    target["opportunity_id"] = opp.id
    container.repos.discovery.update_mission_target(m["mission_id"], target)
    again = container.repos.discovery.get_mission(m["mission_id"])
    assert again["target"]["opportunity_id"] == opp.id


# ---------------------------------------------------------------------------
# 3. Importación: verified=true SOLO con URL+fecha+fragmento
# ---------------------------------------------------------------------------
def test_mission_import_verifies_only_with_url_date_fragment(container):
    dcid, concept_id, _rid = _campaign_with_promoted(container)
    mission = next(
        m for m in container.repos.discovery.missions_by_campaign(dcid)
        if (m.get("target") or {}).get("concept_id") == concept_id
    )
    from app.models.discovery import MissionIn

    ok = dict(_verified_evidence())
    broken = dict(_verified_evidence())
    broken["raw_excerpt"] = ""  # falta fragmento → NUNCA verified
    broken["source_url"] = "https://example.com/otra"
    res = container.discovery.import_mission_result(
        mission["mission_id"],
        MissionIn(mission_id=mission["mission_id"], evidences=[ok, broken]),
    )
    assert res["verified"] == 1
    assert res["unverified"] == 1
    stored = container.repos.discovery.mission_results(mission["mission_id"])[0]["evidences"]
    by_url = {e["source_url"]: e for e in stored}
    assert by_url["https://example.com/fuente"]["verified"] is True
    assert by_url["https://example.com/otra"]["verified"] is False

    # attach_mission_evidence solo copia las verificadas.
    opp = container.repos.opportunities.get_by_concept(concept_id)
    attached = container.discovery.attach_mission_evidence(opp.id, mission["mission_id"])
    assert attached["evidences_attached"] == 1
    rows = container.repos.evidence.list_for(opp.id)
    assert len(rows) == 1 and rows[0].verified is True


# ---------------------------------------------------------------------------
# 4. Contrato de telemetría de lanzamiento (sin secretos, sin inventar)
# ---------------------------------------------------------------------------
def test_telemetry_launch_contract_honest(container):
    telemetry = container.command_center.agent_telemetry()
    assert "launch_winner" in telemetry
    assert isinstance(telemetry["services_required"], list)
    assert telemetry["authorization_mandate"]["state"] == "PENDING_OWNER_AUTHORIZATION"
    assert telemetry["authorization_mandate"]["duration_days"] == 30
    assert "Gasto real sin autorización" in telemetry["authorization_mandate"]["blocked_actions"]
    # Servicios pendientes: MISSING y sin valores de credenciales.
    joined = json.dumps(telemetry)
    assert "sk_live" not in joined and "sk_test" not in joined
    for svc in telemetry["services_required"]:
        assert svc["status"] in ("MISSING", "CONNECTED", "INVALID", "EXPIRED")
        assert "value" not in svc  # nunca se expone el contenido de la credencial


# ---------------------------------------------------------------------------
# 5. Readiness honesto: READY_TO_CONNECT_SERVICES solo con todas las
#    precondiciones; producción siempre bloqueada.
# ---------------------------------------------------------------------------
def _make_ready(container, run_id: str, dcid: str, concept_id: str) -> str:
    concept = container.repos.discovery.get_concept(concept_id)
    opp = container.repos.opportunities.get_by_concept(concept_id)
    missions = [
        m for m in container.repos.discovery.missions_by_campaign(dcid)
        if (m.get("target") or {}).get("concept_id") == concept_id
    ]
    from app.models.discovery import MissionIn

    for m in missions:
        container.discovery.import_mission_result(
            m["mission_id"],
            MissionIn(mission_id=m["mission_id"], evidences=[dict(_verified_evidence())]),
        )
        container.discovery.attach_mission_evidence(opp.id, m["mission_id"])
    venture = container.discovery._evaluate_venture(concept, dcid)["venture"]
    groups = {getattr(e, "independence_group", "x") for e in container.repos.evidence.list_for(opp.id) if getattr(e, "verified", False)}
    container.repos.evaluations.upsert(
        Evaluation(
            opportunity_id=opp.id,
            pain_score=float(venture.get("economic_pain") or 0.0),
            demand_score=float(venture.get("proven_demand") or 0.0),
            customer_reach_score=float(venture.get("distribution") or 0.0),
            automation_score=float(venture.get("operational_simplicity") or 0.0),
            margin_score=float(venture.get("gross_margin") or 0.0),
            build_speed_score=float(venture.get("validation_speed") or 0.0),
            differentiation_score=50.0,
            safety_score=100.0,
            evidence_quality_score=min(100.0, float(len(groups)) * 10.0),
            confidence_score=float(venture.get("evidence_backed_venture_score") or 0.0),
            final_score=float(venture.get("evidence_backed_venture_score") or 0.0),
            per_criterion={},
            independent_evidence_count=len(groups),
            unverified_assumptions_count=3,
            assumptions=["Hipótesis de comprador y presupuesto."],
            blockers=[],
            approval_reason="Evidencia verificada + sin bloqueadores.",
            rejection_reason=None,
            decision=Decision.approved,
            model_or_method="test_021",
            skeptic_critique=None,
            risks=[],
            estimates=__import__("app.models.evaluation", fromlist=["Estimates"]).Estimates(),
            experiment=None,
        )
    )
    container.repos.orchestrator.create_experiment_plan(
        ExperimentPlan(
            run_id=run_id,
            opportunity_id=opp.id,
            decision="approved",
            offer="Informe de benchmark por provincia.",
            buyer="Comprador concreto de prueba",
            user="Usuario de prueba",
            problem="Problema de prueba.",
            value_proposition="Valor de prueba.",
            price_usd=60.0,
            delivery_format="PDF",
            demo="demo",
            channel="Canal concreto de prueba",
            initial_message="hola",
            min_sample=3,
            max_contacts=20,
            acquisition_method="manual autorizado",
            max_cost_usd=0.0,
            duration_days=30,
            success_metric="primer pago real confirmado",
            success_threshold="1 pago",
            kill_condition="sin señal de pago",
            product_death_condition="sin pago y sin pivote",
            possible_pivots=[],
            automatable_tasks=[],
            owner_tasks=[],
            risks=[],
            dependencies=[],
            payment_readiness="PENDIENTE",
            missing_capabilities=[],
            blockers=[],
        )
    )
    container.repos.orchestrator.update_run(run_id, selected_opportunity_id=opp.id)
    return opp.id


def test_readiness_reaches_ready_to_connect_services_only_with_all_preconditions(container):
    dcid, concept_id, rid = _campaign_with_promoted(container)

    # Antes de preparar: NOT_READY (faltan precondiciones) — nunca READY por existir misiones.
    snap_before = container.command_center.snapshot()
    assert snap_before["autonomous_launch"]["state"] in ("NOT_READY", "BLOCKED")
    assert snap_before["autonomous_launch"]["ready_to_launch"] is False

    opp_id = _make_ready(container, rid, dcid, concept_id)

    snap = container.command_center.snapshot()
    readiness = snap["autonomous_launch"]
    assert readiness["state"] == "READY_TO_CONNECT_SERVICES"
    assert readiness["readiness_missing"] == []
    assert readiness["readiness_blockers"] == []
    assert readiness["candidate_id"] == opp_id
    assert readiness["experiment_id"]
    # Producción continúa bloqueada por diseño.
    assert readiness["conditions"]["production_remains_blocked"] is True
    assert readiness["conditions"]["services_connected"] is False
    assert readiness["conditions"]["owner_authorized"] is False
    assert snap["permissions"]["autonomous_production"] is False
    # Evidencia verificada contada, no inventada.
    assert snap["evidence"]["verified"] >= 1
    assert snap["evidence"]["unverified"] == 0


def test_readiness_blocks_without_price_hypothesis(container):
    dcid, concept_id, rid = _campaign_with_promoted(container)
    opp_id = _make_ready(container, rid, dcid, concept_id)
    # Romper la hipótesis de precio: sin precio positivo nunca es READY.
    plan = container.repos.orchestrator.experiment_plan_for_opportunity(opp_id)
    container.conn.execute(
        "UPDATE experiment_plans SET price_usd = 0 WHERE id = ?", (plan["id"],)
    )
    container.conn.commit()
    snap = container.command_center.snapshot()
    assert snap["autonomous_launch"]["state"] == "NOT_READY"
    assert "price_hypothesis" in snap["autonomous_launch"]["readiness_missing"]
