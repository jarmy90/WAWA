"""Repositorio de evaluaciones (una por oportunidad, se reemplaza al reevaluar)."""
from __future__ import annotations

import json
import sqlite3

from app.models.decision_log import _now
from app.models.enums import Decision
from app.models.evaluation import Evaluation, Estimates, Experiment, RiskItem


def _row_to_model(row: sqlite3.Row) -> Evaluation:
    data = dict(row)
    data["per_criterion"] = json.loads(data.get("per_criterion") or "{}")
    data["assumptions"] = json.loads(data.get("assumptions") or "[]")
    data["blockers"] = json.loads(data.get("blockers") or "[]")
    data["risks"] = [RiskItem.model_validate(r) for r in json.loads(data.get("risks") or "[]")]
    data["estimates"] = Estimates.model_validate(json.loads(data.get("estimates") or "{}"))
    data["experiment"] = Experiment.model_validate(json.loads(data["experiment"])) if data.get("experiment") else None
    data["decision"] = Decision(data["decision"])
    return Evaluation.model_validate(data)


class EvaluationRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert(self, evaluation: Evaluation) -> Evaluation:
        self.conn.execute("DELETE FROM evaluations WHERE opportunity_id = ?", (evaluation.opportunity_id,))
        self.conn.execute(
            """INSERT INTO evaluations
               (opportunity_id, pain_score, demand_score, customer_reach_score, automation_score,
                margin_score, build_speed_score, differentiation_score, safety_score,
                evidence_quality_score, confidence_score, final_score, per_criterion,
                independent_evidence_count, unverified_assumptions_count, assumptions, blockers,
                approval_reason, rejection_reason, decision, model_or_method, skeptic_critique,
                risks, estimates, experiment, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                evaluation.opportunity_id,
                evaluation.pain_score,
                evaluation.demand_score,
                evaluation.customer_reach_score,
                evaluation.automation_score,
                evaluation.margin_score,
                evaluation.build_speed_score,
                evaluation.differentiation_score,
                evaluation.safety_score,
                evaluation.evidence_quality_score,
                evaluation.confidence_score,
                evaluation.final_score,
                json.dumps({k: v.model_dump() for k, v in evaluation.per_criterion.items()}),
                evaluation.independent_evidence_count,
                evaluation.unverified_assumptions_count,
                json.dumps(evaluation.assumptions),
                json.dumps(evaluation.blockers),
                evaluation.approval_reason,
                evaluation.rejection_reason,
                evaluation.decision.value,
                evaluation.model_or_method,
                evaluation.skeptic_critique,
                json.dumps([r.model_dump() for r in evaluation.risks]),
                json.dumps(evaluation.estimates.model_dump()),
                json.dumps(evaluation.experiment.model_dump()) if evaluation.experiment else None,
                evaluation.created_at,
            ),
        )
        self.conn.commit()
        return evaluation

    def get(self, opportunity_id: str) -> Evaluation | None:
        row = self.conn.execute(
            "SELECT * FROM evaluations WHERE opportunity_id = ?", (opportunity_id,)
        ).fetchone()
        return _row_to_model(row) if row else None

    def delete(self, opportunity_id: str) -> None:
        self.conn.execute("DELETE FROM evaluations WHERE opportunity_id = ?", (opportunity_id,))
        self.conn.commit()

    def latest_scores(self) -> dict[str, float]:
        """Mapa opportunity_id -> final_score (para filtros del dashboard)."""
        rows = self.conn.execute("SELECT opportunity_id, final_score FROM evaluations").fetchall()
        return {r["opportunity_id"]: r["final_score"] for r in rows}
