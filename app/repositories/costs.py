"""Repositorio de registros de coste (alimenta al BudgetGuard)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.models.decision_log import CostRecord


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _row_to_model(row: sqlite3.Row) -> CostRecord:
    data = dict(row)
    data["simulation"] = bool(data["simulation"])
    data["blocked"] = bool(data["blocked"])
    return CostRecord.model_validate(data)


class CostRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(self, record: CostRecord) -> CostRecord:
        cur = self.conn.execute(
            """INSERT INTO costs
               (timestamp, action, opportunity_id, provider, estimated_cost_usd, cost_method, simulation, blocked)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.timestamp,
                record.action,
                record.opportunity_id,
                record.provider,
                record.estimated_cost_usd,
                record.cost_method,
                int(record.simulation),
                int(record.blocked),
            ),
        )
        self.conn.commit()
        record.id = cur.lastrowid
        return record

    def spent_today(self) -> float:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(estimated_cost_usd), 0) AS total FROM costs WHERE timestamp LIKE ?",
            (f"{_today()}%",),
        ).fetchone()
        return float(row["total"])

    def spent_for_opportunity(self, opportunity_id: str) -> float:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(estimated_cost_usd), 0) AS total FROM costs WHERE opportunity_id = ?",
            (opportunity_id,),
        ).fetchone()
        return float(row["total"])

    def deep_evaluations_today(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM costs WHERE action = 'deep_evaluation' AND timestamp LIKE ?",
            (f"{_today()}%",),
        ).fetchone()
        return int(row["n"])

    def recent(self, limit: int = 50) -> list[CostRecord]:
        rows = self.conn.execute("SELECT * FROM costs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [_row_to_model(r) for r in rows]
