"""Job Queue repository — SQLite-backed persistent queue for autonomous runtime.

Supports atomic claim (SELECT ... FOR UPDATE style via SQLite locking),
lease expiry recovery, priorities, retry backoff, idempotency, and audit.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any

JOB_SCHEMA = """
-- Cola de jobs persistente (iteración 025): sobrevive reinicios, soporta
-- leases, prioridades, reintentos e idempotencia.
CREATE TABLE IF NOT EXISTS job_queue (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    priority INTEGER NOT NULL DEFAULT 2,
    payload TEXT NOT NULL DEFAULT '{}',
    idempotency_key TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    scheduled_at TEXT NOT NULL,
    claimed_at TEXT,
    lease_expires_at TEXT,
    next_retry_at TEXT,
    completed_at TEXT,
    provider TEXT,
    model TEXT,
    purpose TEXT,
    parent_job_id TEXT,
    result_reference TEXT,
    normalized_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobq_status ON job_queue(status);
CREATE INDEX IF NOT EXISTS idx_jobq_scheduled ON job_queue(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_jobq_priority ON job_queue(priority, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_jobq_type ON job_queue(job_type);
CREATE INDEX IF NOT EXISTS idx_jobq_idempotency ON job_queue(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_jobq_parent ON job_queue(parent_job_id);

-- Runtime state persistente (iteración 025): singleton con estado del
-- scheduler, worker, OmniRoute, circuit breaker, usage counters.
CREATE TABLE IF NOT EXISTS runtime_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    operating_mode TEXT NOT NULL DEFAULT 'OFFLINE',
    scheduler_running INTEGER NOT NULL DEFAULT 0,
    worker_running INTEGER NOT NULL DEFAULT 0,
    omniroute_available INTEGER NOT NULL DEFAULT 0,
    omniroute_last_heartbeat TEXT,
    circuit_breaker_state TEXT NOT NULL DEFAULT 'CLOSED',
    circuit_breaker_failures INTEGER NOT NULL DEFAULT 0,
    circuit_breaker_last_trip TEXT,
    requests_today INTEGER NOT NULL DEFAULT 0,
    tokens_today INTEGER NOT NULL DEFAULT 0,
    cost_today_usd REAL NOT NULL DEFAULT 0.0,
    daily_request_limit INTEGER NOT NULL DEFAULT 500,
    daily_token_limit INTEGER NOT NULL DEFAULT 150000,
    daily_cost_limit_usd REAL NOT NULL DEFAULT 0.0,
    last_job_completed TEXT,
    last_error TEXT,
    safe_pause_reason TEXT,
    safe_pause_scope TEXT,
    safe_pause_activated_at TEXT,
    updated_at TEXT NOT NULL
);

-- Approval queue (iteración 025): aprobaciones del propietario para
-- acciones irreversibles. Append-only, expirable, auditada.
CREATE TABLE IF NOT EXISTS owner_approvals (
    id TEXT PRIMARY KEY,
    approval_type TEXT NOT NULL,
    job_id TEXT,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    requested_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by TEXT,
    decision TEXT,
    decision_notes TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_approval_status ON owner_approvals(status);
CREATE INDEX IF NOT EXISTS idx_approval_type ON owner_approvals(approval_type);
"""


class JobRepository:
    """CRUD y cola persistente para jobs del runtime autónomo."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # -- Create ----------------------------------------------------------
    def create_job(
        self,
        *,
        job_type: str,
        payload: dict[str, Any] | None = None,
        priority: int = 2,
        idempotency_key: str = "",
        scheduled_at: str = "",
        max_attempts: int = 3,
        provider: str | None = None,
        model: str | None = None,
        purpose: str | None = None,
        parent_job_id: str | None = None,
    ) -> dict[str, Any]:
        now = _now()
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        scheduled = scheduled_at or now
        self.conn.execute(
            """INSERT INTO job_queue
               (job_id, job_type, status, priority, payload, idempotency_key,
                attempts, max_attempts, scheduled_at, provider, model, purpose,
                parent_job_id, created_at, updated_at)
               VALUES (?,?,'PENDING',?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                job_id, job_type, priority, json.dumps(payload or {}),
                idempotency_key, 0, max_attempts, scheduled,
                provider, model, purpose, parent_job_id, now, now,
            ),
        )
        self.conn.commit()
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM job_queue WHERE job_id = ?", (job_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None

    # -- Idempotent enqueue ----------------------------------------------
    def enqueue_if_new(
        self, *, job_type: str, idempotency_key: str,
        payload: dict[str, Any] | None = None, priority: int = 2,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Encola SOLO si no existe un job con el mismo idempotency_key en
        estado terminal o pendiente. Devuelve el job existente o el nuevo."""
        if idempotency_key:
            row = self.conn.execute(
                """SELECT * FROM job_queue
                   WHERE idempotency_key = ?
                     AND status NOT IN ('CANCELLED')
                   ORDER BY created_at DESC LIMIT 1""",
                (idempotency_key,),
            ).fetchone()
            if row:
                return _row_to_dict(row)
        return self.create_job(
            job_type=job_type, payload=payload, priority=priority,
            idempotency_key=idempotency_key, **kwargs,
        )

    # -- Claim (atomic via SQLite busy_timeout) --------------------------
    def claim_next(self, worker_id: str = "worker-1", lease_seconds: int = 600) -> dict[str, Any] | None:
        """Claim el job PENDING de mayor prioridad (menor número) y más
        antiguo. Retorna None si no hay jobs disponibles."""
        now = _now()
        lease_until = _add_seconds(now, lease_seconds)
        # Recuperar leases expirados primero
        self._recover_expired_leases(now)
        row = self.conn.execute(
            """SELECT job_id FROM job_queue
               WHERE status = 'PENDING'
                 AND scheduled_at <= ?
               ORDER BY priority ASC, scheduled_at ASC
               LIMIT 1""",
            (now,),
        ).fetchone()
        if not row:
            return None
        job_id = row["job_id"]
        self.conn.execute(
            """UPDATE job_queue
               SET status = 'RUNNING', claimed_at = ?, lease_expires_at = ?,
                   attempts = attempts + 1, updated_at = ?
               WHERE job_id = ? AND status = 'PENDING'""",
            (now, lease_until, now, job_id),
        )
        self.conn.commit()
        return self.get_job(job_id)

    def _recover_expired_leases(self, now: str) -> int:
        """Recovery: jobs cuyo lease expiró vuelven a PENDING o RETRY_WAIT."""
        rows = self.conn.execute(
            """SELECT job_id, attempts, max_attempts FROM job_queue
               WHERE status = 'RUNNING' AND lease_expires_at < ?""",
            (now,),
        ).fetchall()
        count = 0
        for r in rows:
            if r["attempts"] < r["max_attempts"]:
                self.conn.execute(
                    """UPDATE job_queue
                       SET status = 'RETRY_WAIT', lease_expires_at = NULL,
                           next_retry_at = ?, updated_at = ?
                       WHERE job_id = ?""",
                    (_add_seconds(now, 30), now, r["job_id"]),
                )
            else:
                self.conn.execute(
                    """UPDATE job_queue
                       SET status = 'FAILED', lease_expires_at = NULL,
                           normalized_error = 'lease_expired_max_attempts',
                           completed_at = ?, updated_at = ?
                       WHERE job_id = ?""",
                    (now, now, r["job_id"]),
                )
            count += 1
        if count:
            self.conn.commit()
        return count

    # -- Complete / Fail / Cancel ----------------------------------------
    def complete(self, job_id: str, result_reference: str | None = None) -> None:
        now = _now()
        self.conn.execute(
            """UPDATE job_queue
               SET status = 'SUCCEEDED', completed_at = ?, result_reference = ?,
                   lease_expires_at = NULL, updated_at = ?
               WHERE job_id = ?""",
            (now, result_reference, now, job_id),
        )
        self.conn.commit()

    def fail(self, job_id: str, error: str) -> None:
        now = _now()
        row = self.conn.execute(
            "SELECT attempts, max_attempts FROM job_queue WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if row and row["attempts"] < row["max_attempts"]:
            backoff = min(30 * (2 ** (row["attempts"] - 1)), 3600)
            self.conn.execute(
                """UPDATE job_queue
                   SET status = 'RETRY_WAIT', normalized_error = ?,
                       next_retry_at = ?, lease_expires_at = NULL, updated_at = ?
                   WHERE job_id = ?""",
                (error, _add_seconds(now, backoff), now, job_id),
            )
        else:
            self.conn.execute(
                """UPDATE job_queue
                   SET status = 'FAILED', normalized_error = ?,
                       completed_at = ?, lease_expires_at = NULL, updated_at = ?
                   WHERE job_id = ?""",
                (error, now, now, job_id),
            )
        self.conn.commit()

    def cancel(self, job_id: str) -> None:
        now = _now()
        self.conn.execute(
            """UPDATE job_queue SET status = 'CANCELLED', completed_at = ?,
               updated_at = ? WHERE job_id = ?""",
            (now, now, job_id),
        )
        self.conn.commit()

    # -- Retry wait -> PENDING -------------------------------------------
    def promote_retryable(self) -> int:
        now = _now()
        cursor = self.conn.execute(
            """UPDATE job_queue SET status = 'PENDING', updated_at = ?
               WHERE status = 'RETRY_WAIT' AND next_retry_at <= ?""",
            (now, now),
        )
        self.conn.commit()
        return cursor.rowcount

    # -- Queries ---------------------------------------------------------
    def list_jobs(
        self, *, status: str | None = None, job_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM job_queue WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if job_type:
            query += " AND job_type = ?"
            params.append(job_type)
        query += " ORDER BY priority ASC, created_at ASC LIMIT ?"
        params.append(limit)
        return [_row_to_dict(r) for r in self.conn.execute(query, params).fetchall()]

    def count_by_status(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) as cnt FROM job_queue GROUP BY status"
        ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}

    def safe_pause_jobs(self, scope: str | None = None, reason: str = "") -> int:
        """Pausa todos los jobs PENDING/RUNNING según el scope."""
        now = _now()
        if scope and scope != "GLOBAL":
            cursor = self.conn.execute(
                """UPDATE job_queue SET status = 'SAFE_PAUSED', updated_at = ?
                   WHERE status IN ('PENDING','RUNNING')
                   AND job_type LIKE ?""",
                (now, f"%{scope}%"),
            )
        else:
            cursor = self.conn.execute(
                """UPDATE job_queue SET status = 'SAFE_PAUSED', updated_at = ?
                   WHERE status IN ('PENDING','RUNNING')""",
                (now,),
            )
        self.conn.commit()
        return cursor.rowcount

    def resume_paused(self) -> int:
        now = _now()
        cursor = self.conn.execute(
            """UPDATE job_queue SET status = 'PENDING', updated_at = ?
               WHERE status = 'SAFE_PAUSED'""",
            (now,),
        )
        self.conn.commit()
        return cursor.rowcount


class ApprovalRepository:
    """Cola de aprobaciones del propietario para acciones irreversibles."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def request_approval(
        self, *, approval_type: str, job_id: str | None = None,
        description: str, ttl_seconds: int = 86400,
    ) -> dict[str, Any]:
        now = _now()
        approval_id = f"appr-{uuid.uuid4().hex[:12]}"
        self.conn.execute(
            """INSERT INTO owner_approvals
               (id, approval_type, job_id, description, status,
                requested_at, expires_at, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (approval_id, approval_type, job_id, description, "PENDING",
             now, _add_seconds(now, ttl_seconds), now),
        )
        self.conn.commit()
        return self.get_approval(approval_id)

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM owner_approvals WHERE id = ?", (approval_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None

    def list_pending(self, approval_type: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM owner_approvals WHERE status = 'PENDING'"
        params: list[Any] = []
        if approval_type:
            query += " AND approval_type = ?"
            params.append(approval_type)
        query += " ORDER BY created_at ASC"
        return [_row_to_dict(r) for r in self.conn.execute(query, params).fetchall()]

    def decide(self, approval_id: str, decision: str, decided_by: str = "owner",
               notes: str = "") -> dict[str, Any] | None:
        now = _now()
        self.conn.execute(
            """UPDATE owner_approvals
               SET status = 'DECIDED', decision = ?, decided_by = ?,
                   decision_notes = ?, decided_at = ?, created_at = created_at
               WHERE id = ? AND status = 'PENDING'""",
            (decision, decided_by, notes, now, approval_id),
        )
        self.conn.commit()
        return self.get_approval(approval_id)

    def expire_stale(self) -> int:
        now = _now()
        cursor = self.conn.execute(
            """UPDATE owner_approvals SET status = 'EXPIRED'
               WHERE status = 'PENDING' AND expires_at < ?""",
            (now,),
        )
        self.conn.commit()
        return cursor.rowcount


# -- Helpers --------------------------------------------------------------

def _now() -> str:
    import datetime
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _add_seconds(iso: str, seconds: int) -> str:
    import datetime
    dt = datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
    dt += datetime.timedelta(seconds=seconds)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    if "payload" in d and isinstance(d["payload"], str):
        try:
            d["payload"] = json.loads(d["payload"])
        except (json.JSONDecodeError, TypeError):
            pass
    return d
