"""Job Queue model — persistent SQLite-backed job queue for the autonomous
24/7 runtime (iteration 025).

Every autonomous action (discovery, arena generation, research, critique,
scoring, campaign advance, maintenance) flows through this queue. Jobs
survive restarts, support leases, priorities, retries, and audit.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    RETRY_WAIT = "RETRY_WAIT"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    SAFE_PAUSED = "SAFE_PAUSED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobType(str, enum.Enum):
    # Discovery flow
    DISCOVERY_GENERATE = "discovery_generate"
    DISCOVERY_DEDUP = "discovery_dedup"
    DISCOVERY_CLASSIFY = "discovery_classify"
    DISCOVERY_SCORING = "discovery_scoring"
    DISCOVERY_TOURNAMENT = "discovery_tournament"
    # Arena flow
    ARENA_GENERATE = "arena_generate"
    ARENA_IMPORT = "arena_import"
    ARENA_FILTER = "arena_filter"
    ARENA_TOURNAMENT = "arena_tournament"
    # Research
    RESEARCH_MISSION = "research_mission"
    RESEARCH_COLLECT = "research_collect"
    # Critique
    CRITIQUE_REVIEW = "critique_review"
    # Campaigns
    CAMPAIGN_ADVANCE = "campaign_advance"
    CAMPAIGN_FINALIZE = "campaign_finalize"
    # Maintenance
    MAINTENANCE_LEASE_RECOVERY = "maintenance_lease_recovery"
    MAINTENANCE_HEALTHCHECK = "maintenance_healthcheck"
    MAINTENANCE_BACKUP = "maintenance_backup"
    MAINTENANCE_DAILY_SUMMARY = "maintenance_daily_summary"
    # External import
    EXTERNAL_IMPORT = "external_import"
    # Synthesis
    SYNTHESIZE_AND_DECIDE = "synthesize_and_decide"


class JobPriority(int, enum.Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


@dataclass
class Job:
    job_id: str
    job_type: str
    status: str = JobStatus.PENDING.value
    priority: int = JobPriority.NORMAL.value
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""
    attempts: int = 0
    max_attempts: int = 3
    scheduled_at: str = ""
    claimed_at: str | None = None
    lease_expires_at: str | None = None
    next_retry_at: str | None = None
    completed_at: str | None = None
    provider: str | None = None
    model: str | None = None
    purpose: str | None = None
    parent_job_id: str | None = None
    result_reference: str | None = None
    normalized_error: str | None = None
    created_at: str = ""
    updated_at: str = ""
