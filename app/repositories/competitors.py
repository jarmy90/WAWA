"""Repositorio de competidores."""
from __future__ import annotations

import sqlite3

from app.models.evidence import Competitor


def _row_to_model(row: sqlite3.Row) -> Competitor:
    return Competitor.model_validate(dict(row))


class CompetitorRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(self, competitor: Competitor) -> Competitor:
        self.conn.execute(
            """INSERT INTO competitors
               (id, opportunity_id, name, url, offer, observed_price, strengths, weaknesses, evidence_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                competitor.id,
                competitor.opportunity_id,
                competitor.name,
                competitor.url,
                competitor.offer,
                competitor.observed_price,
                competitor.strengths,
                competitor.weaknesses,
                competitor.evidence_id,
            ),
        )
        self.conn.commit()
        return competitor

    def list_for(self, opportunity_id: str) -> list[Competitor]:
        rows = self.conn.execute(
            "SELECT * FROM competitors WHERE opportunity_id = ? ORDER BY name", (opportunity_id,)
        ).fetchall()
        return [_row_to_model(r) for r in rows]

    def delete_for_opportunity(self, opportunity_id: str) -> int:
        cur = self.conn.execute("DELETE FROM competitors WHERE opportunity_id = ?", (opportunity_id,))
        self.conn.commit()
        return cur.rowcount
