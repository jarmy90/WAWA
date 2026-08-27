"""Repositorio del Multi-Agent Ideation Arena.

Persiste ideas, lotes importados, estado de la arena y eventos del log vivo.
Esquema con CREATE TABLE IF NOT EXISTS compatible con iteraciones anteriores.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.models.arena import ArenaBatch, ArenaIdea, ArenaState, new_id, _now

ARENA_SCHEMA = """
CREATE TABLE IF NOT EXISTS arena_ideas (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT 'wawa',
    title TEXT NOT NULL,
    problem TEXT NOT NULL,
    buyer TEXT NOT NULL DEFAULT '',
    offer TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT '',
    price_hypothesis TEXT NOT NULL DEFAULT '',
    differentiation TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'GENERATED_HYPOTHESIS',
    structural_score REAL NOT NULL DEFAULT 0.0,
    structural_tags TEXT NOT NULL DEFAULT '[]',
    commodity_test TEXT NOT NULL DEFAULT 'PENDING',
    quality_gate TEXT NOT NULL DEFAULT 'PENDING',
    fingerprint TEXT NOT NULL DEFAULT '',
    merged_from TEXT NOT NULL DEFAULT '[]',
    convergence_count INTEGER NOT NULL DEFAULT 0,
    raw_source TEXT,
    file_hash TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_arena_ideas_provider ON arena_ideas(provider);
CREATE INDEX IF NOT EXISTS idx_arena_ideas_status ON arena_ideas(status);
CREATE INDEX IF NOT EXISTS idx_arena_ideas_batch ON arena_ideas(batch_id);

CREATE TABLE IF NOT EXISTS arena_batches (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    filename TEXT NOT NULL DEFAULT '',
    idea_count INTEGER NOT NULL DEFAULT 0,
    accepted_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    excess_count INTEGER NOT NULL DEFAULT 0,
    file_hash TEXT,
    error TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS arena_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    phase TEXT NOT NULL DEFAULT 'IDLE',
    generation_batch_id TEXT NOT NULL DEFAULT '',
    total_ideas INTEGER NOT NULL DEFAULT 0,
    wawa_count INTEGER NOT NULL DEFAULT 0,
    external_count INTEGER NOT NULL DEFAULT 0,
    duplicates_removed INTEGER NOT NULL DEFAULT 0,
    commodities_removed INTEGER NOT NULL DEFAULT 0,
    quality_failed INTEGER NOT NULL DEFAULT 0,
    tournament_survivors INTEGER NOT NULL DEFAULT 0,
    selected_for_review INTEGER NOT NULL DEFAULT 0,
    approved_for_research INTEGER NOT NULL DEFAULT 0,
    events TEXT NOT NULL DEFAULT '[]',
    started_at TEXT,
    last_event_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS arena_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    agent TEXT NOT NULL,
    message TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'info'
);
CREATE INDEX IF NOT EXISTS idx_arena_events_ts ON arena_events(id);
"""


class ArenaRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ---------------------------------------------------------------- state
    def get_state(self) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM arena_state WHERE id = 1").fetchone()
        if row is None:
            state = ArenaState()
            self.conn.execute(
                """INSERT INTO arena_state
                   (id, phase, generation_batch_id, total_ideas, wawa_count,
                    external_count, duplicates_removed, commodities_removed,
                    quality_failed, tournament_survivors, selected_for_review,
                    approved_for_research, events, started_at, last_event_at, updated_at)
                   VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (state.phase, state.generation_batch_id, state.total_ideas,
                 state.wawa_count, state.external_count, state.duplicates_removed,
                 state.commodities_removed, state.quality_failed, state.tournament_survivors,
                 state.selected_for_review, state.approved_for_research,
                 json.dumps(state.events), state.started_at, state.last_event_at, _now()),
            )
            self.conn.commit()
            return self.get_state()
        d = dict(row)
        d["events"] = json.loads(d.get("events") or "[]")
        return d

    def update_state(self, **fields: Any) -> dict[str, Any]:
        state = self.get_state()
        allowed = {
            "phase", "generation_batch_id", "total_ideas", "wawa_count",
            "external_count", "duplicates_removed", "commodities_removed",
            "quality_failed", "tournament_survivors", "selected_for_review",
            "approved_for_research", "events", "started_at", "last_event_at",
        }
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return state
        if "events" in sets:
            sets["events"] = json.dumps(sets["events"])
        sets["updated_at"] = _now()
        cols = ", ".join(f"{k} = ?" for k in sets)
        self.conn.execute(
            f"UPDATE arena_state SET {cols} WHERE id = 1",
            (*sets.values(),),
        )
        self.conn.commit()
        return self.get_state()

    # ---------------------------------------------------------------- ideas
    def save_idea(self, idea: ArenaIdea) -> dict[str, Any]:
        brief = idea.brief
        self.conn.execute(
            """INSERT OR REPLACE INTO arena_ideas
               (id, batch_id, provider, title, problem, buyer, offer, channel,
                price_hypothesis, differentiation, status, structural_score,
                structural_tags, commodity_test, quality_gate, fingerprint,
                merged_from, convergence_count, raw_source, file_hash,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                idea.id, idea.batch_id, idea.provider,
                brief.title, brief.problem, brief.buyer, brief.offer,
                brief.channel, brief.price_hypothesis, brief.differentiation,
                idea.status, idea.structural_score,
                json.dumps(idea.structural_tags),
                idea.commodity_test, idea.quality_gate, idea.fingerprint,
                json.dumps(idea.merged_from), idea.convergence_count,
                idea.raw_source, idea.file_hash,
                idea.created_at, idea.updated_at,
            ),
        )
        self.conn.commit()
        return self.get_idea(idea.id)

    def get_idea(self, idea_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM arena_ideas WHERE id = ?", (idea_id,)
        ).fetchone()
        return self._idea_row(row) if row else None

    def list_ideas(self, *, status: str | None = None, provider: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if provider:
            clauses.append("provider = ?")
            params.append(provider)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM arena_ideas{where} ORDER BY structural_score DESC, created_at ASC",
            params,
        ).fetchall()
        return [self._idea_row(r) for r in rows]

    def count_ideas(self, *, status: str | None = None, provider: str | None = None) -> int:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if provider:
            clauses.append("provider = ?")
            params.append(provider)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        row = self.conn.execute(f"SELECT COUNT(*) AS n FROM arena_ideas{where}", params).fetchone()
        return int(row["n"]) if row else 0

    def find_by_fingerprint(self, fingerprint: str) -> dict[str, Any] | None:
        if not fingerprint:
            return None
        row = self.conn.execute(
            "SELECT * FROM arena_ideas WHERE fingerprint = ? AND status NOT IN ('REJECTED','TOURNAMENT_ELIMINATED')",
            (fingerprint,),
        ).fetchone()
        return self._idea_row(row) if row else None

    def find_by_file_hash(self, file_hash: str) -> dict[str, Any] | None:
        if not file_hash:
            return None
        row = self.conn.execute(
            "SELECT * FROM arena_ideas WHERE file_hash = ?",
            (file_hash,),
        ).fetchone()
        return self._idea_row(row) if row else None

    def update_idea(self, idea_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {
            "status", "structural_score", "structural_tags", "commodity_test",
            "quality_gate", "fingerprint", "merged_from", "convergence_count",
            "batch_id", "raw_source", "file_hash", "updated_at",
        }
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return self.get_idea(idea_id)
        if "structural_tags" in sets and isinstance(sets["structural_tags"], list):
            sets["structural_tags"] = json.dumps(sets["structural_tags"])
        if "merged_from" in sets and isinstance(sets["merged_from"], list):
            sets["merged_from"] = json.dumps(sets["merged_from"])
        sets["updated_at"] = _now()
        cols = ", ".join(f"{k} = ?" for k in sets)
        self.conn.execute(
            f"UPDATE arena_ideas SET {cols} WHERE id = ?",
            (*sets.values(), idea_id),
        )
        self.conn.commit()
        return self.get_idea(idea_id)

    def delete_idea(self, idea_id: str) -> None:
        self.conn.execute("DELETE FROM arena_ideas WHERE id = ?", (idea_id,))
        self.conn.commit()

    # ---------------------------------------------------------------- batches
    def save_batch(self, batch: ArenaBatch) -> dict[str, Any]:
        self.conn.execute(
            """INSERT INTO arena_batches
               (id, provider, filename, idea_count, accepted_count,
                rejected_count, excess_count, file_hash, error, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                batch.id, batch.provider, batch.filename,
                batch.idea_count, batch.accepted_count, batch.rejected_count,
                batch.excess_count, batch.file_hash, batch.error, batch.created_at,
            ),
        )
        self.conn.commit()
        return dict(batch.model_dump())

    def list_batches(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM arena_batches ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------------------------------------------------------------- events
    def add_event(self, agent: str, message: str, kind: str = "info") -> dict[str, Any]:
        now = _now()
        self.conn.execute(
            "INSERT INTO arena_events (timestamp, agent, message, kind) VALUES (?,?,?,?)",
            (now, agent, message, kind),
        )
        self.conn.commit()
        return {"timestamp": now, "agent": agent, "message": message, "kind": kind}

    def list_events(self, limit: int = 200, *, agent: str | None = None) -> list[dict[str, Any]]:
        if agent:
            rows = self.conn.execute(
                "SELECT * FROM arena_events WHERE agent = ? ORDER BY id DESC LIMIT ?",
                (agent, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM arena_events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ---------------------------------------------------------------- mappers
    @staticmethod
    def _idea_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["structural_tags"] = json.loads(d.get("structural_tags") or "[]")
        d["merged_from"] = json.loads(d.get("merged_from") or "[]")
        return d
