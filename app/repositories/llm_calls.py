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
                fallback_used, response_status, notes, created_at, actual_provider,
                routing_strategy, fallback_reason, response_is_external,
                response_is_synthetic, quota_state)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
                record.actual_provider,
                record.routing_strategy,
                record.fallback_reason,
                1 if record.response_is_external else 0,
                1 if record.response_is_synthetic else 0,
                record.quota_state,
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
        """Total de costes CONOCIDOS (reported si existe, si no estimated).

        Cota inferior honesta: las llamadas con coste desconocido NO se
        convierten en cero en el agregado; se excluyen y se informan por
        separado con ``cost_detail_since``.
        """
        query = (
            "SELECT COALESCE(SUM(COALESCE(reported_cost, estimated_cost)), 0) AS total "
            "FROM llm_call_log WHERE created_at >= ? "
            "AND (reported_cost IS NOT NULL OR estimated_cost IS NOT NULL)"
        )
        params: list[Any] = [since_iso]
        if provider:
            query += " AND provider = ?"
            params.append(provider)
        row = self.conn.execute(query, params).fetchone()
        return float(row["total"] or 0.0)

    def cost_detail_since(self, since_iso: str, *, provider: str | None = None) -> dict[str, Any]:
        """Desglose honesto de costes: reportado, estimado, cero reales y desconocidos.

        Distingue coste real 0, estimado 0 y coste desconocido (NULL): un
        coste desconocido nunca se convierte en cero.
        """
        query = (
            "SELECT COUNT(*) AS total_calls, "
            "SUM(CASE WHEN reported_cost IS NOT NULL THEN 1 ELSE 0 END) AS reported_calls, "
            "SUM(CASE WHEN reported_cost IS NULL AND estimated_cost IS NOT NULL THEN 1 ELSE 0 END) AS estimated_calls, "
            "SUM(CASE WHEN reported_cost IS NULL AND estimated_cost IS NULL THEN 1 ELSE 0 END) AS unknown_calls, "
            "SUM(CASE WHEN COALESCE(reported_cost, estimated_cost) = 0 THEN 1 ELSE 0 END) AS zero_calls, "
            "COALESCE(SUM(reported_cost), 0) AS reported_total, "
            "COALESCE(SUM(CASE WHEN reported_cost IS NULL THEN estimated_cost ELSE 0 END), 0) AS estimated_total "
            "FROM llm_call_log WHERE created_at >= ?"
        )
        params: list[Any] = [since_iso]
        if provider:
            query += " AND provider = ?"
            params.append(provider)
        row = self.conn.execute(query, params).fetchone()
        reported_calls = int(row["reported_calls"] or 0)
        estimated_calls = int(row["estimated_calls"] or 0)
        unknown_calls = int(row["unknown_calls"] or 0)
        reported_total = float(row["reported_total"] or 0.0) if reported_calls > 0 else None
        estimated_total = float(row["estimated_total"] or 0.0) if estimated_calls > 0 else None
        return {
            "total_calls": int(row["total_calls"] or 0),
            "reported_calls": reported_calls,
            "estimated_calls": estimated_calls,
            "unknown_calls": unknown_calls,
            "zero_calls": int(row["zero_calls"] or 0),
            "reported_total": reported_total,
            "estimated_total": estimated_total,
            "known_total": float((reported_total or 0.0) + (estimated_total or 0.0)),
            "complete": unknown_calls == 0,
        }

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
        d["response_is_external"] = bool(d.get("response_is_external"))
        d["response_is_synthetic"] = bool(d.get("response_is_synthetic"))
        return d
