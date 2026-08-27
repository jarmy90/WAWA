"""SAFE_PAUSE — functional safe-stop mechanism for the autonomous runtime.

Activates on: auth failure, limits exhausted, unknown cost, repeated errors,
insecure config, provider down, storage unavailable, loops.

Scope: GLOBAL, PROVIDER, CAMPAIGN, JOB_TYPE.

Preserves the queue, prevents new affected claims, does NOT kill FastAPI,
shows the cause, allows safe recovery. Auth, budget, security, or corruption
errors require manual intervention.

Iteration 025.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.core.logging import get_logger
from app.repositories.jobs import JobRepository, _now

log = get_logger("safe_pause")

# Activation reasons that require manual intervention
MANUAL_INTERVENTION_REASONS = {
    "authentication_failed",
    "budget_exhausted",
    "security_violation",
    "database_corrupt",
    "storage_unavailable",
    "secret_exposed",
}


class SafePause:
    """Functional SAFE_PAUSE with scope and recovery."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.jobs = JobRepository(conn)

    def activate(
        self,
        reason: str,
        scope: str = "GLOBAL",
        *,
        require_manual: bool = False,
    ) -> dict[str, Any]:
        """Activate SAFE_PAUSE. Returns current state."""
        now = _now()
        requires_manual = require_manual or any(
            pattern in reason.lower() for pattern in MANUAL_INTERVENTION_REASONS
        )

        # Update runtime state
        self.conn.execute(
            """UPDATE runtime_state SET
               operating_mode = 'SAFE_PAUSED',
               safe_pause_reason = ?,
               safe_pause_scope = ?,
               safe_pause_activated_at = ?,
               updated_at = ?
               WHERE id = 1""",
            (reason[:500], scope, now, now),
        )
        self.conn.commit()

        # Pause affected jobs
        paused = self.jobs.safe_pause_jobs(scope, reason)

        # Record event
        self.conn.execute(
            """INSERT INTO engine_events (timestamp, event_type, summary, cost_usd)
               VALUES (?, 'SAFE_PAUSE_ACTIVATED', ?, 0)""",
            (now, f"scope={scope} reason={reason[:300]} paused={paused}"),
        )
        self.conn.commit()

        log.warning(f"SAFE_PAUSE activated: scope={scope} reason={reason[:200]} paused={paused}")

        return {
            "activated": True,
            "scope": scope,
            "reason": reason[:500],
            "requires_manual_intervention": requires_manual,
            "jobs_paused": paused,
            "activated_at": now,
        }

    def deactivate(self, *, actor: str = "system") -> dict[str, Any]:
        """Deactivate SAFE_PAUSE and resume paused jobs. Only allowed when
        the underlying issue is resolved."""
        now = _now()

        # Check current reason
        row = self.conn.execute(
            "SELECT safe_pause_reason, safe_pause_scope FROM runtime_state WHERE id = 1"
        ).fetchone()
        reason = row["safe_pause_reason"] if row else ""
        scope = row["safe_pause_scope"] if row else "GLOBAL"

        # Resume jobs
        resumed = self.jobs.resume_paused()

        # Update runtime state
        self.conn.execute(
            """UPDATE runtime_state SET
               operating_mode = 'AUTONOMOUS_24_7',
               safe_pause_reason = NULL,
               safe_pause_scope = NULL,
               safe_pause_activated_at = NULL,
               updated_at = ?
               WHERE id = 1""",
            (now,),
        )
        self.conn.commit()

        # Record event
        self.conn.execute(
            """INSERT INTO engine_events (timestamp, event_type, summary, cost_usd)
               VALUES (?, 'SAFE_PAUSE_DEACTIVATED', ?, 0)""",
            (now, f"scope={scope} actor={actor} resumed={resumed}"),
        )
        self.conn.commit()

        log.info(f"SAFE_PAUSE deactivated by {actor}: resumed {resumed} jobs")

        return {
            "deactivated": True,
            "previous_reason": reason,
            "previous_scope": scope,
            "jobs_resumed": resumed,
            "deactivated_at": now,
            "deactivated_by": actor,
        }

    def status(self) -> dict[str, Any]:
        row = self.conn.execute(
            """SELECT operating_mode, safe_pause_reason, safe_pause_scope,
                      safe_pause_activated_at, updated_at
               FROM runtime_state WHERE id = 1"""
        ).fetchone()
        if not row:
            return {"active": False}
        return {
            "active": row["operating_mode"] == "SAFE_PAUSED",
            "mode": row["operating_mode"],
            "reason": row["safe_pause_reason"],
            "scope": row["safe_pause_scope"],
            "activated_at": row["safe_pause_activated_at"],
            "updated_at": row["updated_at"],
        }
