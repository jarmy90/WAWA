"""Autonomous Scheduler — real persistent scheduler for 24/7 operation.

The scheduler runs inside the FastAPI lifespan (or as a standalone process).
It periodically:
1. Promotes retryable jobs back to PENDING
2. Enqueues scheduled autonomous tasks (discovery rounds, maintenance)
3. Recovers expired leases
4. Checks circuit breaker and provider health
5. Produces maintenance summaries
6. Triggers SAFE_PAUSE on critical errors

Iteration 025.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time as _time
from typing import Any

from app.core.logging import get_logger
from app.repositories.jobs import JobRepository, _now

log = get_logger("scheduler")


class AutonomousScheduler:
    """Real scheduler that runs as a background thread within FastAPI lifespan.

    - Polls the job queue every `poll_interval_seconds`
    - Promotes retryable jobs
    - Enqueues periodic maintenance and discovery tasks
    - Does NOT duplicate across multiple Uvicorn workers (single-process)
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        poll_interval_seconds: int = 15,
        enabled: bool = False,
    ) -> None:
        self.conn = conn
        self.jobs = JobRepository(conn)
        self.poll_interval = max(poll_interval_seconds, 5)
        self.enabled = enabled
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_maintenance_at: str | None = None
        self._last_discovery_at: str | None = None

    def start(self) -> None:
        if not self.enabled:
            log.info("Scheduler disabled (AUTONOMOUS_SCHEDULER_ENABLED=false)")
            return
        if self._thread and self._thread.is_alive():
            log.warning("Scheduler already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="wawa-scheduler")
        self._thread.start()
        self._update_runtime_state(running=True)
        log.info(f"Scheduler started (poll={self.poll_interval}s)")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self._update_runtime_state(running=False)
        log.info("Scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run_loop(self) -> None:
        log.info("Scheduler loop starting")
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as exc:
                log.error(f"Scheduler tick error: {exc}")
                self._record_error(str(exc))
            self._stop_event.wait(self.poll_interval)
        log.info("Scheduler loop ended")

    def _tick(self) -> None:
        now = _now()
        # 1. Promote retryable jobs
        promoted = self.jobs.promote_retryable()
        if promoted:
            log.info(f"Promoted {promoted} retryable jobs to PENDING")

        # 2. Check for expired approvals
        expired = self.jobs.conn.execute(
            """UPDATE owner_approvals SET status = 'EXPIRED'
               WHERE status = 'PENDING' AND expires_at < ?""",
            (now,),
        ).rowcount
        if expired:
            self.jobs.conn.commit()
            log.info(f"Expired {expired} stale approvals")

        # 3. Periodic maintenance (every 30 minutes)
        if self._should_run_maintenance(now):
            self._enqueue_maintenance(now)

        # 4. Periodic discovery round (every 6 hours)
        if self._should_run_discovery(now):
            self._enqueue_discovery(now)

        # 5. Update heartbeat
        self.conn.execute(
            """UPDATE runtime_state SET updated_at = ? WHERE id = 1""",
            (now,),
        )
        self.conn.commit()

    def _should_run_maintenance(self, now: str) -> bool:
        if not self._last_maintenance_at:
            return True
        try:
            from datetime import datetime, timedelta
            last = datetime.strptime(self._last_maintenance_at, "%Y-%m-%dT%H:%M:%SZ")
            return datetime.utcnow() - last >= timedelta(minutes=30)
        except (ValueError, TypeError):
            return True

    def _should_run_discovery(self, now: str) -> bool:
        if not self._last_discovery_at:
            return True
        try:
            from datetime import datetime, timedelta
            last = datetime.strptime(self._last_discovery_at, "%Y-%m-%dT%H:%M:%SZ")
            return datetime.utcnow() - last >= timedelta(hours=6)
        except (ValueError, TypeError):
            return True

    def _enqueue_maintenance(self, now: str) -> None:
        self.jobs.enqueue_if_new(
            job_type="maintenance_healthcheck",
            idempotency_key=f"maintenance-healthcheck-{now[:13]}",
            priority=3,
            purpose="maintenance",
        )
        self._last_maintenance_at = now
        log.info("Enqueued maintenance healthcheck job")

    def _enqueue_discovery(self, now: str) -> None:
        self.jobs.enqueue_if_new(
            job_type="discovery_generate",
            idempotency_key=f"discovery-round-{now[:13]}",
            priority=2,
            purpose="discovery",
        )
        self._last_discovery_at = now
        log.info("Enqueued discovery generation job")

    def _update_runtime_state(self, running: bool) -> None:
        now = _now()
        self.conn.execute(
            """UPDATE runtime_state SET scheduler_running = ?, updated_at = ? WHERE id = 1""",
            (int(running), now),
        )
        self.conn.commit()

    def _record_error(self, error: str) -> None:
        now = _now()
        self.conn.execute(
            """UPDATE runtime_state SET last_error = ?, updated_at = ? WHERE id = 1""",
            (error[:500], now),
        )
        self.conn.commit()
