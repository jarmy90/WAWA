"""Conexión SQLite y esquema inicial.

El esquema se crea automáticamente al arrancar (``init_db``). Las migraciones
futuras se gestionarán en este módulo.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.config import Settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    problem TEXT NOT NULL,
    proposed_solution TEXT,
    target_customer TEXT,
    sector TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    evidence_type TEXT NOT NULL,
    source_name TEXT,
    source_url TEXT,
    captured_at TEXT NOT NULL,
    summary TEXT NOT NULL,
    raw_excerpt TEXT,
    reliability_score REAL NOT NULL DEFAULT 0.5,
    independence_group TEXT,
    verified INTEGER NOT NULL DEFAULT 0,
    verification_notes TEXT,
    collected_by TEXT NOT NULL DEFAULT 'system',
    method TEXT NOT NULL DEFAULT 'mock'
);
CREATE INDEX IF NOT EXISTS idx_evidence_opp ON evidence(opportunity_id);

CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    url TEXT,
    offer TEXT,
    observed_price REAL,
    strengths TEXT,
    weaknesses TEXT,
    evidence_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_competitors_opp ON competitors(opportunity_id);

CREATE TABLE IF NOT EXISTS evaluations (
    evaluation_id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_id TEXT,
    campaign_id TEXT,
    mission_id TEXT,
    prompt_version TEXT,
    execution_mode TEXT NOT NULL DEFAULT 'MOCK',
    provenance TEXT NOT NULL DEFAULT '{}',
    pain_score REAL NOT NULL DEFAULT 0,
    demand_score REAL NOT NULL DEFAULT 0,
    customer_reach_score REAL NOT NULL DEFAULT 0,
    automation_score REAL NOT NULL DEFAULT 0,
    margin_score REAL NOT NULL DEFAULT 0,
    build_speed_score REAL NOT NULL DEFAULT 0,
    differentiation_score REAL NOT NULL DEFAULT 0,
    safety_score REAL NOT NULL DEFAULT 0,
    evidence_quality_score REAL NOT NULL DEFAULT 0,
    confidence_score REAL NOT NULL DEFAULT 0,
    final_score REAL NOT NULL DEFAULT 0,
    per_criterion TEXT NOT NULL DEFAULT '{}',
    independent_evidence_count INTEGER NOT NULL DEFAULT 0,
    unverified_assumptions_count INTEGER NOT NULL DEFAULT 0,
    assumptions TEXT NOT NULL DEFAULT '[]',
    blockers TEXT NOT NULL DEFAULT '[]',
    approval_reason TEXT,
    rejection_reason TEXT,
    decision TEXT NOT NULL DEFAULT 'deferred',
    model_or_method TEXT,
    skeptic_critique TEXT,
    risks TEXT NOT NULL DEFAULT '[]',
    estimates TEXT NOT NULL DEFAULT '{}',
    experiment TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    hypothesis TEXT,
    cheapest_test TEXT,
    maximum_budget REAL,
    success_metric TEXT,
    success_threshold TEXT,
    failure_threshold TEXT,
    duration TEXT,
    status TEXT NOT NULL DEFAULT 'proposed',
    result TEXT
);

CREATE TABLE IF NOT EXISTS decision_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    agent TEXT NOT NULL,
    opportunity_id TEXT,
    input_summary TEXT,
    output_summary TEXT,
    evidence_used TEXT NOT NULL DEFAULT '[]',
    decision TEXT,
    model_or_method TEXT,
    estimated_cost REAL NOT NULL DEFAULT 0,
    cost_method TEXT,
    errors TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_log_opp ON decision_log(opportunity_id);

CREATE TABLE IF NOT EXISTS costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    action TEXT NOT NULL,
    opportunity_id TEXT,
    provider TEXT,
    estimated_cost_usd REAL NOT NULL DEFAULT 0,
    cost_method TEXT,
    simulation INTEGER NOT NULL DEFAULT 0,
    blocked INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS engine_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    mode TEXT NOT NULL DEFAULT 'development_and_review',
    engine_state TEXT NOT NULL DEFAULT 'researching',
    current_task TEXT,
    task_started_at TEXT,
    last_result TEXT,
    next_action TEXT,
    heartbeat_at TEXT,
    activated_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mode_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    from_mode TEXT NOT NULL,
    to_mode TEXT NOT NULL,
    reason TEXT,
    actor TEXT NOT NULL DEFAULT 'system',
    evidence_used TEXT NOT NULL DEFAULT '[]',
    budget_consumed_usd REAL NOT NULL DEFAULT 0,
    revenue_usd REAL NOT NULL DEFAULT 0,
    decision TEXT,
    rule TEXT
);

CREATE TABLE IF NOT EXISTS engine_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    opportunity_id TEXT,
    engine_state TEXT,
    mode TEXT,
    cost_usd REAL NOT NULL DEFAULT 0,
    confidence REAL
);
CREATE INDEX IF NOT EXISTS idx_engine_events_ts ON engine_events(id);

-- Ledger contable (append-only). Los importes se guardan como TEXT para
-- preservar la precisión Decimal (nunca float).
CREATE TABLE IF NOT EXISTS ledger_entries (
    id TEXT PRIMARY KEY,
    entry_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    amount TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    status TEXT NOT NULL DEFAULT 'PENDING',
    source_type TEXT,
    source_id TEXT,
    opportunity_id TEXT,
    experiment_id TEXT,
    description TEXT NOT NULL,
    evidence_reference TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    operating_mode TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'system',
    created_at TEXT NOT NULL,
    confirmed_at TEXT,
    reversed_entry_id TEXT,
    metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_ledger_opp ON ledger_entries(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_ledger_exp ON ledger_entries(experiment_id);
CREATE INDEX IF NOT EXISTS idx_ledger_status ON ledger_entries(status);
CREATE INDEX IF NOT EXISTS idx_ledger_created ON ledger_entries(created_at);

CREATE TABLE IF NOT EXISTS reconciliation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    reconciled INTEGER NOT NULL DEFAULT 0,
    issues TEXT NOT NULL DEFAULT '[]',
    summary TEXT NOT NULL DEFAULT '{}',
    triggered_pause INTEGER NOT NULL DEFAULT 0
);

-- Business Discovery Engine (iteración 004)
CREATE TABLE IF NOT EXISTS discovery_campaigns (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    territory_keys TEXT NOT NULL DEFAULT '[]',
    lens_keys TEXT NOT NULL DEFAULT '[]',
    archetype_keys TEXT NOT NULL DEFAULT '[]',
    phase TEXT NOT NULL DEFAULT 'created',
    status TEXT NOT NULL DEFAULT 'active',
    phase1_target INTEGER NOT NULL DEFAULT 60,
    shortlist_target INTEGER NOT NULL DEFAULT 10,
    finalists_target INTEGER NOT NULL DEFAULT 3,
    diversity REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS discovery_concepts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES discovery_campaigns(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    territory_key TEXT,
    lens_keys TEXT NOT NULL DEFAULT '[]',
    archetype_key TEXT,
    problem_hypothesis TEXT NOT NULL,
    mechanism TEXT NOT NULL,
    buyer_hypothesis TEXT,
    outcome_hypothesis TEXT,
    why_now TEXT,
    general_ai_risk TEXT,
    asset_potential TEXT,
    fingerprint TEXT NOT NULL DEFAULT '{}',
    phase TEXT NOT NULL DEFAULT 'phase1',
    status TEXT NOT NULL DEFAULT 'draft',
    source TEXT NOT NULL DEFAULT 'generated',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_concepts_campaign ON discovery_concepts(campaign_id);

CREATE TABLE IF NOT EXISTS substitution_tests (
    id TEXT PRIMARY KEY,
    concept_id TEXT NOT NULL REFERENCES discovery_concepts(id) ON DELETE CASCADE,
    classification TEXT NOT NULL,
    general_ai_resistance REAL NOT NULL DEFAULT 0,
    verdict TEXT NOT NULL,
    answers TEXT NOT NULL DEFAULT '{}',
    reasons TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_substitution_concept ON substitution_tests(concept_id);

CREATE TABLE IF NOT EXISTS venture_evaluations (
    id TEXT PRIMARY KEY,
    concept_id TEXT NOT NULL REFERENCES discovery_concepts(id) ON DELETE CASCADE,
    scores TEXT NOT NULL DEFAULT '{}',
    final_score REAL NOT NULL DEFAULT 0,
    -- Iteración 013: puntuación estructural vs puntuación con evidencia.
    structural_concept_score REAL NOT NULL DEFAULT 0,
    evidence_backed_venture_score REAL NOT NULL DEFAULT 0,
    has_verified_evidence INTEGER NOT NULL DEFAULT 0,
    novelty_score REAL NOT NULL DEFAULT 0,
    utility_score REAL NOT NULL DEFAULT 0,
    blockers TEXT NOT NULL DEFAULT '[]',
    labels TEXT NOT NULL DEFAULT '[]',
    rationale TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_venture_concept ON venture_evaluations(concept_id);

CREATE TABLE IF NOT EXISTS concept_comparisons (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES discovery_campaigns(id) ON DELETE CASCADE,
    winner_id TEXT NOT NULL,
    loser_id TEXT NOT NULL,
    winner_score REAL NOT NULL DEFAULT 0,
    loser_score REAL NOT NULL DEFAULT 0,
    criteria TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS learning_records (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    pattern TEXT NOT NULL,
    source TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS research_missions (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    target TEXT NOT NULL DEFAULT '{}',
    export_payload TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'exported',
    created_at TEXT NOT NULL,
    imported_at TEXT
);

CREATE TABLE IF NOT EXISTS mission_results (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES research_missions(mission_id) ON DELETE CASCADE,
    raw TEXT NOT NULL DEFAULT '{}',
    evidences TEXT NOT NULL DEFAULT '[]',
    competitors TEXT NOT NULL DEFAULT '[]',
    buyer_confirmed TEXT,
    verified INTEGER NOT NULL DEFAULT 0,
    verification_notes TEXT,
    imported_at TEXT NOT NULL
);

-- Comité de contraste (iteración 005): revisiones externas de finalistas.
CREATE TABLE IF NOT EXISTS review_queue (
    opportunity_id TEXT PRIMARY KEY REFERENCES opportunities(id) ON DELETE CASCADE,
    internal_score REAL NOT NULL DEFAULT 0,
    queued_at TEXT NOT NULL,
    window_deadline TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    review_required INTEGER NOT NULL DEFAULT 0,
    reviewed_without_external INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS external_reviews (
    id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    provider TEXT NOT NULL DEFAULT 'unknown',
    model TEXT NOT NULL DEFAULT 'unknown',
    model_version TEXT,
    execution_mode TEXT NOT NULL DEFAULT 'MANUAL_IMPORT',
    review_date TEXT NOT NULL,
    raw_response TEXT NOT NULL,
    parsed_response TEXT NOT NULL DEFAULT '{}',
    recommendation TEXT,
    confidence REAL,
    strongest_evidence TEXT,
    weakest_assumption TEXT,
    missing_evidence TEXT,
    primary_risk TEXT,
    suggested_improvement TEXT,
    cheaper_experiment TEXT,
    kill_condition TEXT,
    cost REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'valid',
    parse_errors TEXT NOT NULL DEFAULT '[]',
    imported_by TEXT NOT NULL DEFAULT 'system',
    file_hash TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (opportunity_id, file_hash)
);
CREATE INDEX IF NOT EXISTS idx_reviews_opp ON external_reviews(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_reviews_status ON external_reviews(status);

-- Estado del ciclo económico inicial (iteración 009-010): fila única (id=1).
-- started_at es NULLABLE: el reloj NO arranca hasta POST /cycle/start.
-- Concesión de prórroga auditable: una sola vez por ciclo.
CREATE TABLE IF NOT EXISTS cycle_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    started_at TEXT,
    extension_granted_at TEXT,
    extension_count INTEGER NOT NULL DEFAULT 0
);

-- Orquestador end-to-end (iteración 010): ejecución única por campaña real.
CREATE TABLE IF NOT EXISTS orchestrator_runs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    campaign_type TEXT NOT NULL DEFAULT 'real_market_discovery',
    state TEXT NOT NULL DEFAULT 'CAMPAIGN_CREATED',
    status TEXT NOT NULL DEFAULT 'active',
    config TEXT NOT NULL DEFAULT '{}',
    discovery_campaign_id TEXT,
    selected_opportunity_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orchestrator_state ON orchestrator_runs(state);

CREATE TABLE IF NOT EXISTS orchestrator_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES orchestrator_runs(id) ON DELETE CASCADE,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'system',
    reason TEXT,
    inputs TEXT NOT NULL DEFAULT '{}',
    outputs TEXT NOT NULL DEFAULT '{}',
    concepts_considered INTEGER NOT NULL DEFAULT 0,
    concepts_rejected INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL,
    cost_source TEXT,
    errors TEXT NOT NULL DEFAULT '[]',
    blockers TEXT NOT NULL DEFAULT '[]',
    next_action TEXT,
    owner_action_required INTEGER NOT NULL DEFAULT 0,
    synthetic INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_orchestrator_transitions_run ON orchestrator_transitions(run_id);

-- Plan de experimento (iteración 010): creado tras decisión SMALL/PRIORITY.
CREATE TABLE IF NOT EXISTS experiment_plans (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES orchestrator_runs(id) ON DELETE CASCADE,
    opportunity_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    offer TEXT,
    buyer TEXT,
    user TEXT,
    problem TEXT,
    value_proposition TEXT,
    price_usd REAL,
    delivery_format TEXT,
    demo TEXT,
    channel TEXT,
    initial_message TEXT,
    min_sample INTEGER,
    max_contacts INTEGER,
    acquisition_method TEXT,
    max_cost_usd REAL,
    duration_days INTEGER,
    success_metric TEXT,
    success_threshold TEXT,
    kill_condition TEXT,
    product_death_condition TEXT,
    possible_pivots TEXT NOT NULL DEFAULT '[]',
    automatable_tasks TEXT NOT NULL DEFAULT '[]',
    owner_tasks TEXT NOT NULL DEFAULT '[]',
    risks TEXT NOT NULL DEFAULT '[]',
    dependencies TEXT NOT NULL DEFAULT '[]',
    payment_readiness TEXT,
    missing_capabilities TEXT NOT NULL DEFAULT '[]',
    blockers TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_syntheses (
    opportunity_id TEXT PRIMARY KEY REFERENCES opportunities(id) ON DELETE CASCADE,
    reviews_count INTEGER NOT NULL DEFAULT 0,
    valid_reviews_count INTEGER NOT NULL DEFAULT 0,
    consensus_level TEXT NOT NULL DEFAULT 'NONE',
    recommendation_distribution TEXT NOT NULL DEFAULT '{}',
    average_confidence REAL,
    agreements TEXT NOT NULL DEFAULT '[]',
    disagreements TEXT NOT NULL DEFAULT '[]',
    unique_risks TEXT NOT NULL DEFAULT '[]',
    repeated_risks TEXT NOT NULL DEFAULT '[]',
    missing_evidence TEXT NOT NULL DEFAULT '[]',
    recommended_next_action TEXT,
    internal_score_before REAL,
    internal_score_after REAL,
    score_change_reason TEXT,
    generated_at TEXT NOT NULL
);

-- CampaignRunner Freebuff-first (iteración 006): campañas reanudables por sesiones.
CREATE TABLE IF NOT EXISTS ff_campaigns (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    stage TEXT NOT NULL DEFAULT 'CREATED',
    discovery_campaign_id TEXT,
    territory_keys TEXT NOT NULL DEFAULT '[]',
    lens_keys TEXT NOT NULL DEFAULT '[]',
    archetype_keys TEXT NOT NULL DEFAULT '[]',
    time_budget_hours INTEGER NOT NULL DEFAULT 3,
    api_budget_usd REAL NOT NULL DEFAULT 0,
    experiment_budget_usd REAL NOT NULL DEFAULT 0,
    external_review_slots INTEGER NOT NULL DEFAULT 3,
    maximum_deep_research_candidates INTEGER NOT NULL DEFAULT 10,
    funnel_limits TEXT NOT NULL DEFAULT '{}',
    signals_count INTEGER NOT NULL DEFAULT 0,
    concepts_count INTEGER NOT NULL DEFAULT 0,
    concepts_rejected INTEGER NOT NULL DEFAULT 0,
    finalists_count INTEGER NOT NULL DEFAULT 0,
    missions_count INTEGER NOT NULL DEFAULT 0,
    evidences_added INTEGER NOT NULL DEFAULT 0,
    sessions_count INTEGER NOT NULL DEFAULT 0,
    is_synthetic INTEGER NOT NULL DEFAULT 0,
    closed_reason TEXT,
    next_recommended_action TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ff_transitions (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES ff_campaigns(id) ON DELETE CASCADE,
    from_stage TEXT NOT NULL,
    to_stage TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'system',
    reason TEXT,
    inputs_used TEXT NOT NULL DEFAULT '[]',
    outputs_generated TEXT NOT NULL DEFAULT '[]',
    concepts_considered INTEGER NOT NULL DEFAULT 0,
    concepts_rejected INTEGER NOT NULL DEFAULT 0,
    costs_recorded TEXT NOT NULL DEFAULT '{}',
    unknowns TEXT NOT NULL DEFAULT '[]',
    errors TEXT NOT NULL DEFAULT '[]',
    next_recommended_action TEXT
);
CREATE INDEX IF NOT EXISTS idx_ff_transitions_camp ON ff_transitions(campaign_id);

CREATE TABLE IF NOT EXISTS ff_sessions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE,
    campaign_id TEXT NOT NULL REFERENCES ff_campaigns(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'planned',
    time_budget_hours INTEGER NOT NULL,
    stage_start TEXT NOT NULL,
    stage_end TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    tasks_planned TEXT NOT NULL DEFAULT '[]',
    tasks_completed TEXT NOT NULL DEFAULT '[]',
    tasks_pending TEXT NOT NULL DEFAULT '[]',
    concepts_created INTEGER NOT NULL DEFAULT 0,
    concepts_rejected INTEGER NOT NULL DEFAULT 0,
    evidences_added INTEGER NOT NULL DEFAULT 0,
    review_packets_created INTEGER NOT NULL DEFAULT 0,
    blockers TEXT NOT NULL DEFAULT '[]',
    errors TEXT NOT NULL DEFAULT '[]',
    next_action TEXT,
    repo_commit TEXT,
    plan_path TEXT,
    state_path TEXT,
    output_path TEXT,
    report_path TEXT,
    next_session_path TEXT,
    short_prompt TEXT,
    is_synthetic INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_ff_sessions_camp ON ff_sessions(campaign_id);

CREATE TABLE IF NOT EXISTS ff_readiness (
    id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    state TEXT NOT NULL,
    criteria TEXT NOT NULL DEFAULT '{}',
    unknown_criteria TEXT NOT NULL DEFAULT '[]',
    missing TEXT NOT NULL DEFAULT '[]',
    reasoning TEXT,
    proposed_daily_limit_usd REAL,
    estimated_cost_per_call_usd REAL,
    estimated_value_per_call_usd REAL,
    evaluated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ff_reasoning_log (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES ff_campaigns(id) ON DELETE CASCADE,
    session_id TEXT,
    level TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_call_log (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    action TEXT NOT NULL DEFAULT 'llm_call',
    opportunity_id TEXT,
    requested_model TEXT NOT NULL DEFAULT '',
    actual_model TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    reported_cost REAL,
    estimated_cost REAL,
    cost_source TEXT NOT NULL DEFAULT 'UNKNOWN',
    billing_verified INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER,
    retry_count INTEGER NOT NULL DEFAULT 0,
    fallback_used INTEGER NOT NULL DEFAULT 0,
    response_status TEXT NOT NULL DEFAULT 'ok',
    notes TEXT,
    created_at TEXT NOT NULL,
    actual_provider TEXT,
    routing_strategy TEXT,
    fallback_reason TEXT,
    response_is_external INTEGER NOT NULL DEFAULT 1,
    response_is_synthetic INTEGER NOT NULL DEFAULT 0,
    quota_state TEXT
);
CREATE INDEX IF NOT EXISTS idx_llm_call_created ON llm_call_log(created_at);
CREATE INDEX IF NOT EXISTS idx_llm_call_opp ON llm_call_log(opportunity_id);

-- Bootstrap comercial (iteración 022): fila única (id=1) con el estado
-- APLICADO de la activación comercial. Idempotente: si ya está aplicado,
-- START_WAWA.bat y el botón REPARAR Y CONTINUAR no duplican datos.
CREATE TABLE IF NOT EXISTS commercial_bootstrap_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    applied_version TEXT NOT NULL DEFAULT '',
    applied_at TEXT,
    run_id TEXT,
    campaign_id TEXT,
    winner_opportunity_id TEXT,
    asset_hash TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
);

-- Checkpoints del bootstrap (iteración 022): append-only, permiten reanudar
-- tras un corte de alimentación sin repetir pasos completados.
CREATE TABLE IF NOT EXISTS bootstrap_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component TEXT NOT NULL,
    state TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bootstrap_checkpoints_component ON bootstrap_checkpoints(component);
"""


