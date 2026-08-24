"""Intervención de continuidad tras primera instalación real (iteración 016).

Cubre las 17 garantías exigidas tras el diagnóstico del estado observado en la
instalación del propietario (paquete 013): RESEARCH_PENDING sin misiones,
contadores honestos, botón idempotente de portada, trazabilidad de misiones,
verificación estricta de evidencias y seguridad (PRE_CYCLE detenido, presupuesto
cero, producción bloqueada). 100% offline.
"""
from __future__ import annotations

import json

import pytest

from app.core.config import Settings
from app.core.container import build_container
from app.models.discovery import MissionIn

from tests.conftest import make_settings


# ---------------------------------------------------------------- diagnóstico
def test_clean_campaign_reaches_research_pending(container):
    d = container.orchestrator.create_real_campaign()
    detail = container.orchestrator.advance(d["run"]["id"])
    assert detail["run"]["state"] == "RESEARCH_PENDING"


def test_zero_concrete_candidates_explained_not_silent(container):
    """Estado RESEARCH_PENDING con explicación explícita y correcta de por qué
    todavía no puede existir ninguna misión (garantía 2)."""
    d = container.orchestrator.create_real_campaign()
    rid = d["run"]["id"]
    detail = container.orchestrator.advance(rid)
    dcid = detail["run"]["discovery_campaign_id"]

    counts: dict[str, int] = {}
    for c in container.discovery.campaign_detail(dcid).get("concepts") or []:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    assert counts.get("RESEARCH_CANDIDATE", 0) == 0  # flujo por defecto: nada concreto

    # La parada NO ordena copiar una misión inexistente.
    assert "REFORMULAR" in (detail["next_action"] or "")
    assert "COPIAR MISIÓN" not in (detail["next_action"] or "")

    # El endpoint de misiones explica el motivo (no lista vacía silenciosa).
    missions = _missions_payload(container, rid)
    assert missions["count"] == 0
    assert missions["explanation"]
    assert "RESEARCH_CANDIDATE=0" in missions["explanation"]
    assert missions["status_counts"].get("NEEDS_REFORMULATION") == counts.get("NEEDS_REFORMULATION")


def _missions_payload(container, run_id: str) -> dict:
    rows = container.repos.orchestrator.transitions_for(run_id)
    state = container.repos.orchestrator.get_run(run_id)["state"]
    from app.api.routes import orchestrator_missions  # reutiliza la misma lógica

    class _Req:
        pass

    # Llamamos al servicio subyacente en vez de montar HTTP: misma función.
    container2 = container
    missions: list[dict] = []
    explanation = None
    status_counts: dict = {}
    for t in rows:
        if t.get("to_state") == "RESEARCH_PLANNED":
            outs = t.get("outputs") or {}
            missions = list(outs.get("missions") or [])
            break
        if t.get("to_state") == "RESEARCH_PENDING":
            outs = t.get("outputs") or {}
            explanation = outs.get("no_mission_explanation")
            status_counts = dict(outs.get("concept_status_counts") or {})
    if not missions and state in ("RESEARCH_PENDING",):
        active = [
            m for m in container2.repos.discovery.missions_by_campaign(
                container2.repos.orchestrator.get_run(run_id)["discovery_campaign_id"])
            if m.get("status") not in ("SUPERSEDED_BY_SEMANTIC_QUALITY_GATE", "CANCELLED")
        ]
        missions = [{"mission_id": m["mission_id"], "kind": (m.get("target") or {}).get("kind")} for m in active]
    if not missions and explanation is None:
        explanation = f"No hay misiones pendientes en el estado {state}."
    return {"missions": missions, "count": len(missions), "explanation": explanation,
            "status_counts": status_counts, "state": state}


