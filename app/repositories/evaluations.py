"""Repositorio append-only de evaluaciones versionadas."""
from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from app.models.enums import Decision
from app.models.evaluation import Evaluation, Estimates, Experiment, RiskItem

_META = ("evaluation_id", "version", "integrity_status", "supersedes_id", "campaign_id", "mission_id", "prompt_version", "execution_mode", "provider", "provenance", "invalidated_at")


def _row_to_model(row: sqlite3.Row) -> Evaluation:
    data = dict(row)
    for key in _META:
        data.pop(key, None)
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
        columns = {row[1] for row in conn.execute("PRAGMA table_info(evaluations)").fetchall()}
        if "integrity_status" not in columns:
            conn.execute("ALTER TABLE evaluations ADD COLUMN integrity_status TEXT NOT NULL DEFAULT 'VALID'")
            conn.commit()

    def upsert(self, evaluation: Evaluation) -> Evaluation:
        """Inserta una versión nueva; nunca elimina historial."""
        previous = self.conn.execute(
            "SELECT evaluation_id, version FROM evaluations WHERE opportunity_id = ? ORDER BY version DESC LIMIT 1",
            (evaluation.opportunity_id,),
        ).fetchone()
        evaluation_id = evaluation.evaluation_id or uuid.uuid4().hex
        version = max(int(evaluation.version or 1), int(previous["version"] + 1) if previous else 1)
        supersedes = evaluation.supersedes_id or (previous["evaluation_id"] if previous else None)
        columns = """evaluation_id, opportunity_id, version, supersedes_id, campaign_id, mission_id,
            prompt_version, execution_mode, provider, provenance, invalidated_at,
            pain_score, demand_score, customer_reach_score, automation_score, margin_score,
            build_speed_score, differentiation_score, safety_score, evidence_quality_score,
            confidence_score, final_score, per_criterion, independent_evidence_count,
            unverified_assumptions_count, assumptions, blockers, approval_reason, rejection_reason,
            decision, model_or_method, skeptic_critique, risks, estimates, experiment, created_at,
            integrity_status"""
        values = (
            evaluation_id, evaluation.opportunity_id, version, supersedes, evaluation.campaign_id,
            evaluation.mission_id, getattr(evaluation, "prompt_version", None), evaluation.execution_mode,
            evaluation.provider, json.dumps(evaluation.provenance), evaluation.invalidated_at,
            evaluation.pain_score, evaluation.demand_score, evaluation.customer_reach_score,
            evaluation.automation_score, evaluation.margin_score, evaluation.build_speed_score,
            evaluation.differentiation_score, evaluation.safety_score, evaluation.evidence_quality_score,
            evaluation.confidence_score, evaluation.final_score,
            json.dumps({k: v.model_dump() for k, v in evaluation.per_criterion.items()}),
            evaluation.independent_evidence_count, evaluation.unverified_assumptions_count,
            json.dumps(evaluation.assumptions), json.dumps(evaluation.blockers), evaluation.approval_reason,
            evaluation.rejection_reason, evaluation.decision.value, evaluation.model_or_method,
            evaluation.skeptic_critique, json.dumps([r.model_dump() for r in evaluation.risks]),
            json.dumps(evaluation.estimates.model_dump()),
            json.dumps(evaluation.experiment.model_dump()) if evaluation.experiment else None,
            evaluation.created_at, evaluation.integrity_status,
        )
        self.conn.execute(f"INSERT INTO evaluations ({columns}) VALUES ({','.join('?' for _ in values)})", values)
        self.conn.commit()
        return evaluation.model_copy(update={"evaluation_id": evaluation_id, "version": version, "supersedes_id": supersedes})

    def get(self, opportunity_id: str) -> Evaluation | None:
        row = self.conn.execute(
            "SELECT * FROM evaluations WHERE opportunity_id = ? AND integrity_status = 'VALID' ORDER BY version DESC LIMIT 1",
            (opportunity_id,),
        ).fetchone()
        return _row_to_model(row) if row else None

    def history(self, opportunity_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM evaluations WHERE opportunity_id = ? ORDER BY version", (opportunity_id,)).fetchall()]

    def quarantine(self, opportunity_id: str, reason: str) -> None:
        self.conn.execute("UPDATE evaluations SET integrity_status = 'QUARANTINED', invalidated_at = ?, rejection_reason = ? WHERE opportunity_id = ? AND integrity_status != 'QUARANTINED'", (__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(), f"QUARANTINED: {reason}", opportunity_id))
        self.conn.commit()

    def integrity_status(self, opportunity_id: str) -> str | None:
        row = self.conn.execute("SELECT integrity_status FROM evaluations WHERE opportunity_id = ? ORDER BY version DESC LIMIT 1", (opportunity_id,)).fetchone()
        return row["integrity_status"] if row else None

    def delete(self, opportunity_id: str) -> None:
        raise RuntimeError("Evaluaciones append-only: no se permite borrar historial")

    def latest_scores(self) -> dict[str, float]:
        rows = self.conn.execute("SELECT opportunity_id, final_score FROM evaluations WHERE integrity_status = 'VALID' AND version = (SELECT MAX(e2.version) FROM evaluations e2 WHERE e2.opportunity_id = evaluations.opportunity_id AND e2.integrity_status = 'VALID')").fetchall()
        return {r["opportunity_id"]: r["final_score"] for r in rows}