def _ensure_evaluation_columns(conn: sqlite3.Connection) -> None:
    """Migración idempotente del historial de evaluaciones (iteración 028)."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(evaluations)").fetchall()}
    additions = {
        "evaluation_id": "TEXT",
        "version": "INTEGER NOT NULL DEFAULT 1",
        "supersedes_id": "TEXT",
        "campaign_id": "TEXT",
        "mission_id": "TEXT",
        "prompt_version": "TEXT",
        "execution_mode": "TEXT NOT NULL DEFAULT 'MOCK'",
        "provenance": "TEXT NOT NULL DEFAULT '{}'",
        "prompt_version": "TEXT",
        "integrity_status": "TEXT NOT NULL DEFAULT 'VALID'",
        "provider": "TEXT",
        "invalidated_at": "TEXT",
    }
    for name, ddl in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE evaluations ADD COLUMN {name} {ddl}")
    rows = conn.execute("SELECT rowid, evaluation_id FROM evaluations").fetchall()
    import uuid
    for row in rows:
        if not row["evaluation_id"]:
            conn.execute("UPDATE evaluations SET evaluation_id = ? WHERE rowid = ?", (uuid.uuid4().hex, row["rowid"]))
    conn.commit()


def _ensure_llm_call_columns(conn: sqlite3.Connection) -> None:
    """Migración idempotente para bases creadas antes de la iteración 008."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(llm_call_log)").fetchall()}
    columns = {
        "actual_provider": "TEXT",
        "routing_strategy": "TEXT",
        "fallback_reason": "TEXT",
        "response_is_external": "INTEGER NOT NULL DEFAULT 1",
        "response_is_synthetic": "INTEGER NOT NULL DEFAULT 0",
        "quota_state": "TEXT",
    }
    for name, ddl in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE llm_call_log ADD COLUMN {name} {ddl}")
    conn.commit()


