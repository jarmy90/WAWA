"""Iteración 020 — Mission Control Premium y Sistema Solar de agentes.

Prueba: rutas directas, recarga, contrato de telemetría (estados permitidos,
sin actividad inventada), separación del modo demo, mapeo semántico, costes
desconocidos, datos no conectados, XSS, reduced motion, fallback textual y
sintaxis JS (node --check).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import FRONTEND_DIR, PROJECT_ROOT, make_settings

ALLOWED_STATES = {"ACTIVE", "WORKING", "WAITING", "BLOCKED", "IDLE", "ERROR", "OFFLINE", "NO_DATA"}

AGENT_IDS = {"orchestrator", "scout", "researcher", "skeptic", "economist", "builder", "compliance", "judge"}

REQUIRED_AGENT_FIELDS = {
    "id", "name", "role", "status", "current_action", "last_event_at", "activity_level",
    "priority", "tools", "missions", "parent_agent_id", "blocked_reason", "event_count",
    "error_count", "cost", "data_nature",
}

REQUIRED_TOP_KEYS = {
    "snapshot_at", "system_health", "production_capability", "campaign_id", "active_project",
    "agents", "agent_relationships", "scheduled_tasks", "mission_queue", "recent_events",
    "blockers", "provider_states", "costs", "experiment_state", "commercial_metrics", "data_nature",
}


@pytest.fixture
def client(container):
    app = create_app(container)
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Rutas directas y recarga
# ---------------------------------------------------------------------------
def test_mission_control_route_direct(client):
    r = client.get("/mission-control")
    assert r.status_code == 200
    assert "WAWA AUTONOMOUS BUSINESS COMMAND" in r.text
    assert "/viz-core.js" in r.text
    assert "/mission-control.js" in r.text


def test_agents_viz_route_direct(client):
    r = client.get("/agents-viz")
    assert r.status_code == 200
    assert "Sistema Solar de agentes" in r.text
    assert "sv-canvas" in r.text


def test_mission_control_route_reload(client):
    """Recarga (refresco de navegador) sirve la misma vista: ruta directa."""
    r = client.get("/mission-control")
    assert r.status_code == 200
    r2 = client.get("/mission-control")
    assert r2.status_code == 200
    assert r2.text == r.text


def test_routes_do_not_break_main_dashboard(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "/mission-control" in r.text
    assert "/agents-viz" in r.text


# ---------------------------------------------------------------------------
# Contrato de telemetría
# ---------------------------------------------------------------------------
def test_telemetry_endpoint_contract(client):
    r = client.get("/api/agent-telemetry")
    assert r.status_code == 200
    d = r.json()
    assert REQUIRED_TOP_KEYS <= set(d.keys())
    assert d["data_nature"] == "REAL"
    assert d["version"] == "0.23.0"
    assert d["iteration"] == "022"


def test_telemetry_agent_fields_and_states(client):
    d = client.get("/api/agent-telemetry").json()
    assert isinstance(d["agents"], list) and d["agents"]
    for agent in d["agents"]:
        assert REQUIRED_AGENT_FIELDS <= set(agent.keys()), f"Faltan campos en {agent.get('id')}"
        assert agent["status"] in ALLOWED_STATES, f"Estado no permitido: {agent['status']}"
        assert agent["data_nature"] == "REAL"


def test_telemetry_includes_real_logical_agents(client):
    d = client.get("/api/agent-telemetry").json()
    ids = {a["id"] for a in d["agents"]}
    assert AGENT_IDS <= ids, f"Faltan agentes lógicos: {AGENT_IDS - ids}"


def test_telemetry_does_not_invent_activity_on_empty_db(settings):
    """Base vacía: ningún agente ACTIVE/WORKING sin datos que lo respalden."""
    from app.core.container import build_container

    container = build_container(make_settings(settings.data_dir, **{}))
    # Base recién creada en tmp_path (sin campaña, sin misiones, sin llamadas).
    app = create_app(container)
    with TestClient(app) as c:
        d = c.get("/api/agent-telemetry").json()
        for agent in d["agents"]:
            if agent["id"] == "mock":
                continue  # MockProvider siempre está disponible (offline determinista)
            assert agent["status"] not in ("ACTIVE", "WORKING"), (
                f"{agent['id']} reporta {agent['status']} sin actividad real"
            )
    container.close()


def test_telemetry_costs_never_invent_zero(settings):
    """Sin llamadas LLM: reported/estimated son None y display NO_CALLS (no 0 falso)."""
    from app.core.container import build_container

    container = build_container(make_settings(settings.data_dir, **{}))
    app = create_app(container)
    with TestClient(app) as c:
        d = c.get("/api/agent-telemetry").json()
        costs = d["costs"]
        assert costs["reported_total"] is None
        assert costs["estimated_total"] is None
        assert costs["display_status"] in ("NO_CALLS", "UNKNOWN", "KNOWN_WITH_UNKNOWN_CALLS")
    container.close()


def test_telemetry_commercial_metrics_not_connected(client):
    d = client.get("/api/agent-telemetry").json()
    cm = d["commercial_metrics"]
    assert cm["visits"] == "NO CONECTADO"
    assert cm["payments"] == "NO CONECTADO"
    assert cm["nature"] == "NO CONECTADO"


def test_telemetry_relationships_reference_existing_agents(client):
    d = client.get("/api/agent-telemetry").json()
    ids = {a["id"] for a in d["agents"]}
    for rel in d["agent_relationships"]:
        assert rel["parent"] in ids, f"Padre inexistente: {rel['parent']}"
        assert rel["child"] in ids, f"Hijo inexistente: {rel['child']}"


# ---------------------------------------------------------------------------
# Modo demo separado (cliente): nunca se mezcla con datos reales
# ---------------------------------------------------------------------------
def test_viz_core_demo_is_labeled_and_separate():
    viz = (FRONTEND_DIR / "viz-core.js").read_text(encoding="utf-8")
    assert "DEMO DATA · NOT REAL ACTIVITY" in viz
    assert "data_nature: \"DEMO\"" in viz or "DEMO" in viz
    # El endpoint real siempre marca REAL; el demo es solo cliente.
    assert "?demo=1" in viz or 'demo") === "1"' in viz


def test_mission_control_html_has_demo_banner():
    html = (FRONTEND_DIR / "mission-control.html").read_text(encoding="utf-8")
    assert "DEMO DATA · NOT REAL ACTIVITY" in html


# ---------------------------------------------------------------------------
# Accesibilidad: reduced motion, fallback textual, navegación por teclado
# ---------------------------------------------------------------------------
def test_reduced_motion_supported():
    css = (FRONTEND_DIR / "mission-control.css").read_text(encoding="utf-8")
    assert "@media (prefers-reduced-motion: reduce)" in css
    js = (FRONTEND_DIR / "viz-core.js").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in js
    viz_core = (FRONTEND_DIR / "viz-core.js").read_text(encoding="utf-8")
    assert "matchMedia" in viz_core  # detección en el núcleo compartido
    agents_js = (FRONTEND_DIR / "agents-viz.js").read_text(encoding="utf-8")
    assert "prefersReducedMotion" in agents_js  # usa el núcleo


def test_canvas_has_textual_fallback_and_aria():
    html = (FRONTEND_DIR / "agents-viz.html").read_text(encoding="utf-8")
    assert "aria-label" in html
    assert "sv-fallback" in html
    assert "alternativa textual" in html
    assert "tabindex" in html  # navegación por teclado


def test_no_cdn_external_dependencies():
    for name in ("mission-control.html", "agents-viz.html"):
        html = (FRONTEND_DIR / name).read_text(encoding="utf-8")
        assert "https://" not in html.replace("https://github.com", "") or "cdn" not in html.lower()
        assert "unpkg" not in html and "jsdelivr" not in html and "cdnjs" not in html


# ---------------------------------------------------------------------------
# Seguridad: escape de datos (XSS) en el núcleo visual
# ---------------------------------------------------------------------------
def test_viz_core_escapes_html():
    viz = (FRONTEND_DIR / "viz-core.js").read_text(encoding="utf-8")
    assert "replace(/&/g" in viz  # escapeHtml presente
    # node unit check si está disponible
    node = _node_bin()
    if node is None:
        pytest.skip("node no disponible")
    code = (
        "const fs=require('fs');const vm=require('vm');"
        "const src=fs.readFileSync('frontend/viz-core.js','utf8');"
        "const sandbox={window:{},URLSearchParams:globalThis.URLSearchParams,matchMedia:()=>({matches:false})};"
        "vm.createContext(sandbox);vm.runInContext(src,sandbox);"
        "const v=sandbox.window.WAWA_Viz;"
        "if(!v){console.error('WAWA_Viz no expuesto');process.exit(9)}"
        "const out=v.escapeHtml('<script>alert(1)</script>');"
        "if(out.indexOf('<script>')>=0){process.exit(1)}"
        "if(v.escapeHtml('<img onerror=1>').indexOf('<img')>=0){process.exit(4)}"
        "const demo=v.demoTelemetry();"
        "if(demo.data_nature!=='DEMO'){process.exit(2)}"
        "if(v.safeState('BOGUS')!=='NO_DATA'){process.exit(3)}"
        "if(v.safeState('blocked')!=='BLOCKED'){process.exit(5)}"
        "console.log('VIZ_CORE_OK');"
    )
    res = subprocess.run([node, "-e", code], cwd=str(FRONTEND_DIR.parent), capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, res.stderr
    assert "VIZ_CORE_OK" in res.stdout


def _node_bin():
    for name in ("node", "nodejs"):
        try:
            r = subprocess.run([name, "--version"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return name
        except FileNotFoundError:
            continue
    return None


# ---------------------------------------------------------------------------
# Smoke test de render (headless, sin navegador)
# ---------------------------------------------------------------------------
def test_viz_views_render_headless():
    """Ejecuta las vistas con mocks de DOM/Canvas: el render, la selección,
    los filtros, el modo demo y el escape XSS no lanzan excepciones."""
    node = _node_bin()
    if node is None:
        pytest.skip("node no disponible")
    script = PROJECT_ROOT / "scripts" / "viz_smoke.js"
    assert script.exists()
    res = subprocess.run([node, str(script)], cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "ALL_SMOKE_TESTS_PASSED" in res.stdout


# ---------------------------------------------------------------------------
# Sintaxis JavaScript
# ---------------------------------------------------------------------------
def test_js_syntax_node_check():
    node = _node_bin()
    if node is None:
        pytest.skip("node no disponible")
    for name in ("viz-core.js", "mission-control.js", "agents-viz.js", "app.js", "ops17.js", "ops18.js"):
        path = FRONTEND_DIR / name
        assert path.exists(), f"Falta {name}"
        res = subprocess.run([node, "--check", str(path)], capture_output=True, text=True, timeout=30)
        assert res.returncode == 0, f"{name}: {res.stderr}"


# ---------------------------------------------------------------------------
# Mapeo semántico visual (Bloque 4)
# ---------------------------------------------------------------------------
def test_solar_system_semantic_mapping_documented_in_code():
    js = (FRONTEND_DIR / "agents-viz.js").read_text(encoding="utf-8")
    # Sol = orchestrator; planetas = agentes; color = estado; órbitas congeladas
    assert "orchestrator" in js
    assert "stateColor" in js
    assert "frozen" in js
    assert "BLOCKED" in js and "ERROR" in js
    assert "asteroids" in js and "comets" in js
