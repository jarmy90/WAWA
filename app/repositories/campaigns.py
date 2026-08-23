"""Repositorio del CampaignRunner Freebuff-first (iteración 006).

Persiste campañas (con presupuestos y límites de embudo inmutables),
transiciones auditadas, sesiones reanudables con sus artefactos, API
Readiness Gates y el log de niveles de razonamiento. JSON para estructuras;
nunca SQL interpolada.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.models.campaign import Campaign, FreebuffSession, new_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CampaignRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ------------------------------------------------------------------ campaigns
    def create_campaign(self, campaign: Campaign) -> dict[str, Any]:
        self.conn.execute(
            """INSERT INTO ff_campaigns
               (id, title, status, stage, discovery_campaign_id, territory_keys, lens_keys,
                archetype_keys, time_budget_hours, api_budget_usd, experiment_budget_usd,
                external_review_slots, maximum_deep_research_candidates, funnel_limits,
                signals_count, concepts_count, concepts_rejected, finalists_count,
                missions_count, evidences_added, sessions_count, is_synthetic,
                closed_reason, next_recommended_action, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                campaign.id,
                campaign.title,
                campaign.status.value,
                campaign.stage.value,
                campaign.discovery_campaign_id,
                json.dumps(campaign.territory_keys, ensure_ascii=False),
                json.dumps(campaign.lens_keys, ensure_ascii=False),
                json.dumps(campaign.archetype_keys, ensure_ascii=False),
                campaign.time_budget_hours,
                campaign.api_budget_usd,
                campaign.experiment_budget_usd,
                campaign.external_review_slots,
                campaign.maximum_deep_research_candidates,
                json.dumps(campaign.funnel_limits, ensure_ascii=False),
                campaign.signals_count,
                campaign.concepts_count,
                campaign.concepts_rejected,
                campaign.finalists_count,
                campaign.missions_count,
                campaign.evidences_added,
                campaign.sessions_count,
                1 if campaign.is_synthetic else 0,
                campaign.closed_reason,
                campaign.next_recommended_action,
                campaign.created_at,
                campaign.updated_at,
            ),
        )
        self.conn.commit()
        return self.get_campaign(campaign.id)  # type: ignore[return-value]

    def get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM ff_campaigns WHERE id = ?", (campaign_id,)).fetchone()
        return self._campaign_row(row) if row else None

    def list_campaigns(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM ff_campaigns ORDER BY created_at DESC").fetchall()
        return [self._campaign_row(r) for r in rows]

    def update_campaign(self, campaign_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {
            "status", "stage", "discovery_campaign_id", "signals_count", "concepts_count",
            "concepts_rejected", "finalists_count", "missions_count", "evidences_added",
            "sessions_count", "closed_reason", "next_recommended_action",
        }
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return self.get_campaign(campaign_id)
        sets["updated_at"] = _now()
        cols = ", ".join(f"{k} = ?" for k in sets)
        self.conn.execute(
            f"UPDATE ff_campaigns SET {cols} WHERE id = ?", (*sets.values(), campaign_id)
        )
        self.conn.commit()
        return self.get_campaign(campaign_id)

    def count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS n FROM ff_campaigns").fetchone()
        return int(row["n"])

    # ------------------------------------------------------------------ transitions
    def add_transition(self, data: dict[str, Any]) -> dict[str, Any]:
        tid = data.get("id") or new_id()
        self.conn.execute(
            """INSERT INTO ff_transitions
               (id, campaign_id, from_stage, to_stage, timestamp, actor, reason,
                inputs_used, outputs_generated, concepts_considered, concepts_rejected,
                costs_recorded, unknowns, errors, next_recommended_action)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                tid,
                data["campaign_id"],
                data["from_stage"],
                data["to_stage"],
                data.get("timestamp", _now()),
                data.get("actor", "system"),
                data.get("reason"),
                json.dumps(data.get("inputs_used", []), ensure_ascii=False),
                json.dumps(data.get("outputs_generated", []), ensure_ascii=False),
                data.get("concepts_considered", 0),
                data.get("concepts_rejected", 0),
                json.dumps(data.get("costs_recorded", {}), ensure_ascii=False),
                json.dumps(data.get("unknowns", []), ensure_ascii=False),
                json.dumps(data.get("errors", []), ensure_ascii=False),
                data.get("next_recommended_action"),
            ),
        )
        self.conn.commit()
        return {"id": tid, **data}

    def transitions_for(self, campaign_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM ff_transitions WHERE campaign_id = ? ORDER BY timestamp DESC LIMIT ?",
            (campaign_id, limit),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for k in ("inputs_used", "outputs_generated", "unknowns", "errors"):
                d[k] = json.loads(d.get(k) or "[]")
            d["costs_recorded"] = json.loads(d.get("costs_recorded") or "{}")
            out.append(d)
        return out

    # ------------------------------------------------------------------ sessions
    def create_session(self, session: FreebuffSession) -> dict[str, Any]:
        self.conn.execute(
            """INSERT INTO ff_sessions
               (id, session_id, campaign_id, status, time_budget_hours, stage_start, stage_end,
                started_at, completed_at, tasks_planned, tasks_completed, tasks_pending,
                concepts_created, concepts_rejected, evidences_added, review_packets_created,
                blockers, errors, next_action, repo_commit, plan_path, state_path, output_path,
                report_path, next_session_path, short_prompt, is_synthetic)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                session.id,
                session.session_id,
                session.campaign_id,
                session.status,
                session.time_budget_hours,
                session.stage_start,
                session.stage_end,
                session.started_at,
                session.completed_at,
                json.dumps(session.tasks_planned, ensure_ascii=False),
                json.dumps(session.tasks_completed, ensure_ascii=False),
                json.dumps(session.tasks_pending, ensure_ascii=False),
                session.concepts_created,
                session.concepts_rejected,
                session.evidences_added,
                session.review_packets_created,
                json.dumps(session.blockers, ensure_ascii=False),
                json.dumps(session.errors, ensure_ascii=False),
                session.next_action,
                session.repo_commit,
                session.plan_path,
                session.state_path,
                session.output_path,
                session.report_path,
                session.next_session_path,
                session.short_prompt,
                1 if session.is_synthetic else 0,
            ),
        )
        self.conn.commit()
        return self.get_session(session.session_id)  # type: ignore[return-value]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM ff_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return self._session_row(row) if row else None

    def sessions_for(self, campaign_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM ff_sessions WHERE campaign_id = ? ORDER BY started_at DESC",
            (campaign_id,),
        ).fetchall()
        return [self._session_row(r) for r in rows]

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM ff_sessions ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._session_row(r) for r in rows]

    def update_session(self, session_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {
            "status", "stage_end", "completed_at", "tasks_planned", "tasks_completed",
            "tasks_pending", "concepts_created", "concepts_rejected", "evidences_added",
            "review_packets_created", "blockers", "errors", "next_action", "repo_commit",
            "plan_path", "state_path", "output_path", "report_path", "next_session_path",
            "short_prompt",
        }
        list_fields = {"tasks_planned", "tasks_completed", "tasks_pending", "blockers", "errors"}
        sets = {}
        for k, v in fields.items():
            if k not in allowed:
                continue
            sets[k] = json.dumps(v, ensure_ascii=False) if k in list_fields else v
        if not sets:
            return self.get_session(session_id)
        cols = ", ".join(f"{k} = ?" for k in sets)
        self.conn.execute(
            f"UPDATE ff_sessions SET {cols} WHERE session_id = ?", (*sets.values(), session_id)
        )
        self.conn.commit()
        return self.get_session(session_id)

    # ------------------------------------------------------------------ readiness
    def save_readiness(self, gate: dict[str, Any]) -> dict[str, Any]:
        gid = gate.get("id") or new_id()
        self.conn.execute(
            """INSERT INTO ff_readiness
               (id, opportunity_id, state, criteria, unknown_criteria, missing, reasoning,
                proposed_daily_limit_usd, estimated_cost_per_call_usd,
                estimated_value_per_call_usd, evaluated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                gid,
                gate["opportunity_id"],
                gate["state"],
                json.dumps(gate.get("criteria", {}), ensure_ascii=False),
                json.dumps(gate.get("unknown_criteria", []), ensure_ascii=False),
                json.dumps(gate.get("missing", []), ensure_ascii=False),
                gate.get("reasoning"),
                gate.get("proposed_daily_limit_usd"),
                gate.get("estimated_cost_per_call_usd"),
                gate.get("estimated_value_per_call_usd"),
                gate.get("evaluated_at", _now()),
            ),
        )
        self.conn.commit()
        return {"id": gid, **gate}

    def readiness_for(self, opportunity_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM ff_readiness WHERE opportunity_id = ? ORDER BY evaluated_at DESC LIMIT 1",
            (opportunity_id,),
        ).fetchone()
        return self._readiness_row(row) if row else None

    def list_readiness(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM ff_readiness ORDER BY evaluated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._readiness_row(r) for r in rows]

    # ------------------------------------------------------------------ reasoning log
    def add_reasoning(self, record: dict[str, Any]) -> dict[str, Any]:
        rid = record.get("id") or new_id()
        self.conn.execute(
            """INSERT INTO ff_reasoning_log (id, campaign_id, session_id, level, action, reason, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                rid,
                record["campaign_id"],
                record.get("session_id"),
                record["level"],
                record["action"],
                record.get("reason"),
                record.get("created_at", _now()),
            ),
        )
        self.conn.commit()
        return {"id": rid, **record}

    def reasoning_for(self, campaign_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM ff_reasoning_log WHERE campaign_id = ? ORDER BY created_at DESC LIMIT ?",
            (campaign_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ mappers
    @staticmethod
    def _campaign_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        for k in ("territory_keys", "lens_keys", "archetype_keys"):
            d[k] = json.loads(d.get(k) or "[]")
        d["funnel_limits"] = json.loads(d.get("funnel_limits") or "{}")
        d["is_synthetic"] = bool(d.get("is_synthetic"))
        return d

    @staticmethod
    def _session_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        for k in ("tasks_planned", "tasks_completed", "tasks_pending", "blockers", "errors"):
            d[k] = json.loads(d.get(k) or "[]")
        d["is_synthetic"] = bool(d.get("is_synthetic"))
        return d

    @staticmethod
    def _readiness_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["criteria"] = json.loads(d.get("criteria") or "{}")
        d["unknown_criteria"] = json.loads(d.get("unknown_criteria") or "[]")
        d["missing"] = json.loads(d.get("missing") or "[]")
        return d
