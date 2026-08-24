"""Cierre end-to-end, PRE_CYCLE y primera campaña real (iteración 010).

Cubre: orquestador (crear campaña real, avanzar hasta RESEARCH_PENDING sin
repetir fases, transiciones auditadas), corrección crítica PRE_CYCLE
(leer/abrir web/campaña no arranca el reloj; POST /cycle/start explícito con
12 precondiciones), fuente única de 30 días (initial_cycle_days deprecado),
exportaciones CSV/JSON/MD/finalists, CORS local restrictivo, escape XSS de
contenido importado, y reanudación sin duplicar fases.
"""
from __future__ import annotations

import csv
import io
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from app.models.evaluation import Decision, Evaluation
from app.models.opportunity import OpportunityCreate

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROBLEM = "Problema sintético para el orquestador (iteración 010)."
SCORE80 = {
    "pain_score": 80.0, "demand_score": 80.0, "customer_reach_score": 80.0,
    "automation_score": 80.0, "margin_score": 80.0, "build_speed_score": 80.0,
    "differentiation_score": 80.0, "safety_score": 80.0, "evidence_quality_score": 80.0,
    "confidence_score": 80.0, "final_score": 80.0, "decision": Decision.approved,
    "independent_evidence_count": 4,
}


# ------------------------------------------------------------------ orchestrator
def test_create_real_campaign_advances_to_research_pending(container):
    run = container.orchestrator.create_real_campaign()
    rid = run["run"]["id"]
    assert run["run"]["title"] == "PRIMERA CAMPAÑA REAL 001"
    detail = container.orchestrator.advance(rid)
    assert detail["run"]["state"] == "RESEARCH_PENDING"
    assert detail["research_pending"] is True
    assert detail["owner_action_required"] is True
    # Iteración 016: con cero candidatas concretas (flujo por defecto), la parada
    # explica honestamente que NO hay misión que copiar y pide REFORMULAR.
    assert "REFORMULAR" in (detail["next_action"] or "")
    assert "COPIAR MISIÓN" not in (detail["next_action"] or "")


def test_orchestrator_does_not_repeat_phases(container):
    run = container.orchestrator.create_real_campaign()
    rid = run["run"]["id"]
    container.orchestrator.advance(rid)
    n1 = len(container.repos.orchestrator.transitions_for(rid))
    # Re-advance: ya en RESEARCH_PENDING, no ejecuta nada nuevo.
    container.orchestrator.advance(rid)
    n2 = len(container.repos.orchestrator.transitions_for(rid))
    assert n2 == n1


def test_orchestrator_idempotent_create(container):
    run = container.orchestrator.create_real_campaign()
    rid1 = run["run"]["id"]
    run2 = container.orchestrator.create_real_campaign()
    assert run2["run"]["id"] == rid1  # no duplica ejecución activa


def test_orchestrator_transitions_audited(container):
    run = container.orchestrator.create_real_campaign()
    rid = run["run"]["id"]
    container.orchestrator.advance(rid)
    transitions = container.repos.orchestrator.transitions_for(rid)
    states = [t["to_state"] for t in transitions]
    assert "DISCOVERING" in states
    assert "TOURNAMENT" in states
    assert "RESEARCH_PLANNED" in states
    # La fase 1 produjo 60 conceptos (config de la primera campaña real).
    t1 = next(t for t in transitions if t["to_state"] == "DISCOVERING")
    assert t1["concepts_considered"] == 60
    # Sin llama LLM: el costo registrado es estimación local.
    assert all(t.get("cost_source") == "LOCAL_ESTIMATE" for t in transitions)


def test_orchestrator_pause_resume_cancel(container):
    run = container.orchestrator.create_real_campaign()
    rid = run["run"]["id"]
    paused = container.orchestrator.pause(rid)
    assert paused["run"]["status"] == "paused"
    resumed = container.orchestrator.resume(rid)
    assert resumed["run"]["status"] == "active"
    assert resumed["run"]["state"] == "RESEARCH_PENDING"
    cancelled = container.orchestrator.cancel(rid)
    assert cancelled["run"]["status"] == "cancelled"


