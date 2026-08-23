"""Registro append-only de llamadas LLM (append-only: no se edita ni borra)."""
from __future__ import annotations

import sqlite3
from typing import Any

from app.models.llm_call import LLMCallRecord


class LLMCallRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(self, record: LLMCallRecord) -> dict[str, Any]:
        self.conn.execute(
            """INSERT INTO llm_call_log
               (id, provider, action, opportunity_id, requested_model, actual_model,
                prompt_tokens, completion_tokens, total_tokens, reported_cost,
                estimated_cost, cost_source, billing_verified, latency_ms, retry_count,
                fallback_used, response_status, notes, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                record.id,
                record.provider,
                record.action,
                record.opportunity_id,
                record.requested_model,
                record.actual_model,
                record.prompt_tokens,
                record.completion_tokens,
                record.total_tokens,
                record.reported_cost,
                record.estimated_cost,
                record.cost_source,
                1 if record.billing_verified else 0,
                record.latency_ms,
                record.retry_count,
                1 if record.fallback_used else 0,
                record.response_status,
                record.notes,
                record.created_at,
            ),
        )
        self.conn.commit()
        return self.get(record.id)  # type: ignore[return-value]

    def get(self, record_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM llm_call_log WHERE id = ?", (record_id,)).fetchone()
        return self._row(row) if row else None

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM llm_call_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row(r) for r in rows]

    def count_since(self, since_iso: str, *, provider: str | None = None) -> int:
        query = "SELECT COUNT(*) AS n FROM llm_call_log WHERE created_at >= ?"
        params: list[Any] = [since_iso]
        if provider:
            query += " AND provider = ?"
            params.append(provider)
        row = self.conn.execute(query, params).fetchone()
        return int(row["n"])

    def cost_since(self, since_iso: str, *, provider: str | None = None) -> float:
        """Suma honesta: reported_cost si existe, si no estimated_cost (etiquetado)."""
        query = (
            "SELECT COALESCE(SUM(COALESCE(reported_cost, estimated_cost, 0)), 0) AS total "
            "FROM llm_call_log WHERE created_at >= ?"
        )
        params: list[Any] = [since_iso]
        if provider:
            query += " AND provider = ?"
            params.append(provider)
        row = self.conn.execute(query, params).fetchone()
        return float(row["total"] or 0.0)

    def failures_since(self, since_iso: str, *, provider: str | None = None) -> int:
        query = "SELECT COUNT(*) AS n FROM llm_call_log WHERE created_at >= ? AND response_status != 'ok'"
        params: list[Any] = [since_iso]
        if provider:
            query += " AND provider = ?"
            params.append(provider)
        row = self.conn.execute(query, params).fetchone()
        return int(row["n"])

    def count_auto_reviews_for(self, opportunity_id: str) -> int:
        """Revisiones automáticas ya realizadas para una oportunidad."""
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM external_reviews "
            "WHERE opportunity_id = ? AND execution_mode = 'API_AUTOMATIC'",
            (opportunity_id,),
        ).fetchone()
        return int(row["n"])

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["billing_verified"] = bool(d.get("billing_verified"))
        d["fallback_used"] = bool(d.get("fallback_used"))
        return d
