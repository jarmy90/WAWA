"""Repositorio de evidencias."""
from __future__ import annotations

import sqlite3

from app.models.evidence import Evidence


def _row_to_model(row: sqlite3.Row) -> Evidence:
    data = dict(row)
    data["verified"] = bool(data["verified"])
    return Evidence.model_validate(data)


class EvidenceRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(self, evidence: Evidence) -> Evidence:
        self.conn.execute(
            """INSERT INTO evidence
               (id, opportunity_id, evidence_type, source_name, source_url, captured_at, summary,
                raw_excerpt, reliability_score, independence_group, verified, verification_notes,
                collected_by, method)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                evidence.id,
                evidence.opportunity_id,
                evidence.evidence_type,
                evidence.source_name,
                evidence.source_url,
                evidence.captured_at,
                evidence.summary,
                evidence.raw_excerpt,
                evidence.reliability_score,
                evidence.independence_group,
                int(evidence.verified),
                evidence.verification_notes,
                evidence.collected_by,
                evidence.method,
            ),
        )
        self.conn.commit()
        return evidence

    def list_for(self, opportunity_id: str) -> list[Evidence]:
        rows = self.conn.execute(
            "SELECT * FROM evidence WHERE opportunity_id = ? ORDER BY captured_at", (opportunity_id,)
        ).fetchall()
        return [_row_to_model(r) for r in rows]

    def is_duplicate(self, evidence: Evidence) -> bool:
        """Duplicado: misma URL o mismo resumen normalizado para la misma oportunidad."""
        row = self.conn.execute(
            """SELECT id FROM evidence WHERE opportunity_id = ? AND (source_url = ? OR summary = ?) LIMIT 1""",
            (evidence.opportunity_id, evidence.source_url, evidence.summary),
        ).fetchone()
        return row is not None

    def delete_for_opportunity(self, opportunity_id: str) -> int:
        cur = self.conn.execute("DELETE FROM evidence WHERE opportunity_id = ?", (opportunity_id,))
        self.conn.commit()
        return cur.rowcount

    def count_for(self, opportunity_id: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) AS n FROM evidence WHERE opportunity_id = ?", (opportunity_id,)
        ).fetchone()["n"]
