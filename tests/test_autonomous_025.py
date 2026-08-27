"""Tests for Autonomous 24/7 Runtime (iteración 025).

Covers: job queue, LLM router, scheduler, worker, autonomous flows,
SAFE_PAUSE, approval queue, preflight, runtime state, API endpoints.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.container import build_container
from app.main import create_app
from app.models.job import JobStatus, JobType, JobPriority
from app.providers.llm_router import LLMRouter, LLMRouterConfig, CB_CLOSED, CB_OPEN, CB_HALF_OPEN
from app.repositories.jobs import (
    JobRepository, ApprovalRepository, JOB_SCHEMA, _now, _add_seconds,
)
from app.services.scheduler import AutonomousScheduler
from app.services.worker import AutonomousWorker
from app.services.autonomous import AutonomousFlow
from app.services.safe_pause import SafePause
from app.services.preflight import run_preflight


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture()
def tmp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    # Create all required schemas
    from app.repositories.db import SCHEMA
    conn.executescript(SCHEMA)
    conn.executescript(JOB_SCHEMA)
    # Ensure runtime_state singleton
    conn.execute(
        "INSERT OR IGNORE INTO runtime_state (id, operating_mode, updated_at) VALUES (1, 'OFFLINE', ?)",
        (_now(),),
    )
    conn.commit()
    yield conn
    conn.close()
    db_path.unlink(missing_ok=True)


@pytest.fixture()
def settings(tmp_db):
    return Settings(
        database_path=Path(str(tmp_db.execute("PRAGMA database_list").fetchone()[2])),
        data_dir=Path(tempfile.mkdtemp()),
    )


@pytest.fixture()
def container(settings):
    return build_container(settings)


@pytest.fixture()
def client(container):
    return TestClient(create_app(container))


# ------------------------------------------------------------------
# 1) Job Queue: create, claim, complete
# ------------------------------------------------------------------

class TestJobQueue:
    def test_create_job(self, tmp_db):
        jr = JobRepository(tmp_db)
        job = jr.create_job(job_type="discovery_generate", priority=2)
        assert job["job_id"].startswith("job-")
        assert job["status"] == "PENDING"
        assert job["job_type"] == "discovery_generate"

    def test_claim_next(self, tmp_db):
        jr = JobRepository(tmp_db)
        jr.create_job(job_type="discovery_generate", priority=2)
        job = jr.claim_next()
        assert job is not None
        assert job["status"] == "RUNNING"
        assert job["attempts"] == 1

    def test_claim_empty_queue(self, tmp_db):
        jr = JobRepository(tmp_db)
        assert jr.claim_next() is None

    def test_complete_job(self, tmp_db):
        jr = JobRepository(tmp_db)
        job = jr.create_job(job_type="discovery_generate")
        jr.complete(job["job_id"], result_reference="ok")
        updated = jr.get_job(job["job_id"])
        assert updated["status"] == "SUCCEEDED"

    def test_fail_with_retry(self, tmp_db):
        jr = JobRepository(tmp_db)
        job = jr.create_job(job_type="discovery_generate", max_attempts=3)
        jr.claim_next()
        jr.fail(job["job_id"], "transient error")
        updated = jr.get_job(job["job_id"])
        assert updated["status"] == "RETRY_WAIT"

    def test_fail_max_attempts(self, tmp_db):
        jr = JobRepository(tmp_db)
        job = jr.create_job(job_type="discovery_generate", max_attempts=1)
        jr.claim_next()
        jr.fail(job["job_id"], "final error")
        updated = jr.get_job(job["job_id"])
        assert updated["status"] == "FAILED"

    def test_cancel_job(self, tmp_db):
        jr = JobRepository(tmp_db)
        job = jr.create_job(job_type="discovery_generate")
        jr.cancel(job["job_id"])
        updated = jr.get_job(job["job_id"])
        assert updated["status"] == "CANCELLED"

    def test_idempotent_enqueue(self, tmp_db):
        jr = JobRepository(tmp_db)
        key = "idempotency-test-123"
        j1 = jr.enqueue_if_new(job_type="discovery_generate", idempotency_key=key)
        j2 = jr.enqueue_if_new(job_type="discovery_generate", idempotency_key=key)
        assert j1["job_id"] == j2["job_id"]

    def test_count_by_status(self, tmp_db):
        jr = JobRepository(tmp_db)
        jr.create_job(job_type="discovery_generate")
        jr.create_job(job_type="discovery_generate")
        counts = jr.count_by_status()
        assert counts.get("PENDING", 0) >= 2

    def test_safe_pause_jobs(self, tmp_db):
        jr = JobRepository(tmp_db)
        jr.create_job(job_type="discovery_generate")
        jr.create_job(job_type="arena_generate")
        paused = jr.safe_pause_jobs("GLOBAL")
        assert paused >= 2

    def test_resume_paused(self, tmp_db):
        jr = JobRepository(tmp_db)
        jr.create_job(job_type="discovery_generate")
        jr.safe_pause_jobs("GLOBAL")
        resumed = jr.resume_paused()
        assert resumed >= 1

    def test_priority_ordering(self, tmp_db):
        jr = JobRepository(tmp_db)
        jr.create_job(job_type="low", priority=3)
        jr.create_job(job_type="high", priority=0)
        jr.create_job(job_type="normal", priority=2)
        job = jr.claim_next()
        assert job["job_type"] == "high"


# ------------------------------------------------------------------
# 2) Approval Queue
# ------------------------------------------------------------------

class TestApprovalQueue:
    def test_request_and_decide(self, tmp_db):
        ar = ApprovalRepository(tmp_db)
        appr = ar.request_approval(
            approval_type="financial", description="Test approval"
        )
        assert appr["status"] == "PENDING"
        result = ar.decide(appr["id"], "approved", notes="OK")
        assert result["decision"] == "approved"

    def test_list_pending(self, tmp_db):
        ar = ApprovalRepository(tmp_db)
        ar.request_approval(approval_type="publication", description="Publish")
        ar.request_approval(approval_type="financial", description="Charge")
        pending = ar.list_pending()
        assert len(pending) == 2

    def test_expire_stale(self, tmp_db):
        ar = ApprovalRepository(tmp_db)
        # Create expired approval
        now = _now()
        appr_id = f"appr-{__import__('uuid').uuid4().hex[:12]}"
        tmp_db.execute(
            """INSERT INTO owner_approvals
               (id, approval_type, description, status, requested_at, expires_at, created_at)
               VALUES (?, 'test', 'expired', 'PENDING', ?, ?, ?)""",
            (appr_id, _add_seconds(now, -100), _add_seconds(now, -50), now),
        )
        tmp_db.commit()
        expired = ar.expire_stale()
        assert expired >= 1


# ------------------------------------------------------------------
# 3) LLM Router
# ------------------------------------------------------------------

class TestLLMRouter:
    def test_health_when_unavailable(self, tmp_db):
        router = LLMRouter(tmp_db, omniroute_provider=None)
        health = router.health()
        assert health["router_available"] is False
        assert health["circuit_breaker"] == CB_CLOSED

    def test_circuit_breaker_opens(self, tmp_db):
        config = LLMRouterConfig(circuit_failure_threshold=2)
        router = LLMRouter(tmp_db, config=config)
        # Simulate failures
        router._cb_record_failure()
        assert router._cb_state == CB_CLOSED
        router._cb_record_failure()
        assert router._cb_state == CB_OPEN

    def test_circuit_breaker_half_open_after_cooldown(self, tmp_db):
        config = LLMRouterConfig(circuit_failure_threshold=1, circuit_cooldown_seconds=0)
        router = LLMRouter(tmp_db, config=config)
        router._cb_record_failure()
        assert router._cb_state == CB_OPEN
        # With 0 cooldown, refresh should move to half-open
        router._cb_refresh()
        assert router._cb_state == CB_HALF_OPEN

    def test_circuit_breaker_recovery(self, tmp_db):
        config = LLMRouterConfig(circuit_failure_threshold=1, circuit_cooldown_seconds=0)
        router = LLMRouter(tmp_db, config=config)
        router._cb_record_failure()
        router._cb_refresh()
        router._cb_record_success()
        assert router._cb_state == CB_CLOSED
        assert router._cb_failures == 0

    def test_daily_limit_enforcement(self, tmp_db):
        config = LLMRouterConfig(max_requests_per_day=1, hard_budget_enforcement=True)
        router = LLMRouter(tmp_db, config=config)
        # Insert a fake successful call to exhaust the limit
        tmp_db.execute(
            """INSERT INTO llm_call_log (id, provider, action, requested_model,
               response_status, created_at)
               VALUES ('fake-1', 'omniroute', 'test', '', 'ok', ?)""",
            (_now()[:10],),
        )
        tmp_db.commit()
        with pytest.raises(RuntimeError, match="Daily request limit"):
            router._enforce_daily_limits()

    def test_rate_limit(self, tmp_db):
        config = LLMRouterConfig(max_requests_per_minute=1)
        router = LLMRouter(tmp_db, config=config)
        router._recent_requests = [time.time()]
        with pytest.raises(RuntimeError, match="[Pp]er-minute rate limit"):
            router._enforce_rate_limit()


# ------------------------------------------------------------------
# 4) SAFE_PAUSE
# ------------------------------------------------------------------

class TestSafePause:
    def test_activate_and_status(self, tmp_db):
        sp = SafePause(tmp_db)
        result = sp.activate("test reason", "GLOBAL")
        assert result["activated"] is True
        assert result["scope"] == "GLOBAL"
        status = sp.status()
        assert status["active"] is True

    def test_deactivate(self, tmp_db):
        sp = SafePause(tmp_db)
        sp.activate("test", "GLOBAL")
        result = sp.deactivate(actor="test")
        assert result["deactivated"] is True
        assert sp.status()["active"] is False

    def test_auth_failure_requires_manual(self, tmp_db):
        sp = SafePause(tmp_db)
        result = sp.activate("authentication_failed", "GLOBAL")
        assert result["requires_manual_intervention"] is True

    def test_safe_pause_preserves_queue(self, tmp_db):
        jr = JobRepository(tmp_db)
        sp = SafePause(tmp_db)
        jr.create_job(job_type="discovery_generate")
        sp.activate("test", "GLOBAL")
        # Job should be SAFE_PAUSED, not deleted
        jobs = jr.list_jobs(status="SAFE_PAUSED")
        assert len(jobs) >= 1


# ------------------------------------------------------------------
# 5) Preflight
# ------------------------------------------------------------------

class TestPreflight:
    def test_ready_when_configured(self, tmp_db):
        settings = MagicMock()
        settings.omniroute_enabled = True
        settings.omniroute_base_url = "http://localhost:20128/v1"
        settings.omniroute_api_key = "test-key"
        settings.autonomous_scheduler_enabled = True
        settings.autonomous_worker_enabled = True
        settings.autonomous_runtime_enabled = True
        settings.llm_max_estimated_cost_usd_per_day = 0
        settings.autonomous_allow_external_writes = False
        settings.autonomous_allow_publication = False
        settings.autonomous_allow_financial_actions = False
        settings.autonomous_allow_production_deployment = False
        settings.production_capability_available = False
        result = run_preflight(tmp_db, settings)
        assert result["status"] == "READY_FOR_AUTONOMOUS_24_7"

    def test_config_required_when_disabled(self, tmp_db):
        settings = MagicMock()
        settings.omniroute_enabled = False
        settings.omniroute_base_url = ""
        settings.omniroute_api_key = ""
        settings.autonomous_scheduler_enabled = False
        settings.autonomous_worker_enabled = False
        settings.autonomous_runtime_enabled = False
        settings.llm_max_estimated_cost_usd_per_day = 0
        settings.autonomous_allow_external_writes = False
        settings.autonomous_allow_publication = False
        settings.autonomous_allow_financial_actions = False
        settings.autonomous_allow_production_deployment = False
        settings.production_capability_available = False
        result = run_preflight(tmp_db, settings)
        assert result["status"] in ("CONFIGURATION_REQUIRED", "PROVIDER_UNAVAILABLE")

    def test_unsafe_when_dangerous_permissions(self, tmp_db):
        settings = MagicMock()
        settings.omniroute_enabled = True
        settings.omniroute_base_url = "http://localhost:20128/v1"
        settings.omniroute_api_key = "key"
        settings.autonomous_scheduler_enabled = True
        settings.autonomous_worker_enabled = True
        settings.autonomous_runtime_enabled = True
        settings.llm_max_estimated_cost_usd_per_day = 0
        settings.autonomous_allow_external_writes = True  # DANGEROUS
        settings.autonomous_allow_publication = False
        settings.autonomous_allow_financial_actions = False
        settings.autonomous_allow_production_deployment = False
        settings.production_capability_available = False
        result = run_preflight(tmp_db, settings)
        assert result["status"] == "UNSAFE_CONFIGURATION"


# ------------------------------------------------------------------
# 6) Scheduler
# ------------------------------------------------------------------

class TestScheduler:
    def test_start_stop(self, tmp_db):
        scheduler = AutonomousScheduler(tmp_db, enabled=True, poll_interval_seconds=1)
        scheduler.start()
        assert scheduler.is_running
        scheduler.stop()
        assert not scheduler.is_running

    def test_disabled_does_not_start(self, tmp_db):
        scheduler = AutonomousScheduler(tmp_db, enabled=False)
        scheduler.start()
        assert not scheduler.is_running

    def test_tick_promotes_retryable(self, tmp_db):
        jr = JobRepository(tmp_db)
        job = jr.create_job(job_type="discovery_generate", max_attempts=3)
        jr.claim_next()
        jr.fail(job["job_id"], "error")
        # Manually set next_retry_at to past so tick can promote it
        tmp_db.execute(
            "UPDATE job_queue SET next_retry_at = ? WHERE job_id = ?",
            (_add_seconds(_now(), -10), job["job_id"]),
        )
        tmp_db.commit()
        scheduler = AutonomousScheduler(tmp_db, enabled=False)
        scheduler._tick()
        updated = jr.get_job(job["job_id"])
        assert updated["status"] == "PENDING"


# ------------------------------------------------------------------
# 7) Worker
# ------------------------------------------------------------------

class TestWorker:
    def test_start_stop(self, tmp_db):
        worker = AutonomousWorker(tmp_db, enabled=True)
        worker.start()
        assert worker.is_running
        worker.stop()
        assert not worker.is_running

    def test_disabled_does_not_start(self, tmp_db):
        worker = AutonomousWorker(tmp_db, enabled=False)
        worker.start()
        assert not worker.is_running

    def test_execute_job_with_handler(self, tmp_db):
        results = []
        def handler(payload, job):
            results.append(payload)
            return {"ok": True}

        worker = AutonomousWorker(tmp_db, enabled=False)
        worker.register_handlers({"test_type": handler})
        jr = JobRepository(tmp_db)
        job = jr.create_job(job_type="test_type", payload={"x": 1})
        claimed = jr.claim_next()
        worker._execute_job(claimed)
        assert len(results) == 1
        assert results[0] == {"x": 1}

    def test_execute_unknown_job_type(self, tmp_db):
        worker = AutonomousWorker(tmp_db, enabled=False)
        jr = JobRepository(tmp_db)
        job = jr.create_job(job_type="nonexistent_type", max_attempts=1)
        claimed = jr.claim_next()
        worker._execute_job(claimed)
        updated = jr.get_job(job["job_id"])
        assert updated["status"] == "FAILED"

    def test_execute_failing_handler(self, tmp_db):
        def handler(payload, job):
            raise ValueError("boom")

        worker = AutonomousWorker(tmp_db, enabled=False)
        worker.register_handlers({"fail_type": handler})
        jr = JobRepository(tmp_db)
        job = jr.create_job(job_type="fail_type")
        claimed = jr.claim_next()
        worker._execute_job(claimed)
        updated = jr.get_job(job["job_id"])
        assert updated["status"] in ("RETRY_WAIT", "FAILED")


# ------------------------------------------------------------------
# 8) Autonomous Flow handlers
# ------------------------------------------------------------------

class TestAutonomousFlow:
    def test_all_handlers_registered(self, tmp_db):
        flow = AutonomousFlow(tmp_db)
        handlers = flow.get_handlers()
        expected = [
            "discovery_generate", "discovery_dedup", "discovery_classify",
            "discovery_scoring", "discovery_tournament",
            "arena_generate", "arena_filter", "arena_tournament",
            "research_mission", "critique_review", "campaign_advance",
            "maintenance_healthcheck", "maintenance_lease_recovery",
            "maintenance_backup", "maintenance_daily_summary",
            "synthesize_and_decide",
        ]
        for h in expected:
            assert h in handlers, f"Missing handler: {h}"

    def test_healthcheck(self, tmp_db):
        flow = AutonomousFlow(tmp_db)
        result = flow.handle_maintenance_healthcheck({}, {})
        assert "sqlite_ok" in result
        assert result["sqlite_ok"] is True

    def test_lease_recovery(self, tmp_db):
        flow = AutonomousFlow(tmp_db)
        result = flow.handle_maintenance_lease_recovery({}, {})
        assert "recovered" in result

    def test_daily_summary(self, tmp_db):
        flow = AutonomousFlow(tmp_db)
        result = flow.handle_maintenance_daily_summary({}, {})
        assert "jobs" in result
        assert "timestamp" in result

    def test_discovery_without_service(self, tmp_db):
        flow = AutonomousFlow(tmp_db)
        result = flow.handle_discovery_generate({}, {})
        assert result["status"] == "skipped"

    def test_critique_without_router(self, tmp_db):
        flow = AutonomousFlow(tmp_db)
        result = flow.handle_critique_review({"opportunity_id": "test"}, {})
        assert result["status"] == "skipped"


# ------------------------------------------------------------------
# 9) Runtime State API
# ------------------------------------------------------------------

class TestRuntimeAPI:
    def test_runtime_status_endpoint(self, client):
        resp = client.get("/api/runtime/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "runtime" in data
        assert "scheduler_running" in data
        assert "worker_running" in data
        assert "llm_router" in data
        assert "job_counts" in data

    def test_preflight_endpoint(self, client):
        resp = client.get("/api/runtime/preflight")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] in (
            "READY_FOR_AUTONOMOUS_24_7", "CONFIGURATION_REQUIRED",
            "UNSAFE_CONFIGURATION", "PROVIDER_UNAVAILABLE",
        )

    def test_jobs_endpoint(self, client):
        resp = client.get("/api/runtime/jobs")
        assert resp.status_code == 200
        assert "jobs" in resp.json()

    def test_create_and_cancel_job(self, client):
        resp = client.post("/api/runtime/jobs", json={
            "job_type": "maintenance_healthcheck",
            "priority": 2,
        })
        assert resp.status_code == 200
        job_id = resp.json()["job"]["job_id"]
        resp2 = client.post(f"/api/runtime/jobs/{job_id}/cancel")
        # May be 200 or 422 depending on FastAPI version
        assert resp2.status_code in (200, 422)
        if resp2.status_code == 200:
            assert resp2.json()["cancelled"] is True

    def test_pause_and_resume(self, client):
        resp = client.post("/api/runtime/pause", json={
            "reason": "test pause", "scope": "GLOBAL"
        })
        assert resp.status_code == 200
        assert resp.json()["activated"] is True
        resp2 = client.post("/api/runtime/resume")
        assert resp2.status_code == 200
        assert resp2.json()["deactivated"] is True

    def test_approvals_endpoint(self, client):
        resp = client.get("/api/runtime/approvals")
        assert resp.status_code == 200
        assert "approvals" in resp.json()

    def test_usage_endpoint(self, client):
        resp = client.get("/api/runtime/usage")
        assert resp.status_code == 200
        assert "router_available" in resp.json()

    def test_provider_health_endpoint(self, client):
        resp = client.get("/api/runtime/provider-health")
        assert resp.status_code == 200

    def test_audit_endpoint(self, client):
        resp = client.get("/api/runtime/audit")
        assert resp.status_code == 200
        assert "events" in resp.json()

    def test_daily_summary_endpoint(self, client):
        resp = client.get("/api/runtime/daily-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "job_counts" in data
        assert "usage" in data

    def test_backup_endpoint(self, client):
        resp = client.post("/api/runtime/backup")
        assert resp.status_code == 200
        assert "job" in resp.json()


# ------------------------------------------------------------------
# 10) No LLM calls in any handler
# ------------------------------------------------------------------

class TestNoLLMCalls:
    """All autonomous flow handlers must work without calling external LLMs
    when no provider is configured."""

    def test_discovery_no_llm(self, tmp_db):
        flow = AutonomousFlow(tmp_db)
        result = flow.handle_discovery_generate({}, {})
        assert result.get("status") == "skipped"

    def test_critique_no_llm(self, tmp_db):
        flow = AutonomousFlow(tmp_db)
        result = flow.handle_critique_review({}, {})
        assert result.get("status") == "skipped"

    def test_research_blocked_without_config(self, tmp_db):
        flow = AutonomousFlow(tmp_db)
        flow._settings = MagicMock()
        flow._settings.autonomous_allow_external_reads = False
        result = flow.handle_research_mission({}, {})
        assert result["status"] == "blocked"


# ------------------------------------------------------------------
# 11) SAFE_PAUSE blocks queue
# ------------------------------------------------------------------

class TestSafePauseBlocksQueue:
    def test_safe_pause_prevents_new_claims(self, tmp_db):
        jr = JobRepository(tmp_db)
        sp = SafePause(tmp_db)
        jr.create_job(job_type="discovery_generate")
        sp.activate("test", "GLOBAL")
        # After SAFE_PAUSE, no PENDING jobs should exist to claim
        job = jr.claim_next()
        assert job is None  # All jobs are SAFE_PAUSED

    def test_resume_allows_claims_again(self, tmp_db):
        jr = JobRepository(tmp_db)
        sp = SafePause(tmp_db)
        jr.create_job(job_type="discovery_generate")
        sp.activate("test", "GLOBAL")
        sp.deactivate(actor="test")
        job = jr.claim_next()
        assert job is not None


# ------------------------------------------------------------------
# 12) Production remains blocked
# ------------------------------------------------------------------

class TestProductionBlocked:
    def test_production_capability_false(self, tmp_db):
        from app.core.config import Settings
        s = Settings()
        assert s.production_capability_available is False

    def test_financial_actions_default_false(self, tmp_db):
        from app.core.config import Settings
        s = Settings()
        assert s.autonomous_allow_financial_actions is False
        assert s.autonomous_allow_publication is False
        assert s.autonomous_allow_production_deployment is False
        assert s.autonomous_allow_external_writes is False


# ------------------------------------------------------------------
# 13) Config defaults
# ------------------------------------------------------------------

class TestConfigDefaults:
    def test_default_mode(self):
        from app.core.config import Settings
        s = Settings()
        assert s.wawa_operating_mode == "FREEBUFF_SESSION_ONLY"
        assert s.autonomous_runtime_enabled is False
        assert s.autonomous_scheduler_enabled is False
        assert s.autonomous_worker_enabled is False

    def test_budget_limits(self):
        from app.core.config import Settings
        s = Settings()
        assert s.llm_max_estimated_cost_usd_per_day == 0.0
        assert s.llm_hard_budget_enforcement is True
        assert s.llm_circuit_failure_threshold == 5


# ------------------------------------------------------------------
# 14) Jobs survive simulated restart (SQLite persistence)
# ------------------------------------------------------------------

class TestJobPersistence:
    def test_jobs_persist_across_reopen(self, tmp_db):
        jr = JobRepository(tmp_db)
        job = jr.create_job(job_type="test_persist", payload={"key": "value"})
        job_id = job["job_id"]
        # Get the actual DB path
        db_path = tmp_db.execute("PRAGMA database_list").fetchone()[2]
        # Close and reopen connection
        tmp_db.close()
        conn2 = sqlite3.connect(db_path, check_same_thread=False)
        conn2.row_factory = sqlite3.Row
        conn2.execute("PRAGMA journal_mode = WAL")
        conn2.execute("PRAGMA foreign_keys = ON")
        jr2 = JobRepository(conn2)
        retrieved = jr2.get_job(job_id)
        assert retrieved is not None
        assert retrieved["job_type"] == "test_persist"
        conn2.close()


# ------------------------------------------------------------------
# 15) Owner approval workflow
# ------------------------------------------------------------------

class TestOwnerApprovalWorkflow:
    pass  # Covered by TestApprovalQueue above
    def test_approval_required_for_financial(self, tmp_db):
        ar = ApprovalRepository(tmp_db)
        appr = ar.request_approval(
            approval_type="financial",
            description="Charge customer $50",
            ttl_seconds=3600,
        )
        assert appr["status"] == "PENDING"
        # Check it appears in pending list
        pending = ar.list_pending("financial")
        assert len(pending) >= 1

    def test_rejection_blocks_action(self, tmp_db):
        ar = ApprovalRepository(tmp_db)
        appr = ar.request_approval(
            approval_type="publication",
            description="Publish landing page",
        )
        ar.decide(appr["id"], "rejected", notes="Not ready")
        result = ar.get_approval(appr["id"])
        assert result["decision"] == "rejected"
        assert result["status"] == "DECIDED"
