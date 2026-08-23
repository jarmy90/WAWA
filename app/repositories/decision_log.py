"""Repositorio del registro de decisiones (append-only, auditable)."""
from __future__ import annotations

import json
import sqlite3

from app.models.decision_log import DecisionLog


def _row_to_model(row: sqlite3.Row) -> DecisionLog:
    data = dict(row)
    data["evidence_used"] = json.loads(data.get("evidence_used") or "[]")
    data["errors"] = json.loads(data.get("errors") or "[]")
    return DecisionLog.model_validate(data)


class DecisionLogRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(self, entry: DecisionLog) -> DecisionLog:
        cur = self.conn.execute(
            """INSERT INTO decision_log
               (timestamp, agent, opportunity_id, input_summary, output_summary, evidence_used,
                decision, model_or_method, estimated_cost, cost_method, errors)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.timestamp,
                entry.agent,
                entry.opportunity_id,
                entry.input_summary,
                entry.output_summary,
                json.dumps(entry.evidence_used),
                entry.decision,
                entry.model_or_method,
                entry.estimated_cost,
                entry.cost_method,
                json.dumps(entry.errors),
            ),
        )
        self.conn.commit()
        entry.id = cur.lastrowid
        return entry

    def list_for(self, opportunity_id: str, agent: str | None = None) -> list[DecisionLog]:
        if agent:
            rows = self.conn.execute(
                "SELECT * FROM decision_log WHERE opportunity_id = ? AND agent = ? ORDER BY id",
                (opportunity_id, agent),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM decision_log WHERE opportunity_id = ? ORDER BY id", (opportunity_id,)
            ).fetchall()
        return [_row_to_model(r) for r in rows]

    def recent(self, limit: int = 20) -> list[DecisionLog]:
        rows = self.conn.execute("SELECT * FROM decision_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [_row_to_model(r) for r in rows]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS n FROM decision_log").fetchone()["n"]
