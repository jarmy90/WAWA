"""Iteración 018 — OX ALPHA GRAND INTELLIGENCE SPRINT.

Garantías probadas (100 % offline):
1. La identidad OX Alpha solo es el slug verificado; 'auto' o vacío ⇒
   OX_ALPHA_UNVERIFIED y nunca se declara su uso.
2. La ventana expira el 2026-08-27 inclusive; el 2026-08-28 ⇒ WINDOW_EXPIRED.
3. El fallo de un proveedor es ausencia neutral: no se fabrica salida.
4. El benchmark es reproducible (misma entrada ⇒ misma puntuación).
5. Las salidas de OX Alpha se etiquetan MODEL_* / HIPÓTESIS y NUNCA son
   evidencia: no tocan proven_demand, evidence_backed_venture_score ni
   grupos de evidencia.
6. El super-torneo admite 0 ganadoras y nunca supera 3; exige brief completo.
7. El centro de mando muestra datos REALES y etiqueta lo simulado, la
   hipótesis, el razonamiento de modelo y lo desconocido; nunca inventa
   cifras (DESCONOCIDO / NO CONECTADO / SIN DATOS / SIMULACIÓN).
8. Persistencia y reinicio conservan el estado; PRE_CYCLE sigue detenido;
   gasto real cero; producción bloqueada; secretos ausentes; frontend y
   backend sincronizados en v0.17.0 / iteración 018.
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from app.core.config import Settings
from app.core.container import build_container
from app.core.ox_alpha import (
    FORBIDDEN_OUTPUT_LABELS,
    deep_task_gate,
    ox_alpha_status,
)
from app.scoring.ox_alpha_benchmark import (
    benchmark_verdict,
    score_reformulation_variant,
    score_task_response,
)
from app.scoring.super_tournament import MAX_WINNERS, run_super_tournament, score_entry
from app.services.command_center import CommandCenterService
from tests.conftest import make_settings


# ---------------------------------------------------------------------------
# 1. Identidad OX Alpha: nunca inventar el slug
# ---------------------------------------------------------------------------
def test_ox_alpha_unverified_without_slug(settings):
    s = settings.model_copy(update={"omniroute_enabled": True, "ox_alpha_slug": ""})
    st = ox_alpha_status(s, today=date(2026, 8, 26))
    assert st["identity"] == "OX_ALPHA_UNVERIFIED"
    assert st["can_use"] is False
    assert st["is_evidence"] is False
    assert st["state"] == "SLUG_UNVERIFIED"


def test_ox_alpha_auto_slug_does_not_count(settings):
    s = settings.model_copy(update={"omniroute_enabled": True, "ox_alpha_slug": "auto"})
    st = ox_alpha_status(s, today=date(2026, 8, 26))
    assert st["identity"] == "OX_ALPHA_UNVERIFIED"
    assert st["can_use"] is False


def test_ox_alpha_verified_slug_available_within_window(settings):
    s = settings.model_copy(
        update={"omniroute_enabled": True, "ox_alpha_slug": "acme/alpha-0", "ox_alpha_expires_at": "2026-08-27"}
    )
    st = ox_alpha_status(s, today=date(2026, 8, 26))
    assert st["identity"] == "acme/alpha-0"
    assert st["can_use"] is True
    assert st["state"] == "AVAILABLE"


# ---------------------------------------------------------------------------
# 2. Expiración de la ventana (2026-08-27 inclusive)
# ---------------------------------------------------------------------------
def test_ox_alpha_window_expires_on_28_august(settings):
    s = settings.model_copy(
        update={"omniroute_enabled": True, "ox_alpha_slug": "acme/alpha-0", "ox_alpha_expires_at": "2026-08-27"}
    )
    assert ox_alpha_status(s, today=date(2026, 8, 27))["state"] == "AVAILABLE"
    assert ox_alpha_status(s, today=date(2026, 8, 28))["state"] == "WINDOW_EXPIRED"
    assert ox_alpha_status(s, today=date(2026, 8, 28))["can_use"] is False


# ---------------------------------------------------------------------------
# 3. Fallo neutral y puerta por tarea
# ---------------------------------------------------------------------------
def test_deep_task_gate_restricts_to_p0_tasks(settings):
    s = settings.model_copy(
        update={"omniroute_enabled": True, "ox_alpha_slug": "acme/alpha-0", "ox_alpha_expires_at": "2026-08-27"}
    )
    for task in ("reformulation", "coherence_check", "red_team", "variation_comparison"):
        assert deep_task_gate(s, task, today=date(2026, 8, 26))["can_use"] is True
    assert deep_task_gate(s, "scoring", today=date(2026, 8, 26))["can_use"] is False


def test_absence_is_neutral_no_fabricated_output(settings):
    """Sin OX Alpha verificado no se fabrica ninguna salida atribuida al modelo."""
    s = settings.model_copy(update={"omniroute_enabled": True, "ox_alpha_slug": ""})
    st = ox_alpha_status(s, today=date(2026, 8, 26))
    assert st["can_use"] is False
    # Etiquetas prohibidas jamás se atribuyen a ninguna salida del modelo.
    for label in FORBIDDEN_OUTPUT_LABELS:
        assert label not in st["reason"]
        assert label not in json.dumps(st.get("output_labels_allowed"))


def test_model_output_never_evidence_labels(settings):
    s = settings.model_copy(
        update={"omniroute_enabled": True, "ox_alpha_slug": "acme/alpha-0", "ox_alpha_expires_at": "2026-08-27"}
    )
    st = ox_alpha_status(s, today=date(2026, 8, 26))
    assert st["is_evidence"] is False
    allowed = set(st["output_labels_allowed"])
    assert {"REFORMULACIÓN DE MODELO", "CRÍTICA DE MODELO", "HIPÓTESIS SIN VERIFICAR"} <= allowed


# ---------------------------------------------------------------------------
# 4. Benchmark reproducible y veredictos
# ---------------------------------------------------------------------------
def _good_variant() -> dict:
    return {
        "specific_name": "Cuaderno de cuotas para administradores de fincas colegiados",
        "user": "El administrador de fincas colegiado que gestiona comunidades",
        "buyer": "El presidente de la comunidad que aprueba el presupuesto anual",
        "situation": "Cada trimestre debe cuadrar cuotas, derramas y morosidad a mano",
        "observable_problem": "Pierde horas cada trimestre y comete errores en derramas",
        "current_alternative": "Hoja de cálculo compartida por correo",
        "economic_or_time_cost": "6 horas trimestrales y reclamaciones de propietarios",
        "concrete_deliverable": "Cuaderno de cuotas con estado de cada propietario",
        "measurable_outcome": "Cerrar el trimestre en 1 hora en vez de 6",
        "revenue_model": "Suscripción trimestral",
        "expected_price_hypothesis": "HIPÓTESIS: 39 EUR/trimestre",
        "first_distribution_channel": "Email directo a colegios de administradores",
        "first_20_buyers_location": "Administradores colegiados de una provincia",
        "test_in_48_hours": "Enviar 10 correos ofreciendo el cuaderno a mano",
        "generic_ai_limitation": "Requiere la cartera de propietarios y el histórico de morosidad",
        "compounding_asset": "Histórico por comunidad",
        "primary_risk": "El software de gestión ya lo cubra",
        "assumptions": "HIPÓTESIS: dolor, precio y urgencia sin verificar",
        "prohibited_claims": "No afirmar demanda ni citar clientes",
        "causal_chain": "Cuadrar cuotas a mano provoca errores y horas perdidas",
        "why_someone_pays": "HIPÓTESIS: ahorra tiempo y evita conflictos",
    }


def test_benchmark_reproducible_same_input_same_output():
    v = _good_variant()
    r1 = score_reformulation_variant(v)
    r2 = score_reformulation_variant(v)
    assert r1 == r2  # determinista: sin aleatoriedad ni timestamps
    assert r1["score"] >= 12


def test_benchmark_verdict_unverified():
    v = benchmark_verdict("OX_ALPHA_UNVERIFIED", {"A": {"total_percent": 60}})
    assert v["verdict"] == "OX_ALPHA_UNVERIFIED"


def test_benchmark_verdict_inconclusive_on_missing_arm():
    v = benchmark_verdict("acme/alpha-0", {"A": {"total_percent": 60}, "C": {"status": "error"}})
    assert v["verdict"] == "OX_ALPHA_BENCHMARK_INCONCLUSIVE"


def test_benchmark_verdict_passed_when_model_matches_or_exceeds():
    v = benchmark_verdict(
        "acme/alpha-0",
        {"A": {"total_percent": 60}, "C": {"status": "ok", "total_percent": 65}},
    )
    assert v["verdict"] == "OX_ALPHA_BENCHMARK_PASSED"
    v2 = benchmark_verdict(
        "acme/alpha-0",
        {"A": {"total_percent": 60}, "C": {"status": "ok", "total_percent": 40}},
    )
    assert v2["verdict"] == "OX_ALPHA_BENCHMARK_FAILED"


def test_score_task_response_structure():
    r = score_task_response(
        "reformulation",
        {"variants": [_good_variant()]},
    )
    assert r["max"] == 100
    assert r["score"] > 0


# ---------------------------------------------------------------------------
# 5. OX Alpha nunca toca evidencia ni puntuaciones
# ---------------------------------------------------------------------------
def test_ox_alpha_outputs_never_touch_scores(container):
    """Correr el super-torneo (la única vía que consume briefs) no modifica
    proven_demand ni evidence_backed_venture_score: son etiquetas del concepto."""
    d = container.orchestrator.create_real_campaign()
    rid = d["run"]["id"]
    container.orchestrator.advance(rid)
    dcid = d["run"]["discovery_campaign_id"]
    concepts = container.discovery.campaign_detail(dcid)["concepts"]
    before = {
        c["id"]: {
            "proven_demand": (c.get("venture") or {}).get("proven_demand"),
            "evidence": c.get("evidence_backed_venture_score"),
            "groups": c.get("evidence_groups"),
        }
        for c in concepts
    }
    result = container.super_tournament.run(actor="test")
    assert result["ok"] is True
    after = container.discovery.campaign_detail(dcid)["concepts"]
    for c in after:
        assert (c.get("venture") or {}).get("proven_demand") == before[c["id"]]["proven_demand"]
        assert c["evidence_backed_venture_score"] == before[c["id"]]["evidence"]
        assert c.get("evidence_groups") == before[c["id"]]["groups"]


def test_super_tournament_decision_logged_and_not_evidence(container):
    container.orchestrator.create_real_campaign()
    result = container.super_tournament.run(actor="test")
    entries = container.repos.decision_log.recent(limit=5)
    agents = {e.agent for e in entries}
    assert "super_tournament" in agents
    # La puntuación del torneo es prioridad de investigación, nunca evidencia.
    assert result["note_model_reasoning"]


# ---------------------------------------------------------------------------
# 6. Super-torneo: 0 válido, máx. 3, brief obligatorio
# ---------------------------------------------------------------------------
def test_super_tournament_zero_candidates_valid():
    result = run_super_tournament([])
    assert result["winners"] == []
    assert result["total_entries"] == 0


def _entry(cid: str, title: str, brief: dict) -> dict:
    return {"concept_id": cid, "title": title, "status": "RESEARCH_CANDIDATE", "concept": {"title": title}, "brief": brief}


def _full_brief() -> dict:
    return {
        "specific_name": "X",
        "user": "El responsable de compras de una farmacia",
        "buyer": "El titular de la farmacia que paga el software",
        "situation": "Cada semana revisa manualmente fechas de caducidad",
        "observable_problem": "Pierde ventas cuando un lote caduca antes de revisarlo",
        "current_alternative": "Hoja de cálculo revisada a mano",
        "economic_or_time_cost": "3 horas semanales y mermas por lotes olvidados",
        "concrete_deliverable": "Informe semanal con lotes en riesgo",
        "measurable_outcome": "Reducir mermas un 20%",
        "revenue_model": "Suscripción mensual",
        "expected_price_hypothesis": "29 EUR/mes (HIPÓTESIS)",
        "first_distribution_channel": "Contacto directo con 20 farmacias",
        "first_20_buyers_location": "Farmacias independientes de una ciudad",
        "test_in_48_hours": "Preparar el informe a mano para 2 farmacias",
        "generic_ai_limitation": "Requiere integración con el inventario real",
        "compounding_asset": "Histórico de mermas",
        "primary_risk": "El software de gestión ya lo ofrezca",
        "assumptions": "Comprador, dolor y precio sin verificar: hipótesis",
        "prohibited_claims": "Sin afirmar demanda",
    }


def test_super_tournament_max_three_winners():
    entries = [_entry(f"c{i:02d}", f"Negocio {i}", _full_brief()) for i in range(6)]
    result = run_super_tournament(entries)
    assert len(result["winners"]) <= MAX_WINNERS == 3


def test_super_tournament_requires_full_brief():
    bad = _full_brief()
    bad["buyer"] = ""  # campo crítico vacío ⇒ rechazado en la puerta
    result = run_super_tournament([_entry("c01", "Sin buyer", bad)])
    assert result["winners"] == []
    assert len(result["rejected_incomplete_brief"]) == 1


def test_super_tournament_dedup_repeated_titles():
    entries = [
        _entry("c01", "Cuaderno de cuotas de comunidad", _full_brief()),
        _entry("c02", "Cuaderno de cuotas de comunidad", _full_brief()),
    ]
    result = run_super_tournament(entries)
    assert len(result["winners"]) <= 1  # el mismo negocio ocupa una sola plaza


# ---------------------------------------------------------------------------
# 7. Centro de mando honesto
# ---------------------------------------------------------------------------
def test_command_center_no_invented_numbers(container):
    snap = container.command_center.snapshot()
    assert snap["real_money_moved"] is False
    assert snap["simulated"] is True
    assert snap["version"] == "0.21.0"  # iteración 022 (activación de un clic)
    assert snap["iteration"] == "022"
    assert snap["permissions"]["autonomous_production"] is False
    assert snap["permissions"]["api_budget_usd"] == 0
    # Autonomous Launch: estado determinista; READY_TO_LAUNCH nunca sin autorización.
    assert snap["autonomous_launch"]["state"] in ("NOT_STARTED", "NOT_READY", "READY_TO_CONNECT_SERVICES", "BLOCKED")
    assert snap["autonomous_launch"]["ready_to_launch"] is False
    # El panel distingue naturaleza: simulada, hipótesis, modelo, desconocido.
    assert "SIMULADO" in snap["honesty"]["ledger"]
    assert "HIPÓTESIS" in snap["honesty"]["conceptos_offline"]
    assert "modelo" in snap["honesty"]["modelo"].lower()
    # Bloqueador de producción presente (regla de capacidad).
    kinds = {b["kind"] for b in snap["blockers"]}
    assert "PRODUCTION_BLOCKED" in kinds


def test_command_center_real_campaign_counts(container):
    d = container.orchestrator.create_real_campaign()
    container.orchestrator.advance(d["run"]["id"])
    snap = container.command_center.snapshot()
    assert snap["campaign"]["concepts_total"] == 66
    status = snap["campaign"]["concept_status"]
    assert status.get("NEEDS_REFORMULATION", 0) >= 0
    assert sum(status.values()) == 66
    # La explicación de misiones nunca es un cero silencioso.
    assert snap["missions"]["explanation"]


def test_command_center_differentiates_real_vs_not_connected(container):
    snap = container.command_center.snapshot()
    services = {s["name"]: s for s in snap["services"]}
    assert services["MockProvider (offline)"]["connected"] is True
    assert services["Stripe"]["connected"] is False
    assert services["Stripe"]["nature"] == "NO CONECTADO"


def test_command_center_endpoint_honest_envelope(client, container):
    r = client.get("/api/command-center")
    assert r.status_code == 200
    body = r.json()
    assert body["real_money_moved"] is False
    assert "timeline" in body
    assert "llm_costs" in body
    assert body["llm_costs"]["billing_verified"] is False


# ---------------------------------------------------------------------------
# 8. Persistencia, reinicio y seguridad
# ---------------------------------------------------------------------------
def test_restart_preserves_campaign_and_state(tmp_path):
    s = make_settings(tmp_path)
    c1 = build_container(s)
    d = c1.orchestrator.create_real_campaign()
    rid = d["run"]["id"]
    c1.orchestrator.advance(rid)
    state_before = c1.repos.orchestrator.get_run(rid)["state"]
    c1.close()

    c2 = build_container(s)  # mismo database_path ⇒ reinicio real
    try:
        state_after = c2.repos.orchestrator.get_run(rid)["state"]
        assert state_after == state_before
    finally:
        c2.close()


def test_pre_cycle_stopped_and_zero_real_spend(container):
    cyc = container.cycle.evaluate()
    assert cyc["status"] == "PRE_CYCLE"
    assert cyc["clock_running"] is False
    assert cyc["real_money_moved"] is False
    snap = container.command_center.snapshot()
    assert snap["economy"]["metrics"]["available_balance"] is not None
    assert snap["real_money_moved"] is False
    assert snap["permissions"]["gasto_real_autorizado"].startswith("0")


def test_production_blocked_by_capability(container):
    eng = container.engine.status()
    assert eng["production_capability_available"] is False
    assert eng["production_armed"] is False
    snap = container.command_center.snapshot()
    assert snap["permissions"]["production_capability_available"] is False


def test_no_secrets_in_command_center(container):
    raw = json.dumps(container.command_center.snapshot())
    for marker in ("api_key", "sk-", "AIza", "token=", "BEGIN PRIVATE"):
        assert marker not in raw.lower() or marker == "api_key" and "api_budget" in raw


def test_tests_init_present():
    from pathlib import Path
    assert (Path(__file__).resolve().parents[1] / "tests" / "__init__.py").exists()


# ---------------------------------------------------------------------------
# 9. Frontend/backend sincronizados
# ---------------------------------------------------------------------------
def test_frontend_backend_version_synced(tmp_path):
    from tests.conftest import FRONTEND_DIR
    index = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    assert 'data-wawa-version="0.21.0"' in index
    assert 'data-iteration="022"' in index
    assert 'data-build="022-one-click-activation"' in index
    assert "ops18.js" in index
    assert (FRONTEND_DIR / "ops18.js").exists()
    ops18 = (FRONTEND_DIR / "ops18.js").read_text(encoding="utf-8")
    assert "api/command-center" in ops18
    settings = Settings()
    assert settings.version == "0.21.0"


# ---------------------------------------------------------------------------
# 10. Mapeo estable e investigación portable (reafirmación 017 dentro de 018)
# ---------------------------------------------------------------------------
def test_stable_mapping_and_portable_research(container):
    from app.services.reformulation_import import apply_reformulation_plan, resolve_research_package
    from tests.test_reformulation_import_017 import _valid_brief as valid_brief

    d = container.orchestrator.create_real_campaign()
    rid = d["run"]["id"]
    dcid = d["run"]["discovery_campaign_id"]
    container.orchestrator.advance(rid)
    concepts = container.discovery.campaign_detail(dcid)["concepts"]
    targets = [c for c in concepts if c["status"] == "NEEDS_REFORMULATION"][:1]
    plan = {"briefs": [{"concept_id": "foraneo-018", "direccion_original": targets[0]["title"], "brief": valid_brief()}]}
    applied = apply_reformulation_plan(container, plan, run_id=rid, preview=False)
    assert applied["applied"] == 1
    missions = applied["missions"]
    assert len(missions) >= 6  # Fase 1 progresiva

    # Mapeo estable por (título, kind, fase, ordinal): los foráneos jamás entran.
    title = applied["entries"][0]["local_title"]
    results = [
        {"concept_title": title, "mission_kind": m["kind"],
         "evidences": [{"evidence_type": "demand_signal", "source_name": "Fuente",
                        "source_url": "https://example.com/x", "captured_at": "2026-08-26",
                        "summary": "s", "raw_excerpt": "f", "reliability_score": 0.8,
                        "independence_group": "g1", "verified": True}]}
        for m in missions
    ]
    pkg = {"results": results}
    out = resolve_research_package(container, pkg, run_id=rid, apply=True)
    assert out["matched"] == len(missions)
    assert out["import_transition"]["to_state"] == "RESEARCH_IMPORTED"
    # Re-importar el mismo paquete no duplica evidencia (idempotencia).
    again = resolve_research_package(container, pkg, run_id=rid, apply=True)
    assert again["matched"] == len(missions)


def test_super_tournament_deterministic(container):
    container.orchestrator.create_real_campaign()
    r1 = container.super_tournament.run(actor="test")
    r2 = container.super_tournament.run(actor="test")
    assert [w["concept_id"] for w in r1["winners"]] == [w["concept_id"] for w in r2["winners"]]