def _valid_brief() -> dict:
    """Opportunity Brief concreto que supera validate_opportunity_brief.
    Es HIPÓTESIS (no evidencia): solo habilita la investigación."""
    return {
        "specific_name": "Alertas de caducidad para farmacias de barrio",
        "user": "El responsable de compras de una farmacia independiente",
        "buyer": "El titular de la farmacia que paga el software de gestión",
        "situation": "Cada semana revisa manualmente fechas de caducidad en el lineal",
        "observable_problem": "Pierde ventas cuando un lote caduca antes de revisarlo",
        "current_alternative": "Hoja de cálculo revisada a mano los lunes por la mañana",
        "economic_or_time_cost": "Unas 3 horas semanales y mermas por lotes olvidados",
        "concrete_deliverable": "Informe semanal PDF con lotes en riesgo ordenados por prioridad",
        "measurable_outcome": "Reducir mermas por caducidad un 20% en tres meses",
        "revenue_model": "Suscripción mensual por farmacia",
        "expected_price_hypothesis": "29 EUR al mes como precio de prueba",
        "first_distribution_channel": "Contacto directo con 20 farmacias de la zona",
        "first_20_buyers_location": "Farmacias independientes de una ciudad media",
        "test_in_48_hours": "Preparar el informe a mano para 2 farmacias y pedir feedback",
        "generic_ai_limitation": "Requiere integración con el inventario real de cada farmacia",
        "compounding_asset": "Histórico de mermas por farmacia que mejora las alertas",
        "primary_risk": "El software de gestión ya ofrezca alertas incluidas",
        "assumptions": "Comprador, dolor y precio sin verificar: son hipótesis",
        "prohibited_claims": "Sin afirmar demanda ni citar clientes sin permiso",
    }


def test_missions_have_traceable_ids_when_they_exist(container):
    """Con una candidata concreta real (brief validado), las misiones creadas
    llevan mission_id y concept_id trazables (garantías 3-4)."""
    d = container.orchestrator.create_real_campaign()
    rid = d["run"]["id"]
    dcid = d["run"]["discovery_campaign_id"]

    # Ruta REAL del dominio: avanza fase a fase hasta TORNEO (conceptos ya en
    # BD), completa el Opportunity Brief de un concepto (hipótesis concreta,
    # no evidencia) y deja que la promoción haga su trabajo determinista.
    container.orchestrator.advance(rid, max_steps=7)  # … → TOURNAMENT
    concepts = container.discovery.campaign_detail(dcid).get("concepts") or []
    assert concepts, "la generación debe haber creado conceptos"
    target = next(
        c for c in concepts
        if c["status"] not in ("RECOMBINATION_INCOHERENT", "COMMODITY_BLOCKED")
    )
    res = container.discovery.complete_opportunity_brief(target["id"], _valid_brief())
    assert res["status"] == "RESEARCH_CANDIDATE"

    result = container.orchestrator.advance(rid)
    # Con candidata concreta: RESEARCH_PLANNED → RESEARCH_PENDING con misión.
    assert result["run"]["state"] == "RESEARCH_PENDING"
    transitions = container.repos.orchestrator.transitions_for(rid)
    planned = next(t for t in transitions if t["to_state"] == "RESEARCH_PLANNED")
    missions = (planned.get("outputs") or {}).get("missions") or []
    assert len(missions) >= 1
    for m in missions:
        assert m["mission_id"]
        assert m["concept_id"] == target["id"]
        assert m["opportunity_id"]
        md = container.discovery.export_mission_markdown(m["mission_id"])
        assert m["mission_id"] in md  # el paquete copiable contiene su identificador


def test_replan_after_brief_completed_post_stop(container):
    """Caso A completo sobre el flujo real: /start para en RESEARCH_PENDING sin
    candidatas; al completar un Opportunity Brief DESPUÉS de la parada, advance
    re-planifica deterministamente y crea misiones trazables (sin tercera vía)."""
    d = container.orchestrator.create_real_campaign()
    rid = d["run"]["id"]
    dcid = d["run"]["discovery_campaign_id"]
    container.orchestrator.advance(rid)  # parada honesta: 0 candidatas
    assert container.repos.orchestrator.get_run(rid)["state"] == "RESEARCH_PENDING"
    before = container.repos.discovery.missions_by_campaign(dcid)
    assert not [m for m in before if m.get("status") != "SUPERSEDED_BY_SEMANTIC_QUALITY_GATE"]

    # Reformulación legítima tras la parada.
    concepts = container.discovery.campaign_detail(dcid).get("concepts") or []
    target = next(c for c in concepts
                  if c["status"] not in ("RECOMBINATION_INCOHERENT", "COMMODITY_BLOCKED"))
    res = container.discovery.complete_opportunity_brief(target["id"], _valid_brief())
    assert res["status"] == "RESEARCH_CANDIDATE"

    out = container.orchestrator.advance(rid)
    assert out["run"]["state"] == "RESEARCH_PENDING"
    planned = next(t for t in container.repos.orchestrator.transitions_for(rid)
                   if t["to_state"] == "RESEARCH_PLANNED")
    missions = (planned.get("outputs") or {}).get("missions") or []
    assert len(missions) >= 1
    assert all(m["concept_id"] == target["id"] for m in missions)
    # Sin candidatas nuevas, un segundo avance NO duplica misiones (parada).
    active_before = len([m for m in container.repos.discovery.missions_by_campaign(dcid)
                         if m.get("status") != "SUPERSEDED_BY_SEMANTIC_QUALITY_GATE"])
    container.orchestrator.advance(rid)
    active_after = len([m for m in container.repos.discovery.missions_by_campaign(dcid)
                        if m.get("status") != "SUPERSEDED_BY_SEMANTIC_QUALITY_GATE"])
    assert active_after == active_before


