"""Repositorio de oportunidades."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.models.enums import OpportunityStatus
from app.models.opportunity import Opportunity


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_model(row: sqlite3.Row) -> Opportunity:
    return Opportunity.model_validate(dict(row))


class OpportunityRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(self, opportunity: Opportunity) -> Opportunity:
        self.conn.execute(
            """INSERT INTO opportunities
               (id, title, problem, proposed_solution, target_customer, sector, status, source, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                opportunity.id,
                opportunity.title,
                opportunity.problem,
                opportunity.proposed_solution,
                opportunity.target_customer,
                opportunity.sector,
                opportunity.status.value,
                opportunity.source,
                opportunity.created_at,
                opportunity.updated_at,
            ),
        )
        self.conn.commit()
        return opportunity

    def get(self, opportunity_id: str) -> Opportunity | None:
        row = self.conn.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
        return _row_to_model(row) if row else None

    def update(self, opportunity: Opportunity) -> Opportunity:
        opportunity.updated_at = _now()
        self.conn.execute(
            """UPDATE opportunities SET title=?, problem=?, proposed_solution=?, target_customer=?,
               sector=?, status=?, updated_at=? WHERE id=?""",
            (
                opportunity.title,
                opportunity.problem,
                opportunity.proposed_solution,
                opportunity.target_customer,
                opportunity.sector,
                opportunity.status.value,
                opportunity.updated_at,
                opportunity.id,
            ),
        )
        self.conn.commit()
        return opportunity

    def set_status(self, opportunity_id: str, status: OpportunityStatus) -> None:
        self.conn.execute(
            "UPDATE opportunities SET status=?, updated_at=? WHERE id=?",
            (status.value, _now(), opportunity_id),
        )
        self.conn.commit()

    def list(self, *, status: OpportunityStatus | None = None) -> list[Opportunity]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM opportunities WHERE status = ? ORDER BY created_at DESC", (status.value,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM opportunities ORDER BY created_at DESC").fetchall()
        return [_row_to_model(r) for r in rows]

    def get_by_concept(self, concept_id: str) -> Opportunity | None:
        """Localiza la oportunidad promovida para un concepto (mismo título
        normalizado dentro de la misma campaña de discovery).

        El vínculo concepto→oportunidad se resuelve por título porque las
        oportunidades promovidas copian el título del concepto; nunca se
        insertan identificadores foráneos en esta dirección.
        """
        row = self.conn.execute(
            "SELECT title, campaign_id FROM discovery_concepts WHERE id = ?", (concept_id,)
        ).fetchone()
        if row is None:
            return None
        title, campaign_id = row["title"], row["campaign_id"]
        norm = _normalize(title)
        rows = self.conn.execute("SELECT * FROM opportunities").fetchall()
        for o in (_row_to_model(r) for r in rows):
            if _normalize(o.title) == norm and o.source == f"discovery:{campaign_id}":
                return o
        return None

    def find_similar_title(self, title: str) -> list[Opportunity]:
        """Detección simple de duplicados por título normalizado."""
        norm = _normalize(title)
        rows = self.conn.execute("SELECT * FROM opportunities").fetchall()
        return [o for o in (_row_to_model(r) for r in rows) if _normalize(o.title) == norm]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS n FROM opportunities").fetchone()["n"]

    def delete(self, opportunity_id: str) -> None:
        self.conn.execute("DELETE FROM opportunities WHERE id = ?", (opportunity_id,))
        self.conn.commit()


def _normalize(text: str) -> str:
    import re
    import unicodedata

    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()
