"""Repositorio del Business Discovery Engine (memoria empresarial).

Persiste campañas, conceptos, tests de sustitución, evaluaciones de venture,
comparaciones por pares, learning records y misiones de investigación.
Importes JSON para los campos estructurados (nunca SQL interpolada).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.models.discovery import new_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DiscoveryRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ------------------------------------------------------------------ campaigns
    def create_campaign(self, data: dict[str, Any]) -> dict[str, Any]:
        cid = data.get("id") or new_id()
        now = _now()
        self.conn.execute(
            """INSERT INTO discovery_campaigns
               (id, title, territory_keys, lens_keys, archetype_keys, phase, status,
                phase1_target, shortlist_target, finalists_target, diversity, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                cid,
                data["title"],
                json.dumps(data.get("territory_keys", []), ensure_ascii=False),
                json.dumps(data.get("lens_keys", []), ensure_ascii=False),
                json.dumps(data.get("archetype_keys", []), ensure_ascii=False),
                data.get("phase", "created"),
                data.get("status", "active"),
                data.get("phase1_target", 60),
                data.get("shortlist_target", 10),
                data.get("finalists_target", 3),
                data.get("diversity", 0.0),
                data.get("created_at", now),
                data.get("updated_at", now),
            ),
        )
        self.conn.commit()
        return self.get_campaign(cid)  # type: ignore[return-value]

    def get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM discovery_campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        return self._campaign_row(row) if row else None

    def list_campaigns(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM discovery_campaigns ORDER BY created_at DESC"
        ).fetchall()
        return [self._campaign_row(r) for r in rows]

    def update_campaign(self, campaign_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {"phase", "status", "diversity"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return self.get_campaign(campaign_id)
        sets["updated_at"] = _now()
        cols = ", ".join(f"{k} = ?" for k in sets)
        self.conn.execute(
            f"UPDATE discovery_campaigns SET {cols} WHERE id = ?",
            (*sets.values(), campaign_id),
        )
        self.conn.commit()
        return self.get_campaign(campaign_id)

    # ------------------------------------------------------------------ concepts
    def create_concept(self, data: dict[str, Any]) -> dict[str, Any]:
        cid = data.get("id") or new_id()
        now = _now()
        self.conn.execute(
            """INSERT INTO discovery_concepts
               (id, campaign_id, title, territory_key, lens_keys, archetype_key,
                problem_hypothesis, mechanism, buyer_hypothesis, outcome_hypothesis,
                why_now, general_ai_risk, asset_potential, fingerprint, phase, status,
                source, brief, coherence_ok, coherence_reason, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                cid,
                data["campaign_id"],
                data["title"],
                data.get("territory_key"),
                json.dumps(data.get("lens_keys", []), ensure_ascii=False),
                data.get("archetype_key"),
                data["problem_hypothesis"],
                data["mechanism"],
                data.get("buyer_hypothesis"),
                data.get("outcome_hypothesis"),
                data.get("why_now"),
                data.get("general_ai_risk"),
                data.get("asset_potential"),
                json.dumps(data.get("fingerprint", {}), ensure_ascii=False),
                data.get("phase", "phase1"),
                data.get("status", "GENERATED_HYPOTHESIS"),
                data.get("source", "generated"),
                json.dumps(data.get("brief", {}), ensure_ascii=False),
                1 if data.get("coherence_ok", True) else 0,
                data.get("coherence_reason", ""),
                data.get("created_at", now),
                data.get("updated_at", now),
            ),
        )
        self.conn.commit()
        return self.get_concept(cid)  # type: ignore[return-value]

    def get_concept(self, concept_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM discovery_concepts WHERE id = ?", (concept_id,)
        ).fetchone()
        return self._concept_row(row) if row else None

    def concepts_by_campaign(self, campaign_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM discovery_concepts WHERE campaign_id = ? ORDER BY created_at",
            (campaign_id,),
        ).fetchall()
        return [self._concept_row(r) for r in rows]

    def update_concept(self, concept_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {"phase", "status", "fingerprint", "title", "problem_hypothesis", "mechanism",
                   "brief", "coherence_ok", "coherence_reason"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return self.get_concept(concept_id)
        # El brief se guarda como JSON (columna TEXT).
        if "brief" in sets and not isinstance(sets["brief"], str):
            sets["brief"] = json.dumps(sets["brief"], ensure_ascii=False)
        sets["updated_at"] = _now()
        cols = ", ".join(f"{k} = ?" for k in sets)
        self.conn.execute(
            f"UPDATE discovery_concepts SET {cols} WHERE id = ?",
            (*sets.values(), concept_id),
        )
        self.conn.commit()
        return self.get_concept(concept_id)

    def delete_concepts_by_campaign(self, campaign_id: str) -> None:
        self.conn.execute(
            "DELETE FROM discovery_concepts WHERE campaign_id = ?", (campaign_id,)
        )
        self.conn.commit()

    # ------------------------------------------------------------------ substitution tests
    def save_substitution_test(self, concept_id: str, result: dict[str, Any]) -> dict[str, Any]:
        sid = new_id()
        now = _now()
        self.conn.execute(
            """INSERT INTO substitution_tests
               (id, concept_id, classification, general_ai_resistance, verdict, answers, reasons, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                sid,
                concept_id,
                result["classification"],
                result["general_ai_resistance"],
                result["verdict"],
                json.dumps(result.get("answers", {}), ensure_ascii=False),
                json.dumps(result.get("reasons", []), ensure_ascii=False),
                now,
            ),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM substitution_tests WHERE id = ?", (sid,)
        ).fetchone()
        return self._substitution_row(row)  # type: ignore[return-value]

    def substitution_tests_by_concept(self, concept_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM substitution_tests WHERE concept_id = ? ORDER BY created_at DESC",
            (concept_id,),
        ).fetchall()
        return [self._substitution_row(r) for r in rows]

    # ------------------------------------------------------------------ venture evaluations
    def save_venture_evaluation(self, concept_id: str, data: dict[str, Any]) -> dict[str, Any]:
        vid = new_id()
        now = _now()
        self.conn.execute(
            """INSERT INTO venture_evaluations
               (id, concept_id, scores, final_score, structural_concept_score,
                evidence_backed_venture_score, has_verified_evidence,
                novelty_score, utility_score, blockers, labels, rationale, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                vid,
                concept_id,
                json.dumps(data.get("scores", {}), ensure_ascii=False),
                data.get("final_score", 0.0),
                data.get("structural_concept_score", data.get("final_score", 0.0)),
                data.get("evidence_backed_venture_score", 0.0),
                1 if data.get("has_verified_evidence") else 0,
                data.get("novelty_score", 0.0),
                data.get("utility_score", 0.0),
                json.dumps(data.get("blockers", []), ensure_ascii=False),
                json.dumps(data.get("labels", []), ensure_ascii=False),
                json.dumps(data.get("rationale", {}), ensure_ascii=False),
                now,
            ),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM venture_evaluations WHERE id = ?", (vid,)
        ).fetchone()
        return self._venture_row(row)  # type: ignore[return-value]

    def venture_evaluations_by_concept(self, concept_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM venture_evaluations WHERE concept_id = ? ORDER BY created_at DESC",
            (concept_id,),
        ).fetchall()
        return [self._venture_row(r) for r in rows]

    # ------------------------------------------------------------------ comparisons
    def save_comparison(self, data: dict[str, Any]) -> dict[str, Any]:
        cid = new_id()
        self.conn.execute(
            """INSERT INTO concept_comparisons
               (id, campaign_id, winner_id, loser_id, winner_score, loser_score, criteria, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                cid,
                data["campaign_id"],
                data["winner_id"],
                data["loser_id"],
                data.get("winner_score", 0.0),
                data.get("loser_score", 0.0),
                json.dumps(data.get("criteria", {}), ensure_ascii=False),
                _now(),
            ),
        )
        self.conn.commit()
        return {"id": cid, **data}

    def comparisons_by_campaign(self, campaign_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM concept_comparisons WHERE campaign_id = ? ORDER BY created_at",
            (campaign_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["criteria"] = json.loads(d.get("criteria") or "{}")
            out.append(d)
        return out

    # ------------------------------------------------------------------ learning records
    def add_learning_record(self, kind: str, pattern: str, source: str, notes: str | None = None) -> dict[str, Any]:
        lid = new_id()
        self.conn.execute(
            "INSERT INTO learning_records (id, kind, pattern, source, notes, created_at) VALUES (?,?,?,?,?,?)",
            (lid, kind, pattern, source, notes, _now()),
        )
        self.conn.commit()
        return {"id": lid, "kind": kind, "pattern": pattern, "source": source, "notes": notes}

    def list_learning_records(self, kind: str | None = None) -> list[dict[str, Any]]:
        if kind:
            rows = self.conn.execute(
                "SELECT * FROM learning_records WHERE kind = ? ORDER BY created_at DESC", (kind,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM learning_records ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ missions
    def save_mission(self, mission: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        self.conn.execute(
            """INSERT INTO research_missions (id, mission_id, kind, target, export_payload, status, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                mission.get("id") or new_id(),
                mission["mission_id"],
                mission["kind"],
                json.dumps(mission.get("target", {}), ensure_ascii=False),
                json.dumps(mission.get("export_payload", {}), ensure_ascii=False),
                mission.get("status", "exported"),
                now,
            ),
        )
        self.conn.commit()
        return self.get_mission(mission["mission_id"])  # type: ignore[return-value]

    def get_mission(self, mission_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM research_missions WHERE mission_id = ?", (mission_id,)
        ).fetchone()
        return self._mission_row(row) if row else None

    def list_missions(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM research_missions WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM research_missions ORDER BY created_at DESC").fetchall()
        return [self._mission_row(r) for r in rows]

    def mark_mission_imported(self, mission_id: str) -> None:
        self.conn.execute(
            "UPDATE research_missions SET status = 'imported', imported_at = ? WHERE mission_id = ?",
            (_now(), mission_id),
        )
        self.conn.commit()

    def update_mission_status(self, mission_id: str, status: str) -> None:
        self.conn.execute(
            "UPDATE research_missions SET status = ? WHERE mission_id = ?", (status, mission_id)
        )
        self.conn.commit()

    def missions_by_campaign(self, campaign_id: str) -> list[dict[str, Any]]:
        """Misiones cuyo target referencia esta campaña (iteración 013)."""
        rows = self.conn.execute(
            "SELECT * FROM research_missions ORDER BY created_at DESC"
        ).fetchall()
        out = []
        for r in rows:
            d = self._mission_row(r)
            if (d.get("target") or {}).get("campaign_id") == campaign_id:
                out.append(d)
        return out

    def save_mission_result(self, mission_id: str, result: dict[str, Any]) -> dict[str, Any]:
        rid = new_id()
        self.conn.execute(
            """INSERT INTO mission_results (id, mission_id, raw, evidences, competitors, buyer_confirmed, verified, verification_notes, imported_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                rid,
                mission_id,
                json.dumps(result.get("raw", {}), ensure_ascii=False),
                json.dumps(result.get("evidences", []), ensure_ascii=False),
                json.dumps(result.get("competitors", []), ensure_ascii=False),
                json.dumps(result.get("buyer_confirmed"), ensure_ascii=False) if result.get("buyer_confirmed") else None,
                1 if result.get("verified") else 0,
                result.get("verification_notes"),
                _now(),
            ),
        )
        self.conn.commit()
        return {"id": rid, "mission_id": mission_id, **result}

    def mission_results(self, mission_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM mission_results WHERE mission_id = ? ORDER BY imported_at", (mission_id,)
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["evidences"] = json.loads(d.get("evidences") or "[]")
            d["competitors"] = json.loads(d.get("competitors") or "[]")
            d["buyer_confirmed"] = json.loads(d["buyer_confirmed"]) if d.get("buyer_confirmed") else None
            out.append(d)
        return out

    # ------------------------------------------------------------------ row mappers
    @staticmethod
    def _campaign_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        for k in ("territory_keys", "lens_keys", "archetype_keys"):
            d[k] = json.loads(d.get(k) or "[]")
        return d

    @staticmethod
    def _concept_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["lens_keys"] = json.loads(d.get("lens_keys") or "[]")
        d["fingerprint"] = json.loads(d.get("fingerprint") or "{}")
        d["brief"] = json.loads(d.get("brief") or "{}")
        return d

    @staticmethod
    def _substitution_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["answers"] = json.loads(d.get("answers") or "{}")
        d["reasons"] = json.loads(d.get("reasons") or "[]")
        return d

    @staticmethod
    def _venture_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["scores"] = json.loads(d.get("scores") or "{}")
        d["blockers"] = json.loads(d.get("blockers") or "[]")
        d["labels"] = json.loads(d.get("labels") or "[]")
        d["rationale"] = json.loads(d.get("rationale") or "{}")
        d["structural_concept_score"] = float(d.get("structural_concept_score") or 0.0)
        d["evidence_backed_venture_score"] = float(d.get("evidence_backed_venture_score") or 0.0)
        d["has_verified_evidence"] = bool(d.get("has_verified_evidence"))
        return d

    @staticmethod
    def _mission_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["target"] = json.loads(d.get("target") or "{}")
        d["export_payload"] = json.loads(d.get("export_payload") or "{}")
        return d