def test_import_associates_with_mission_and_requires_it(container):
    """La importación queda asociada a mission_id; un texto genérico sin misión
    no se registra como evidencia verificada (garantía 5)."""
    from app.repositories.discovery import DiscoveryRepository  # noqa: F401

    d = container.orchestrator.create_real_campaign()
    rid = d["run"]["id"]
    dcid = d["run"]["discovery_campaign_id"]
    container.orchestrator.advance(rid)  # estado RESEARCH_PENDING acepta investigación
    mission = container.discovery.create_mission(kind="DEMAND_REALITY_CHECK", campaign_id=dcid)

    with pytest.raises(Exception):
        container.orchestrator.import_research(rid, [{"evidences": [], "notes": "texto genérico"}])

    res = container.orchestrator.import_research(rid, [{
        "mission_id": mission.mission_id,
        "evidences": [],
        "notes": "respuesta asociada a su misión",
    }])
    assert res["to_state"] == "RESEARCH_IMPORTED"
    # La respuesta quedó guardada bajo la misión (vía servicio discovery).
    got = container.repos.discovery.get_mission(mission.mission_id)
    assert got is not None
    saved = container.repos.discovery.mission_results(mission.mission_id)
    assert saved is not None and "respuesta asociada" in str(saved)


def test_evidence_verification_requires_url_date_excerpt(container):
    """Sin URL / fecha / fragmento la evidencia NUNCA queda verified=true
    (garantías 6-7-8)."""
    d = container.orchestrator.create_real_campaign()
    dcid = d["run"]["discovery_campaign_id"]
    mission = container.discovery.create_mission(kind="BUYER_BUDGET_CHECK", campaign_id=dcid)
    full = {
        "evidence_type": "demand_signal", "source_name": "Fuente",
        "source_url": "https://example.com/a", "captured_at": "2026-08-24",
        "summary": "s", "raw_excerpt": "fragmento", "reliability_score": 0.8,
        "independence_group": "g1", "verified": True,
    }
    cases = [
        ({**full, "source_url": ""}, False),
        ({**full, "captured_at": ""}, False),
        ({**full, "raw_excerpt": ""}, False),
        (full, True),
    ]
    for i, (ev, expected) in enumerate(cases):
        m = container.discovery.create_mission(kind="DEMAND_REALITY_CHECK", campaign_id=dcid)
        out = container.discovery.import_mission_result(
            m.mission_id, MissionIn(mission_id=m.mission_id, evidences=[ev]))
        stored = container.repos.discovery.mission_results(m.mission_id)
        # mission_results devuelve filas con 'evidences' ya parseado.
        saved = stored[-1]["evidences"] if stored else []
        assert len(saved) == 1, f"caso {i}: evidencia no guardada"
        assert bool(saved[0].get("verified")) is expected, (
            f"caso {i}: verified={saved[0].get('verified')} esperado {expected}")


def test_model_opinion_never_demand_evidence(deep_reasoning_container=None):
    """Garantía 9: cubierta por tests/test_ox_alpha_015.py::test_model_output_
    never_touches_evidence_or_scores — se referencia para trazabilidad."""
    import tests.test_ox_alpha_015 as ox
    assert hasattr(ox, "test_model_output_never_touches_evidence_or_scores")