def _ensure_venture_columns(conn: sqlite3.Connection) -> None:
    """Migración idempotente (iteración 013): columnas de puntuación estructural
    vs puntuación con evidencia en venture_evaluations."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(venture_evaluations)").fetchall()}
    if "structural_concept_score" not in existing:
        conn.execute("ALTER TABLE venture_evaluations ADD COLUMN structural_concept_score REAL NOT NULL DEFAULT 0")
    if "evidence_backed_venture_score" not in existing:
        conn.execute("ALTER TABLE venture_evaluations ADD COLUMN evidence_backed_venture_score REAL NOT NULL DEFAULT 0")
    if "has_verified_evidence" not in existing:
        conn.execute("ALTER TABLE venture_evaluations ADD COLUMN has_verified_evidence INTEGER NOT NULL DEFAULT 0")
    conn.commit()


def _ensure_concept_columns(conn: sqlite3.Connection) -> None:
    """Migración idempotente (iteración 013): Opportunity Brief + coherencia
    en discovery_concepts."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(discovery_concepts)").fetchall()}
    if "brief" not in existing:
        conn.execute("ALTER TABLE discovery_concepts ADD COLUMN brief TEXT NOT NULL DEFAULT '{}'")
    if "coherence_ok" not in existing:
        conn.execute("ALTER TABLE discovery_concepts ADD COLUMN coherence_ok INTEGER NOT NULL DEFAULT 1")
    if "coherence_reason" not in existing:
        conn.execute("ALTER TABLE discovery_concepts ADD COLUMN coherence_reason TEXT NOT NULL DEFAULT ''")
    conn.commit()


