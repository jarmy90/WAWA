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
    opportunity_id TEXT PRIMARY KEY REFERENCES opportunities(id) ON DELETE CASCADE,
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
"""


def connect(db_path: Path | str) -> sqlite3.Connection:
    # check_same_thread=False: los servidores web (uvicorn/TestClient) atienden
    # peticiones en hilos distintos; cada operación es una transacción corta y
    # WAL serializa los accesos entre hilos.
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
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
    finally:
        conn.close()
