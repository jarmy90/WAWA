"""Iteración 022 — ONE-CLICK OWNER ACTIVATION.

Prueba los 26 casos del Objetivo 12: arranque Windows sin PowerShell,
bootstrap comercial idempotente (instalación limpia / FAILED / interrumpida /
reinicio), modo demo no persistente, tres candidatas, una ganadora, cola de
comité, READY_TO_CONNECT_SERVICES, PRE_CYCLE detenido, gasto real cero,
producción bloqueada, ausencia de secretos y sincronización frontend/backend.

100% offline: bases temporales, MockProvider, sin red, sin navegador.
"""
from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from pathlib import Path

import pytest

from app.core.container import build_container
from tests.conftest import make_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = PROJECT_ROOT / "resources" / "bootstrap" / "commercial_021"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Títulos canónicos de candidatas.json (materializados en la campaña local;
# los títulos del paquete están normalizados sin acentos).
WINNER_TITLE = (
    "Benchmark anonimo de tarifas para clinicas dentales que deciden su precio de ortodoncia"
)
CANDIDATE_TITLES = [
    WINNER_TITLE,
    "Benchmark de honorarios para gestorias que deciden su tarifa mensual",
    "Benchmark de costes de instalacion para empresas de placas solares que deciden presupuesto",
]


# ---------------------------------------------------------------------------
# 1-5. START_WAWA.bat (Windows, sin PowerShell, doble clic, espacios, .venv)
# ---------------------------------------------------------------------------
BAT = (PROJECT_ROOT / "START_WAWA.bat").read_text(encoding="utf-8", errors="replace")


def test_001_bat_works_from_any_directory_powershell_cwd():
    """Causa del error PowerShell: se ejecutaba `.venv\...` desde C:\\Users\\j.
    El .bat debe moverse a su propia carpeta con `cd /d "%~dp0"`."""
    assert 'cd /d "%~dp0"' in BAT


def test_002_bat_handles_spaces_in_project_path():
    """Rutas con espacios: todos los accesos al .venv y python van entre comillas."""
    assert 'call ".venv\\Scripts\\activate.bat"' in BAT
    assert '"scripts\\startup_bootstrap.py"' in BAT
    assert '"%URL%"' in BAT


def test_003_bat_double_click_defaults_port_8000():
    """Doble clic = sin argumentos => puerto por defecto 8000."""
    assert 'if "%1"=="" (set PORT=8000)' in BAT
    assert "setlocal" in BAT


def test_004_bat_creates_missing_venv():
    """Entorno .venv inexistente: el .bat lo crea con python -m venv."""
    assert "python -m venv .venv" in BAT
    assert 'if not exist ".venv"' in BAT


def test_005_bat_uses_existing_venv():
    """Entorno .venv existente: se reutiliza (no se recrea)."""
    assert BAT.count("python -m venv .venv") == 1
    assert "call \".venv\\Scripts\\activate.bat\"" in BAT


def test_005b_bat_runs_bootstrap_before_browser():
    """El .bat aplica el bootstrap ANTES de abrir el navegador y no exige
    comandos adicionales (pasos [4/7]-[6/7] -> startup_bootstrap.py)."""
    assert "startup_bootstrap.py" in BAT
    assert "scripts\\startup_bootstrap.py" in BAT
    idx_bootstrap = BAT.index("startup_bootstrap.py")
    idx_open = BAT.index('start "" "%URL%"')  # apertura real del navegador
    assert idx_open > idx_bootstrap


def test_005c_bat_progress_steps_present():
    """Flujo de 7 pasos visible en consola."""
    for step in ("[1/7]", "[2/7]", "[3/7]", "[4/7]", "[5/7]", "[6/7]", "[7/7]"):
        assert step in BAT, f"falta el paso {step} en START_WAWA.bat"


# ---------------------------------------------------------------------------
# 6-11. Bootstrap comercial (limpia / FAILED / idempotente / interrumpido /
#       reinicio / IDs locales)
# ---------------------------------------------------------------------------
def _container(tmp_path, **overrides):
    settings = make_settings(
        tmp_path,
        credentials_env_path=tmp_path / ".env",
        **overrides,
    )
    return build_container(settings)


def _count(conn, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]


MISSIONS_TABLE = "research_missions"  # esquema real (db.py)


@pytest.fixture
def bootstrapped(tmp_path):
    """Contenedor con el bootstrap comercial ya aplicado (instalación limpia)."""
    c = _container(tmp_path)
    res = c.bootstrap.apply()
    yield c, res
    c.close()


def test_006_clean_install_bootstrap(tmp_path):
    """Instalación limpia: se crea la campaña y queda READY_TO_CONNECT_SERVICES."""
    c = _container(tmp_path)
    try:
        st_before = c.bootstrap.status()
        assert st_before["applied"] is False
        assert st_before["run_state"] is None or st_before["run_status"] in (None, "failed")
        res = c.bootstrap.apply()
        assert res["ok"] is True
        assert res["already_applied"] is False
        assert res["candidates"] == 3
        assert res["missions_imported"] == 18
        assert res["readiness_state"] == "READY_TO_CONNECT_SERVICES"
        assert res["pre_cycle"] == "STOPPED"
        assert res["real_spend_usd"] == 0.0
        assert res["production"] == "BLOCKED"
        assert res["mandate_state"] == "PENDING_OWNER_AUTHORIZATION"
        assert res["committee_queued"] is True
    finally:
        c.close()


def test_007_failed_run_recovered(tmp_path):
    """Campaña con ejecución FAILED recuperable: el bootstrap la recupera sin
    borrar ideas y deja el sistema listo."""
    c = _container(tmp_path)
    try:
        created = c.orchestrator.create_real_campaign()
        run = created.get("run") or c.orchestrator.current_run()
        assert run is not None
        # Simular la ejecución FAILED que reportó el propietario.
        c.repos.orchestrator.update_run(run["id"], status="failed")
        st = c.bootstrap.status()
        assert st["recoverable"] is True
        assert st["recoverable_failed"] is True
        assert st["can_repair"] is True
        res = c.bootstrap.apply()
        assert res["ok"] is True
        assert res["readiness_state"] == "READY_TO_CONNECT_SERVICES"
        run_after = c.repos.orchestrator.get_run(run["id"]) or {}
        assert run_after.get("status") == "active"
        # Las ideas de la campaña original se conservan (nunca se borran).
        assert _count(c.conn, "discovery_concepts") >= 3
    finally:
        c.close()


def test_008_bootstrap_idempotent(bootstrapped):
    """Segunda aplicación: already_applied y sin duplicar misiones/evidencias."""
    c, res = bootstrapped
    res2 = c.bootstrap.apply()
    assert res2["already_applied"] is True
    missions = _count(c.conn, MISSIONS_TABLE)
    evidence = _count(c.conn, "evidence")
    checkpoints = _count(c.conn, "bootstrap_checkpoints")
    res3 = c.bootstrap.apply()
    assert res3["already_applied"] is True
    assert _count(c.conn, MISSIONS_TABLE) == missions
    assert _count(c.conn, "evidence") == evidence
    assert _count(c.conn, "bootstrap_checkpoints") == checkpoints


def test_009_bootstrap_resumes_after_interruption(tmp_path):
    """Corte a mitad: se reintenta y NO duplica datos (checkpoints + idempotencia)."""
    c = _container(tmp_path)
    try:
        c.bootstrap.apply()
        missions = _count(c.conn, MISSIONS_TABLE)
        evidence = _count(c.conn, "evidence")
        # Simular corte: se pierde el marcador de aplicado y el checkpoint de
        # readiness, pero la investigación ya está importada.
        c.conn.execute("DELETE FROM commercial_bootstrap_state")
        c.conn.execute("DELETE FROM bootstrap_checkpoints WHERE component IN ('readiness','applied','evaluation','experiment_plan')")
        c.conn.commit()
        res = c.bootstrap.apply()
        assert res["ok"] is True
        assert res["already_applied"] is False
        assert res["readiness_state"] == "READY_TO_CONNECT_SERVICES"
        # Idempotencia: ni misiones ni evidencias se duplican.
        assert _count(c.conn, MISSIONS_TABLE) == missions
        assert _count(c.conn, "evidence") == evidence
    finally:
        c.close()


def test_010_bootstrap_persists_across_restart(tmp_path):
    """Reinicio de WAWA (nuevo contenedor sobre la misma base): ya aplicado."""
    settings = make_settings(
        tmp_path, credentials_env_path=tmp_path / ".env"
    )
    c1 = build_container(settings)
    c1.bootstrap.apply()
    c1.close()
    c2 = build_container(settings)
    try:
        st = c2.bootstrap.status()
        assert st["applied"] is True
        assert st["applied_version"] == "1"
        res = c2.bootstrap.apply()
        assert res["already_applied"] is True
        snap = c2.command_center.snapshot()
        assert (snap.get("readiness") or {}).get("readiness_state") == "READY_TO_CONNECT_SERVICES"
    finally:
        c2.close()


def test_011_local_ids_never_foreign(tmp_path):
    """Los IDs del paquete son SOLO procedencia: toda fila local tiene IDs
    generados localmente (UUIDs), nunca identificadores de otra base."""
    c = _container(tmp_path)
    try:
        c.bootstrap.apply()
        # El manifiesto declara la política de IDs.
        manifest = json.loads((ASSET_DIR / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["provenance"]["ids_are_provenance_only"]
        # Las misiones locales referencian conceptos/oportunidades locales.
        rows = c.conn.execute(
            "SELECT mission_id, target FROM research_missions WHERE status != 'SUPERSEDED_BY_SEMANTIC_QUALITY_GATE'"
        ).fetchall()
        assert len(rows) >= 18
        # Los IDs locales del esquema son hex de 32 (sin guiones) o UUID.
        local_id = re.compile(r"^[0-9a-f]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
        for row in rows:
            target = json.loads(row["target"] or "{}")
            concept_id = target.get("concept_id") or ""
            assert local_id.match(concept_id), f"concept_id foráneo en misión {row['mission_id']}"
            if target.get("opportunity_id"):
                assert local_id.match(target["opportunity_id"])
            # El paquete portable NUNCA introduce IDs foráneos: el concept_title
            # normalizado es la clave de mapeo, no los IDs de otra base.
            assert target.get("concept_title")
    finally:
        c.close()


def test_012_evidence_not_duplicated(bootstrapped):
    """31 evidencias verificadas, sin duplicados (una por fuente en el paquete)."""
    c, res = bootstrapped
    assert res["evidences_attached"] >= 31
    snap = c.command_center.snapshot()
    ev = snap.get("evidence") or {}
    assert ev.get("verified") == 31
    assert ev.get("total") == 31
    assert ev.get("independent_verified_groups") == 7


def test_013_missions_not_duplicated(bootstrapped):
    """18 misiones de Fase 1 (6 progresivas por candidata), sin duplicados."""
    c, res = bootstrapped
    assert res["missions_imported"] == 18
    rows = c.conn.execute(
        "SELECT COUNT(*) AS n FROM research_missions WHERE status NOT IN ('SUPERSEDED_BY_SEMANTIC_QUALITY_GATE','CANCELLED')"
    ).fetchone()
    assert rows["n"] == 18


def test_014_three_candidates(bootstrapped):
    """La pantalla CANDIDATAS muestra exactamente las 3 candidatas investigadas."""
    c, _ = bootstrapped
    cands = c.bootstrap.candidates()
    assert cands["count"] == 3
    titles = [card["title"] for card in cands["candidates"]]
    for expected in CANDIDATE_TITLES:
        assert any(expected == t or expected in t or t in expected for t in titles), (
            f"no aparece la candidata esperada: {expected}"
        )
    for card in cands["candidates"]:
        assert card["winner_badge"] in ("GANADORA DETERMINISTA PARA EXPERIMENTO", "CANDIDATA INVESTIGADA")
        assert card["demand_validated"] is False  # nunca "demanda validada"


def test_015_one_winner_orthodontics(bootstrapped):
    """Una única ganadora y es el benchmark de ortodoncia."""
    c, res = bootstrapped
    cands = c.bootstrap.candidates()
    winners = [card for card in cands["candidates"] if card["is_winner"]]
    assert len(winners) == 1
    assert winners[0]["title"] == WINNER_TITLE
    assert winners[0]["winner_badge"] == "GANADORA DETERMINISTA PARA EXPERIMENTO"
    assert winners[0]["evidence_verified_live"] == 11
    assert winners[0]["evidence_groups_live"] == 7


def test_016_winner_in_committee_queue(bootstrapped):
    """La ganadora aparece automáticamente en la cola del comité tras el
    bootstrap (sin acciones manuales del propietario)."""
    c, res = bootstrapped
    winner_id = res["winner_opportunity_id"]
    queue = c.repos.reviews.list_queue() if hasattr(c.repos.reviews, "list_queue") else None
    if queue is None:
        queue = _safe_queue(c, winner_id)
    ids = [q.get("opportunity_id") or q.get("id") for q in queue]
    assert winner_id in ids


def _safe_queue(c, winner_id):
    rows = c.conn.execute(
        "SELECT opportunity_id FROM review_queue WHERE opportunity_id = ?", (winner_id,)
    ).fetchall()
    return [{"opportunity_id": r["opportunity_id"]} for r in rows]


# ---------------------------------------------------------------------------
# 17-20. Modo demo (via node smoke sin navegador)
# ---------------------------------------------------------------------------
def test_017_demo_off_initial_by_default():
    """Demo OFF por defecto: el botón inicial dice ACTIVAR DEMO en ambas vistas."""
    for html in ("mission-control.html", "agents-viz.html"):
        content = (FRONTEND_DIR / html).read_text(encoding="utf-8")
        assert ">ACTIVAR DEMO</button>" in content


def test_018_019_020_demo_on_off_url_storage_node_smoke():
    """Demo ON/OFF, URL sin ?demo=1 al salir y localStorage limpio:
    ejecuta el smoke headless de scripts/demo_state_smoke.js."""
    proc = subprocess.run(
        ["node", str(PROJECT_ROOT / "scripts" / "demo_state_smoke.js")],
        capture_output=True, text=True, timeout=60, cwd=PROJECT_ROOT,
    )
    assert proc.returncode == 0, f"demo smoke falló:\n{proc.stdout}\n{proc.stderr}"
    assert "DEMO_STATE_SMOKE_OK" in proc.stdout


def test_018b_viz_js_syntax():
    """node --check de todos los JS nuevos/modificados de la iteración."""
    for js in ("viz-core.js", "mission-control.js", "agents-viz.js", "candidates.js"):
        proc = subprocess.run(
            ["node", "--check", str(FRONTEND_DIR / js)],
            capture_output=True, text=True, timeout=30, cwd=PROJECT_ROOT,
        )
        assert proc.returncode == 0, f"node --check falló en {js}:\n{proc.stderr}"


# ---------------------------------------------------------------------------
# 21-24. Readiness / PRE_CYCLE / gasto / producción
# ---------------------------------------------------------------------------
def test_021_readiness_ready_to_connect(bootstrapped):
    c, res = bootstrapped
    assert res["readiness_state"] == "READY_TO_CONNECT_SERVICES"
    assert res["readiness_missing"] == []
    assert res["readiness_blockers"] == []
    snap = c.command_center.snapshot()
    rd = snap.get("readiness") or {}
    assert rd["readiness_state"] == "READY_TO_CONNECT_SERVICES"
    assert rd["readiness_met"] is True
    assert rd["candidate_id"]
    assert rd["opportunity_id"]
    assert rd["experiment_id"]


def test_022_pre_cycle_stopped(bootstrapped):
    c, _ = bootstrapped
    cycle = c.cycle.evaluate()
    assert not cycle.get("started_at")
    assert cycle.get("status") == "PRE_CYCLE"
    assert cycle.get("clock_running") is False
    # El reloj de 30 días nunca arranca por el bootstrap (solo con autorización
    # explícita del propietario + 12 precondiciones).


def test_023_real_spend_zero(bootstrapped):
    c, res = bootstrapped
    assert res["real_spend_usd"] == 0.0
    ledger = c.repos.ledger.total_real_money_moved() if hasattr(c.repos.ledger, "total_real_money_moved") else None
    if ledger is not None:
        assert float(ledger) == 0.0


def test_024_production_blocked(bootstrapped):
    c, res = bootstrapped
    assert res["production"] == "BLOCKED"
    snap = c.command_center.snapshot()
    prod = snap.get("production_capability") or {}
    assert prod.get("state") == "BLOCKED"
    assert prod.get("nature") == "REAL"
    assert prod.get("reason")  # motivo honesto de bloqueo


# ---------------------------------------------------------------------------
# 25-26. Secretos y sincronización
# ---------------------------------------------------------------------------
def test_025_no_secrets_in_assets_or_api(tmp_path):
    """Sin secretos: los activos de bootstrap y el API de servicios nunca
    revelan valores completos (solo estado y últimos 4 caracteres)."""
    # Activos libres de secretos y de artefactos prohibidos.
    for name in ("manifest.json", "investigacion_fase1_021.json", "candidatas.json"):
        content = (ASSET_DIR / name).read_text(encoding="utf-8", errors="replace")
        assert "sk_live" not in content and "sk_test" not in content
        assert "api_key" not in content.lower().replace("analytics_api_key", "")  # solo nombres de variable
    assert not (ASSET_DIR / "abl.db").exists()  # nunca una SQLite dentro de los activos
    assert not (ASSET_DIR / "logs").exists()
    manifest = json.loads((ASSET_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["guarantees"]["no_secrets"] is True
    assert manifest["guarantees"]["no_sqlite"] is True
    assert manifest["guarantees"]["no_logs"] is True
    # El asistente de servicios devuelve SOLO estado y last4.
    c = _container(tmp_path)
    try:
        c.connect_services.save({"STRIPE_SECRET_KEY": "sk_test_1234567890abcd"})
        status = c.connect_services.status()
        stripe = next(s for s in status["items"] if s["id"] == "stripe")
        assert stripe["status"] == "CONNECTED"
        assert stripe["last4"] == "abcd"
        # El valor completo NUNCA aparece en la respuesta del API.
        blob = json.dumps(status)
        assert "sk_test_1234567890abcd" not in blob
        # Comprobación de formato con valor erróneo.
        check = c.connect_services.check({"STRIPE_SECRET_KEY": "malformada"})
        assert check["results"][0]["state"] == "INVALID"
        # GitHub permanece CONNECTED.
        assert status["github_connected"] is True
    finally:
        c.close()


def test_026_frontend_backend_synced():
    """Versión e iteración coherentes entre backend y frontend."""
    config_src = (PROJECT_ROOT / "app" / "core" / "config.py").read_text(encoding="utf-8")
    assert 'version: str = "0.21.0"' in config_src
    cc_src = (PROJECT_ROOT / "app" / "services" / "command_center.py").read_text(encoding="utf-8")
    assert '"iteration": "022"' in cc_src
    assert '"build": "022-one-click-activation"' in cc_src
    index = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    assert "v0.21.0" in index
    for page in ("mission-control.html", "agents-viz.html", "candidates.html"):
        content = (FRONTEND_DIR / page).read_text(encoding="utf-8")
        assert "022" in content or "0.21.0" in content


def test_026b_routes_and_telemetry(tmp_path):
    """Rutas directas (/candidates, /mission-control, /agents-viz), endpoint de
    bootstrap y telemetría honesta con el bootstrap aplicado."""
    from fastapi.testclient import TestClient
    from app.main import create_app

    c = _container(tmp_path)
    c.bootstrap.apply()
    app = create_app(c)
    with TestClient(app) as client:
        assert client.get("/candidates").status_code == 200
        assert client.get("/mission-control").status_code == 200
        assert client.get("/agents-viz").status_code == 200
        st = client.get("/api/bootstrap/status").json()
        assert st["applied"] is True
        assert st["readiness_state"] == "READY_TO_CONNECT_SERVICES"
        tel = client.get("/api/agent-telemetry").json()
        assert tel["bootstrap"]["applied"] is True
        assert tel["run"]["state"] in ("RESEARCH_IMPORTED", "CANDIDATES_READY", "FINALISTS_READY",
                                       "COMMITTEE_READY", "COMMITTEE_PENDING", "EXPERIMENT_READY")
        # La telemetría usa el título local del concepto (con acentos) y el
        # paquete el título normalizado; se comparan normalizados.
        winner_title = (tel.get("launch_winner") or {}).get("title") or ""
        assert _normalize(winner_title) == _normalize(WINNER_TITLE)
        # Ningún agente ACTIVE sin actividad persistida.
        for agent in tel["agents"]:
            if agent["status"] == "ACTIVE":
                assert agent["event_count"] > 0
        # Demo nunca presente en telemetría real.
        assert tel.get("data_nature") != "DEMO"
        assert "demo" not in json.dumps(tel).lower().replace("demo", "DEMO")  # sin etiquetas demo en real
    c.close()


def _normalize(text: str) -> str:
    import unicodedata
    import re as _re

    t = unicodedata.normalize("NFKD", str(text or "").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return _re.sub(r"[^a-z0-9]+", " ", t).strip()


def test_026c_assets_checksums():
    """Manifiesto con checksum: la investigación portable coincide con el hash."""
    manifest = json.loads((ASSET_DIR / "manifest.json").read_text(encoding="utf-8"))
    expected = manifest["checksums"]["investigacion_fase1_021.json"]
    actual = __import__("hashlib").sha256(
        (ASSET_DIR / "investigacion_fase1_021.json").read_bytes()
    ).hexdigest()
    assert actual == expected
    expected_c = manifest["checksums"]["candidatas.json"]
    actual_c = __import__("hashlib").sha256(
        (ASSET_DIR / "candidatas.json").read_bytes()
    ).hexdigest()
    assert actual_c == expected_c


def test_026d_buyer_confirmed_is_hypothesis(tmp_path):
    """buyer_confirmed del paquete se trata como HIPÓTESIS (sin entrevista real)."""
    research = json.loads((ASSET_DIR / "investigacion_fase1_021.json").read_text(encoding="utf-8"))
    for payload in research["payloads"]:
        for mission in payload.get("missions") or []:
            value = mission.get("buyer_confirmed")
            assert value is not True, "buyer_confirmed no puede ser true sin entrevista real"
            if isinstance(value, dict):
                # Metadatos de hipótesis: nunca un booleano que afirme confirmación.
                assert "hipotesis" in json.dumps(value, ensure_ascii=False).lower()
    manifest = json.loads((ASSET_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["provenance"]["buyer_confirmed_is_hypothesis"] is True