def _ensure_runtime_state(conn: sqlite3.Connection) -> None:
    """Ensure runtime_state singleton row exists (iteración 025)."""
    row = conn.execute("SELECT id FROM runtime_state WHERE id = 1").fetchone()
    if not row:
        import datetime
        now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            """INSERT INTO runtime_state (id, operating_mode, updated_at)
               VALUES (1, 'OFFLINE', ?)""",
            (now,),
        )
        conn.commit()


def _migrate_cycle_state_nullable(conn: sqlite3.Connection) -> None:
    """Migración idempotente (iteración 010): cycle_state.started_at pasa a
    aceptar NULL para que el estado PRE_CYCLE no cree el reloj al consultar.
    Bases de la 009 pueden tener la columna NOT NULL; se reconstruye la tabla
    sin borrar datos de prórroga (extension_count/extension_granted_at)."""
    cols = conn.execute("PRAGMA table_info(cycle_state)").fetchall()
    if not cols:
        return
    started = next((c for c in cols if c["name"] == "started_at"), None)
    if started is not None and started["notnull"] == 0:
        return  # ya es NULLABLE: nada que hacer
    conn.execute("ALTER TABLE cycle_state RENAME TO cycle_state_old")
    conn.execute(
        """CREATE TABLE cycle_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            started_at TEXT,
            extension_granted_at TEXT,
            extension_count INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.execute(
        """INSERT INTO cycle_state (id, started_at, extension_granted_at, extension_count)
           SELECT id, NULL, extension_granted_at, extension_count FROM cycle_state_old"""
    )
    conn.execute("DROP TABLE cycle_state_old")
    conn.commit()


def connect(db_path: Path | str) -> sqlite3.Connection:
    # check_same_thread=False: los servidores web (uvicorn/TestClient) atienden
    # peticiones en hilos distintos; cada operación es una transacción corta y
    # WAL serializa los accesos entre hilos.
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Iteración 023: busy_timeout evita que una colisión con OTRA conexión
    # (p. ej. scripts de mantenimiento junto al servidor) reviente como
    # "database is locked"; esperar acotado es preferible a fallar. La
    # serialización del acceso concurrente DENTRO de la app se hace con el
    # single-flight lock de las rutas del comité (ver app/api/routes.py).
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(settings: Settings) -> None:
    """Crea el esquema si no existe. Idempotente. Se llama al arrancar."""
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(settings.database_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        _ensure_evaluation_columns(conn)
        _ensure_llm_call_columns(conn)
        _ensure_venture_columns(conn)
        _ensure_concept_columns(conn)
        _migrate_cycle_state_nullable(conn)
        # Arena (iteración 024)
        from app.repositories.arena import ARENA_SCHEMA as _ARENA
        conn.executescript(_ARENA)
        conn.commit()
        # Autonomous 24/7 runtime (iteración 025)
        from app.repositories.jobs import JOB_SCHEMA as _JOB
        conn.executescript(_JOB)
        conn.commit()
        _ensure_runtime_state(conn)
    finally:
        conn.close()