def test_orchestrator_export_files(container):
    run = container.orchestrator.create_real_campaign()
    rid = run["run"]["id"]
    container.orchestrator.advance(rid)
    detail = container.discovery.campaign_detail(run["run"]["discovery_campaign_id"])
    from app.services import campaign_exports as exp

    csv_text = exp.build_csv(detail, synthetic=True)
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) >= 60
    row = rows[0]
    for col in ("campaign_id", "concept_id", "title", "ai_substitution_class", "synthetic_or_real"):
        assert col in row, col

    j = json.loads(exp.build_json(detail, synthetic=True, run=run["run"]))
    assert j["summary"]["total"] >= 60
    assert "concepts" in j and "comparisons" in j

    md = exp.build_markdown(detail, synthetic=True)
    assert "## 3. Todas las ideas" in md and "## 4. Ideas descartadas y motivo" in md
    assert "SINTÉTICO" in md

    finals = exp.build_finalists_markdown(detail, synthetic=True)
    assert "# Finalistas" in finals


def test_orchestrator_research_import_requires_mission(container):
    run = container.orchestrator.create_real_campaign()
    rid = run["run"]["id"]
    container.orchestrator.advance(rid)
    # Importar sin mission_id: error claro, sin inventar nada.
    with pytest.raises(Exception):
        container.orchestrator.import_research(rid, [{"evidences": []}])


# ------------------------------------------------------------------ PRE_CYCLE
def test_cycle_reading_never_starts(container):
    st = container.cycle.evaluate()
    assert st["status"] == "PRE_CYCLE" and st["clock_running"] is False
    assert container.cycle._row() is None
    # Abrir la web, crear campaña o generar ideas tampoco arranca el reloj.
    container.orchestrator.create_real_campaign()
    st2 = container.cycle.evaluate()
    assert st2["status"] == "PRE_CYCLE" and st2["started_at"] is None


def test_cycle_start_idempotent_and_auditable(container):
    # Sin precondiciones: bloqueado (honesto). El reintento no cambia nada.
    a = container.cycle.start()
    b = container.cycle.start()
    assert a["started"] is False and b["started"] is False
    assert a["missing_conditions"] == b["missing_conditions"]
    assert "metodo_pago_real_permitido" in a["missing_conditions"]


def test_initial_cycle_days_single_source(container):
    # Única fuente de verdad: 30 días. initial_cycle_days queda fijado a 30.
    assert container.settings.cycle_length_days == 30
    assert container.settings.initial_cycle_days == 30
    assert container.settings.initial_cycle_days == container.settings.cycle_length_days


# ------------------------------------------------------------------ CORS
def test_cors_default_local_restrictive(container, client):
    assert "*" not in container.settings.cors_origins
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "access-control-allow-origin" not in r.headers or "*" not in r.headers.get("access-control-allow-origin", "")


# ------------------------------------------------------------------ XSS escape
def test_imported_response_escaped_before_innerhtml():
    """El contenido importado (dato no confiable) se escapa antes de entrar en
    innerHTML: se ejecuta la función esc() real de app.js con contenido hostil."""
    js = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    m = re.search(r"function esc\(value\) \{(.*?)\n\}", js, re.DOTALL)
    assert m, "esc() no encontrada en app.js"
    fn_body = m.group(1)
    evil = '<img src=x onerror=alert(1)><script>alert(2)</script>"&\'x'
    chars = ["<", ">", '"', "'"]
    script = (
        "function esc(value) {" + fn_body + "\n}\n"
        "const evil = " + json.dumps(evil) + ";\n"
        "const out = esc(evil);\n"
        "const chars = " + json.dumps(chars) + ";\n"
        "for (const ch of chars) { if (out.includes(ch)) { console.error('NOT ESCAPED: ' + ch); process.exit(1); } }\n"
        "if (!out.includes('&lt;') || !out.includes('&amp;')) { console.error('NO ENTITY'); process.exit(2); }\n"
        "console.log('escaped-ok');\n"
    )
    res = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    # Si node no está disponible, se omite el chequeo (no fallar la suite).
    if res.returncode != 0 and "not found" in res.stderr.lower():
        pytest.skip("node no disponible")
    assert res.returncode == 0, res.stderr
    assert "escaped-ok" in res.stdout