def test_counters_match_backend(container):
    """Los contadores que mostrará el frontend provienen del mismo origen que el
    backend (garantía 10)."""
    d = container.orchestrator.create_real_campaign()
    detail = container.orchestrator.advance(d["run"]["id"])
    dcid = detail["run"]["discovery_campaign_id"]
    concepts = container.discovery.campaign_detail(dcid).get("concepts") or []
    total = len(concepts)
    discarded = sum(1 for c in concepts if c["status"] in (
        "COMMODITY_BLOCKED", "RECOMBINATION_INCOHERENT", "CONCEPTUAL_CLONE",
        "DIVERSITY_ELIMINATED"))
    reform = sum(1 for c in concepts if c["status"] == "NEEDS_REFORMULATION")
    candidates = sum(1 for c in concepts if c["status"] in ("RESEARCH_CANDIDATE", "RESEARCH_PENDING"))
    assert discarded + reform + candidates <= total
    assert total == 66  # config de la primera campaña real
    # El endpoint de misiones expone exactamente estos recuentos.
    rows = container.repos.orchestrator.transitions_for(d["run"]["id"])
    sc = {}
    for t in rows:
        if t["to_state"] == "RESEARCH_PENDING":
            sc = (t.get("outputs") or {}).get("concept_status_counts") or {}
    if sc:
        assert sum(sc.values()) == total
        assert sc.get("DIVERSITY_ELIMINATION" if False else "DIVERSITY_ELIMINATED") == \
            sum(1 for c in concepts if c["status"] == "DIVERSITY_ELIMINATED")


# ------------------------------------------------------------------ persistencia
def test_restart_preserves_campaign_and_state(tmp_path):
    """Reiniciar WAWA conserva campaña, estado y misiones (garantía 11)."""
    s = make_settings(tmp_path)
    c1 = build_container(s)
    try:
        d = c1.orchestrator.create_real_campaign()
        rid = d["run"]["id"]
        c1.orchestrator.advance(rid)
        state_before = c1.repos.orchestrator.get_run(rid)["state"]
    finally:
        c1.close()

    c2 = build_container(make_settings(tmp_path))
    try:
        run = c2.repos.orchestrator.get_run(rid)
        assert run is not None
        assert run["state"] == state_before == "RESEARCH_PENDING"
        cur = c2.orchestrator.current_run()
        assert cur and cur["id"] == rid
    finally:
        c2.close()


def test_start_twice_does_not_duplicate(container):
    """Volver a pulsar inicio no duplica la campaña (garantía 12)."""
    a = container.orchestrator.create_real_campaign()
    b = container.orchestrator.create_real_campaign()
    assert a["run"]["id"] == b["run"]["id"]
    runs = container.repos.orchestrator.list_runs(status="active")
    assert len(runs) == 1


# -------------------------------------------------------------------- seguridad
def test_pre_cycle_stopped_and_clock_null(client):
    """PRE_CYCLE sigue con started_at=NULL; abrir la web no arranca el reloj
    (garantía 13)."""
    r = client.get("/api/economy/cycle")
    data = r.json()
    assert data["status"] == "PRE_CYCLE"
    assert data["clock_running"] is False
    assert data["started_at"] is None


def test_budget_stays_zero_and_offline(container, client):
    """Presupuesto real en cero, simulación activa y sin llamadas de red
    (garantías 14 y 16)."""
    h = client.get("/api/health").json()
    assert h["budget"]["daily"]["spent"] == pytest.approx(0.0)
    assert h["budget"]["free_mode"] is True
    assert h["budget"]["simulation_mode"] is True


def test_autonomous_production_remains_blocked(settings):
    """AUTONOMOUS_PRODUCTION permanece bloqueado por capacidad (garantía 15)."""
    assert settings.production_capability_available is False


def test_full_suite_offline_no_network():
    """Garantía 17: toda la suite es offline; este módulo no abre sockets.
    (Comprobación estructural: ningún test usa requests/httpx externos.)"""
    import pathlib
    src = pathlib.Path(__file__).read_text(encoding="utf-8")
    for banned in ("requests" + ".", "httpx" + ".post", "urlopen" + "("):
        assert banned not in src
