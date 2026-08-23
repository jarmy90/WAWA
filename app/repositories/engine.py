"""Repositorio del motor de operación: estado, transiciones y eventos.

Tablas append-only: ``mode_transitions`` y ``engine_events`` nunca se borran
(requisito de auditoría del sistema).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from app.models.decision_log import _now
from app.models.engine import EngineEvent, EngineSnapshot, ModeTransition
from app.models.enums import EngineState, OperatingMode

DEFAULT_MODE = OperatingMode.development_and_review.value
DEFAULT_STATE = EngineState.researching.value


def _row_to_snapshot(row: sqlite3.Row) -> EngineSnapshot:
    data = dict(row)
    data.pop("id", None)
    data["mode"] = OperatingMode(data["mode"])
    data["engine_state"] = EngineState(data["engine_state"])
    return EngineSnapshot.model_validate(data)


def _row_to_transition(row: sqlite3.Row) -> ModeTransition:
    data = dict(row)
    data["evidence_used"] = json.loads(data.get("evidence_used") or "[]")
    return ModeTransition.model_validate(data)


def _row_to_event(row: sqlite3.Row) -> EngineEvent:
    return EngineEvent.model_validate(dict(row))


class EngineRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ------------------------------------------------------------------
    def ensure_default_row(self) -> None:
        """Crea la fila única de estado si no existe (idempotente)."""
        self.conn.execute(
            """INSERT OR IGNORE INTO engine_state (id, mode, engine_state, updated_at) VALUES (1, ?, ?, ?)""",
            (DEFAULT_MODE, DEFAULT_STATE, _now()),
        )
        self.conn.commit()

    def snapshot(self) -> EngineSnapshot:
        self.ensure_default_row()
        row = self.conn.execute("SELECT * FROM engine_state WHERE id = 1").fetchone()
        return _row_to_snapshot(row)

    def update_snapshot(self, snapshot: EngineSnapshot) -> EngineSnapshot:
        self.conn.execute(
            """UPDATE engine_state SET mode=?, engine_state=?, current_task=?, task_started_at=?,
               last_result=?, next_action=?, heartbeat_at=?, activated_at=?, updated_at=? WHERE id=1""",
            (
                snapshot.mode.value,
                snapshot.engine_state.value,
                snapshot.current_task,
                snapshot.task_started_at,
                snapshot.last_result,
                snapshot.next_action,
                snapshot.heartbeat_at,
                snapshot.activated_at,
                _now(),
            ),
        )
        self.conn.commit()
        return snapshot

    def set_mode(self, mode: OperatingMode) -> None:
        self.conn.execute("UPDATE engine_state SET mode=?, updated_at=? WHERE id=1", (mode.value, _now()))
        self.conn.commit()

    def set_engine_state(self, state: EngineState, *, task: str | None = None) -> None:
        now = _now()
        if task:
            self.conn.execute(
                "UPDATE engine_state SET engine_state=?, current_task=?, task_started_at=?, updated_at=? WHERE id=1",
                (state.value, task, now, now),
            )
        else:
            self.conn.execute(
                "UPDATE engine_state SET engine_state=?, updated_at=? WHERE id=1", (state.value, now)
            )
        self.conn.commit()

    def heartbeat(self, *, task: str | None = None, last_result: str | None = None, next_action: str | None = None) -> None:
        now = _now()
        self.conn.execute(
            """UPDATE engine_state SET heartbeat_at=?, current_task=COALESCE(?, current_task),
               last_result=COALESCE(?, last_result), next_action=COALESCE(?, next_action), updated_at=?
               WHERE id=1""",
            (now, task, last_result, next_action, now),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    def add_transition(self, transition: ModeTransition) -> ModeTransition:
        cur = self.conn.execute(
            """INSERT INTO mode_transitions
               (timestamp, from_mode, to_mode, reason, actor, evidence_used, budget_consumed_usd,
                revenue_usd, decision, rule)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                transition.timestamp,
                transition.from_mode,
                transition.to_mode,
                transition.reason,
                transition.actor,
                json.dumps(transition.evidence_used),
                transition.budget_consumed_usd,
                transition.revenue_usd,
                transition.decision,
                transition.rule,
            ),
        )
        self.conn.commit()
        transition.id = cur.lastrowid
        return transition

    def transitions(self, limit: int = 20) -> list[ModeTransition]:
        rows = self.conn.execute(
            "SELECT * FROM mode_transitions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_transition(r) for r in rows]

    # ------------------------------------------------------------------
    def add_event(self, event: EngineEvent) -> EngineEvent:
        cur = self.conn.execute(
            """INSERT INTO engine_events
               (timestamp, event_type, summary, opportunity_id, engine_state, mode, cost_usd, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.timestamp,
                event.event_type,
                event.summary,
                event.opportunity_id,
                event.engine_state,
                event.mode,
                event.cost_usd,
                event.confidence,
            ),
        )
        self.conn.commit()
        event.id = cur.lastrowid
        return event

    def events(self, limit: int = 20) -> list[EngineEvent]:
        rows = self.conn.execute(
            "SELECT * FROM engine_events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_event(r) for r in rows]

    def event_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS n FROM engine_events").fetchone()["n"]

    def transition_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS n FROM mode_transitions").fetchone()["n"]
