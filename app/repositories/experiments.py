"""Repositorio de experimentos."""
from __future__ import annotations

import sqlite3

from app.models.evaluation import Experiment


def _row_to_model(row: sqlite3.Row) -> Experiment:
    return Experiment.model_validate(dict(row))


class ExperimentRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert(self, experiment: Experiment) -> Experiment:
        self.conn.execute("DELETE FROM experiments WHERE opportunity_id = ?", (experiment.opportunity_id,))
        self.conn.execute(
            """INSERT INTO experiments
               (id, opportunity_id, hypothesis, cheapest_test, maximum_budget, success_metric,
                success_threshold, failure_threshold, duration, status, result)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                experiment.id,
                experiment.opportunity_id,
                experiment.hypothesis,
                experiment.cheapest_test,
                experiment.maximum_budget,
                experiment.success_metric,
                experiment.success_threshold,
                experiment.failure_threshold,
                experiment.duration,
                experiment.status,
                experiment.result,
            ),
        )
        self.conn.commit()
        return experiment

    def get_for(self, opportunity_id: str) -> Experiment | None:
        row = self.conn.execute(
            "SELECT * FROM experiments WHERE opportunity_id = ?", (opportunity_id,)
        ).fetchone()
        return _row_to_model(row) if row else None

    def delete_for(self, opportunity_id: str) -> None:
        self.conn.execute("DELETE FROM experiments WHERE opportunity_id = ?", (opportunity_id,))
        self.conn.commit()
