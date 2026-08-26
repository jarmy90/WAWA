"""Repositorio del comité de contraste (revisiones externas).

Persiste la cola de revisión, las revisiones importadas (raw + parsed) y las
síntesis. Campos JSON para estructuras; nunca SQL interpolada. Las revisiones
son DATOS: se conserva siempre la respuesta original.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.models.external_review import ExternalReview, ReviewSynthesis, new_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReviewRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ------------------------------------------------------------------ queue
    def queue_item(self, opportunity_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM review_queue WHERE opportunity_id = ?", (opportunity_id,)
        ).fetchone()
        return dict(row) if row else None

    def enqueue(
        self,
        opportunity_id: str,
        *,
        internal_score: float,
        window_deadline: str,
        review_required: bool = False,
        note: str | None = None,
    ) -> dict[str, Any]:
        now = _now()
        self.conn.execute(
            """INSERT INTO review_queue
               (opportunity_id, internal_score, queued_at, window_deadline, status,
                review_required, reviewed_without_external, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,0,?,?,?)""",
            (
                opportunity_id,
                internal_score,
                now,
                window_deadline,
                "pending",
                1 if review_required else 0,
                note or "",
                now,
                now,
            ),
        )
        self.conn.commit()
        return self.queue_item(opportunity_id)  # type: ignore[return-value]

    def list_queue(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM review_queue WHERE status = ? ORDER BY queued_at DESC", (status,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM review_queue ORDER BY queued_at DESC").fetchall()
        return [dict(r) for r in rows]

    def count_queued_since(self, since_iso: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM review_queue WHERE queued_at >= ?", (since_iso,)
        ).fetchone()
        return int(row["n"])

    def update_queue(self, opportunity_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {"status", "review_required", "reviewed_without_external", "notes"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return self.queue_item(opportunity_id)
        sets["updated_at"] = _now()
        cols = ", ".join(f"{k} = ?" for k in sets)
        self.conn.execute(
            f"UPDATE review_queue SET {cols} WHERE opportunity_id = ?",
            (*sets.values(), opportunity_id),
        )
        self.conn.commit()
        return self.queue_item(opportunity_id)

    def delete_queue_item(self, opportunity_id: str) -> None:
        self.conn.execute("DELETE FROM review_queue WHERE opportunity_id = ?", (opportunity_id,))
        self.conn.commit()

    # ------------------------------------------------------------------ reviews
    def create_review(self, review: ExternalReview) -> dict[str, Any]:
        self.conn.execute(
            """INSERT INTO external_reviews
               (id, opportunity_id, provider, model, model_version, execution_mode,
                review_date, raw_response, parsed_response, recommendation, confidence,
                strongest_evidence, weakest_assumption, missing_evidence, primary_risk,
                suggested_improvement, cheaper_experiment, kill_condition, cost, status,
                parse_errors, imported_by, file_hash, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                review.id,
                review.opportunity_id,
                review.provider,
                review.model,
                review.model_version,
                review.execution_mode,
                review.review_date,
                review.raw_response,
                json.dumps(review.parsed_response, ensure_ascii=False),
                review.recommendation,
                review.confidence,
                review.strongest_evidence,
                review.weakest_assumption,
                review.missing_evidence,
                review.primary_risk,
                review.suggested_improvement,
                review.cheaper_experiment,
                review.kill_condition,
                review.cost,
                review.status,
                json.dumps(review.parse_errors, ensure_ascii=False),
                review.imported_by,
                review.file_hash,
                review.created_at,
            ),
        )
        self.conn.commit()
        return self.get_review(review.id)  # type: ignore[return-value]

    def get_review(self, review_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM external_reviews WHERE id = ?", (review_id,)
        ).fetchone()
        return self._review_row(row) if row else None

    def reviews_for(self, opportunity_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM external_reviews WHERE opportunity_id = ? ORDER BY created_at DESC",
            (opportunity_id,),
        ).fetchall()
        return [self._review_row(r) for r in rows]

    def find_by_hash(self, opportunity_id: str, file_hash: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM external_reviews WHERE opportunity_id = ? AND file_hash = ?",
            (opportunity_id, file_hash),
        ).fetchone()
        return self._review_row(row) if row else None

    def update_review(self, review_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {"status", "parsed_response", "recommendation", "confidence", "parse_errors"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return self.get_review(review_id)
        cols = ", ".join(f"{k} = ?" for k in sets)
        self.conn.execute(
            f"UPDATE external_reviews SET {cols} WHERE id = ?",
            (*sets.values(), review_id),
        )
        self.conn.commit()
        return self.get_review(review_id)

    def list_reviews(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM external_reviews ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._review_row(r) for r in rows]

    # ------------------------------------------------------------------ synthesis
    def save_synthesis(self, synthesis: ReviewSynthesis) -> dict[str, Any]:
        self.conn.execute(
            """INSERT OR REPLACE INTO review_syntheses
               (opportunity_id, reviews_count, valid_reviews_count, consensus_level,
                recommendation_distribution, average_confidence, agreements, disagreements,
                unique_risks, repeated_risks, missing_evidence, recommended_next_action,
                internal_score_before, internal_score_after, score_change_reason, generated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                synthesis.opportunity_id,
                synthesis.reviews_count,
                synthesis.valid_reviews_count,
                synthesis.consensus_level,
                json.dumps(synthesis.recommendation_distribution, ensure_ascii=False),
                synthesis.average_confidence,
                json.dumps(synthesis.agreements, ensure_ascii=False),
                json.dumps(synthesis.disagreements, ensure_ascii=False),
                json.dumps(synthesis.unique_risks, ensure_ascii=False),
                json.dumps(synthesis.repeated_risks, ensure_ascii=False),
                json.dumps(synthesis.missing_evidence, ensure_ascii=False),
                synthesis.recommended_next_action,
                synthesis.internal_score_before,
                synthesis.internal_score_after,
                synthesis.score_change_reason,
                synthesis.generated_at,
            ),
        )
        self.conn.commit()
        return self.get_synthesis(synthesis.opportunity_id)  # type: ignore[return-value]

    def get_synthesis(self, opportunity_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM review_syntheses WHERE opportunity_id = ?", (opportunity_id,)
        ).fetchone()
        return self._synthesis_row(row) if row else None

    def list_syntheses(self, limit: int = 50) -> list[dict[str, Any]]:
        """Lista síntesis persistidas, separadas de las revisiones externas."""
        rows = self.conn.execute(
            "SELECT * FROM review_syntheses ORDER BY generated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._synthesis_row(row) for row in rows]

    def delete_synthesis(self, opportunity_id: str) -> None:
        self.conn.execute("DELETE FROM review_syntheses WHERE opportunity_id = ?", (opportunity_id,))
        self.conn.commit()

    # ------------------------------------------------------------------ mappers
    @staticmethod
    def _review_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["parsed_response"] = json.loads(d.get("parsed_response") or "{}")
        d["parse_errors"] = json.loads(d.get("parse_errors") or "[]")
        return d

    @staticmethod
    def _synthesis_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        for k in ("agreements", "disagreements", "unique_risks", "repeated_risks", "missing_evidence"):
            d[k] = json.loads(d.get(k) or "[]")
        d["recommendation_distribution"] = json.loads(d.get("recommendation_distribution") or "{}")
        return d
