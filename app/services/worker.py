"""Autonomous Worker — claims and executes jobs from the persistent queue.

The worker runs as a background thread within FastAPI lifespan. It:
1. Claims the next PENDING job (atomic, priority-ordered)
2. Routes to the appropriate handler based on job_type
3. Executes with lease protection
4. Records success/failure in the queue
5. Triggers SAFE_PAUSE on critical errors
6. Supports graceful shutdown

Iteration 025.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any, Callable

from app.core.logging import get_logger
from app.repositories.jobs import JobRepository, _now

log = get_logger("worker")


class AutonomousWorker:
    """Real worker that processes jobs from the persistent queue.

    Each job type maps to a handler function. Handlers receive the job
    payload and must be idempotent (the same job may be retried).
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        enabled: bool = False,
        max_concurrent: int = 2,
        lease_seconds: int = 600,
    ) -> None:
        self.conn = conn
        self.jobs = JobRepository(conn)
        self.enabled = enabled
        self.max_concurrent = max_concurrent
        self.lease_seconds = lease_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._handlers: dict[str, Callable] = {}
        self._active_jobs = 0
        # External references set after construction
        self._llm_router: Any = None
        self._arena_service: Any = None
        self._discovery_service: Any = None
        self._reviews_service: Any = None
        self._campaigns_service: Any = None

    def register_handlers(self, handlers: dict[str, Callable]) -> None:
        """Register job_type -> handler functions."""
        self._handlers.update(handlers)

    def set_services(self, **kwargs: Any) -> None:
        """Inject service references for job handlers."""
        for k, v in kwargs.items():
            setattr(self, f"_{k}", v)

    def start(self) -> None:
        if not self.enabled:
            log.info("Worker disabled (AUTONOMOUS_WORKER_ENABLED=false)")
            return
        if self._thread and self._thread.is_alive():
            log.warning("Worker already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="wawa-worker")
        self._thread.start()
        self._update_runtime_state(running=True)
        log.info("Worker started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=15)
        self._update_runtime_state(running=False)
        log.info("Worker stopped")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run_loop(self) -> None:
        log.info("Worker loop starting")
        while not self._stop_event.is_set():
            try:
                self._process_one_cycle()
            except Exception as exc:
                log.error(f"Worker cycle error: {exc}")
            self._stop_event.wait(2)  # Poll every 2 seconds for new jobs
        log.info("Worker loop ended")

    def _process_one_cycle(self) -> None:
        # Respect concurrency limit
        while self._active_jobs < self.max_concurrent and not self._stop_event.is_set():
            job = self.jobs.claim_next(lease_seconds=self.lease_seconds)
            if not job:
                break
            self._active_jobs += 1
            try:
                self._execute_job(job)
            finally:
                self._active_jobs -= 1

    def _execute_job(self, job: dict[str, Any]) -> None:
        job_id = job["job_id"]
        job_type = job["job_type"]
        log.info(f"Executing job {job_id} (type={job_type}, attempt={job['attempts']})")

        handler = self._handlers.get(job_type)
        if not handler:
            log.warning(f"No handler for job type: {job_type}")
            self.jobs.fail(job_id, f"no_handler_for_{job_type}")
            return

        try:
            result = handler(job.get("payload", {}), job)
            result_ref = None
            if isinstance(result, dict):
                result_ref = json.dumps(result)[:2000]
            elif isinstance(result, str):
                result_ref = result[:2000]
            self.jobs.complete(job_id, result_reference=result_ref)
            log.info(f"Job {job_id} completed successfully")
        except Exception as exc:
            error_msg = str(exc)[:500]
            log.error(f"Job {job_id} failed: {error_msg}")
            self.jobs.fail(job_id, error_msg)
            # Check if we should trigger SAFE_PAUSE
            self._check_safe_pause_trigger(error_msg)

    def _check_safe_pause_trigger(self, error: str) -> None:
        """Activate SAFE_PAUSE on critical errors."""
        critical_patterns = [
            "authentication", "UNAUTHORIZED", "FORBIDDEN",
            "budget", "cost limit", "daily limit",
            "database is locked", "corrupt",
            "Circuit breaker OPEN",
        ]
        for pattern in critical_patterns:
            if pattern.lower() in error.lower():
                log.critical(f"SAFE_PAUSE triggered by: {error[:200]}")
                self._activate_safe_pause(f"worker_error: {error[:200]}")
                return

    def _activate_safe_pause(self, reason: str) -> None:
        now = _now()
        self.conn.execute(
            """UPDATE runtime_state SET
               operating_mode = 'SAFE_PAUSED',
               safe_pause_reason = ?,
               safe_pause_scope = 'GLOBAL',
               safe_pause_activated_at = ?,
               updated_at = ?
               WHERE id = 1""",
            (reason[:500], now, now),
        )
        self.conn.commit()
        self.jobs.safe_pause_jobs("GLOBAL", reason)

    def _update_runtime_state(self, running: bool) -> None:
        now = _now()
        self.conn.execute(
            """UPDATE runtime_state SET worker_running = ?, updated_at = ? WHERE id = 1""",
            (int(running), now),
        )
        self.conn.commit()
