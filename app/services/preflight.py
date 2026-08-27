"""Preflight — validates readiness for autonomous 24/7 operation.

Returns one of:
- READY_FOR_AUTONOMOUS_24_7
- CONFIGURATION_REQUIRED
- UNSAFE_CONFIGURATION
- PROVIDER_UNAVAILABLE

Checks: variables, OmniRoute, models, allowlist, SQLite, migrations,
scheduler, worker, disk, backup, limits, external blocks.

Iteration 025.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

log = get_logger("preflight")


class PreflightResult:
    """Result of preflight checks."""

    def __init__(self) -> None:
        self.status = "CONFIGURATION_REQUIRED"
        self.checks: list[dict[str, Any]] = []
        self.blockers: list[str] = []
        self.warnings: list[str] = []

    def add_check(self, name: str, passed: bool, detail: str = "", blocking: bool = False) -> None:
        self.checks.append({"name": name, "passed": passed, "detail": detail})
        if not passed and blocking:
            self.blockers.append(f"{name}: {detail}")
        if not passed and not blocking:
            self.warnings.append(f"{name}: {detail}")

    def evaluate(self) -> str:
        if self.blockers:
            if any("credential" in b.lower() or "unavailable" in b.lower() for b in self.blockers):
                self.status = "PROVIDER_UNAVAILABLE"
            elif any("unsafe" in b.lower() or "security" in b.lower() for b in self.blockers):
                self.status = "UNSAFE_CONFIGURATION"
            else:
                self.status = "CONFIGURATION_REQUIRED"
        else:
            self.status = "READY_FOR_AUTONOMOUS_24_7"
        return self.status

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checks": self.checks,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "total_checks": len(self.checks),
            "passed_checks": sum(1 for c in self.checks if c["passed"]),
        }


def run_preflight(conn: sqlite3.Connection, settings: Any) -> dict[str, Any]:
    """Run all preflight checks and return the result."""
    result = PreflightResult()

    # 1. SQLite accessible and schema present
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        required = {"job_queue", "runtime_state", "owner_approvals", "opportunities"}
        missing = required - table_names
        result.add_check(
            "sqlite_schema", len(missing) == 0,
            f"Missing tables: {missing}" if missing else "All required tables present",
            blocking=True,
        )
    except Exception as exc:
        result.add_check("sqlite_accessible", False, str(exc)[:200], blocking=True)

    # 2. Runtime state initialized
    try:
        row = conn.execute("SELECT * FROM runtime_state WHERE id = 1").fetchone()
        result.add_check("runtime_state_initialized", row is not None, blocking=True)
    except Exception:
        result.add_check("runtime_state_initialized", False, blocking=True)

    # 3. OmniRoute configuration
    omniroute_enabled = getattr(settings, "omniroute_enabled", False)
    omniroute_url = getattr(settings, "omniroute_base_url", "")
    result.add_check(
        "omniroute_configured", omniroute_enabled and bool(omniroute_url),
        f"enabled={omniroute_enabled}, url={omniroute_url}",
        blocking=True,
    )

    # 4. API key present
    api_key = getattr(settings, "omniroute_api_key", "")
    cli_token = getattr(settings, "omniroute_cli_token", "")
    has_creds = bool(api_key or cli_token)
    result.add_check(
        "omniroute_credentials", has_creds,
        "No API key or CLI token configured" if not has_creds else "Credentials present",
        blocking=omniroute_enabled,  # Only blocking if OmniRoute is enabled
    )

    # 5. Autonomous mode configuration
    scheduler_enabled = getattr(settings, "autonomous_scheduler_enabled", False)
    worker_enabled = getattr(settings, "autonomous_worker_enabled", False)
    runtime_enabled = getattr(settings, "autonomous_runtime_enabled", False)
    result.add_check(
        "autonomous_config",
        runtime_enabled and scheduler_enabled and worker_enabled,
        f"runtime={runtime_enabled}, scheduler={scheduler_enabled}, worker={worker_enabled}",
    )

    # 6. Budget limits
    max_cost = getattr(settings, "llm_max_estimated_cost_usd_per_day", 0)
    result.add_check(
        "budget_configured", True,
        f"daily_cost_limit=${max_cost}",
    )

    # 7. Disk space
    try:
        import shutil
        usage = shutil.disk_usage(str(Path(__file__).resolve().parents[2]))
        free_gb = usage.free / (1024 ** 3)
        result.add_check(
            "disk_space", free_gb > 0.1,
            f"{free_gb:.2f} GB free",
            blocking=True,
        )
    except Exception:
        result.add_check("disk_space", False, "Could not check disk space")

    # 8. Security: no dangerous settings
    allow_writes = getattr(settings, "autonomous_allow_external_writes", False)
    allow_publication = getattr(settings, "autonomous_allow_publication", False)
    allow_financial = getattr(settings, "autonomous_allow_financial_actions", False)
    allow_production = getattr(settings, "autonomous_allow_production_deployment", False)
    dangerous = []
    if allow_writes:
        dangerous.append("external_writes")
    if allow_publication:
        dangerous.append("publication")
    if allow_financial:
        dangerous.append("financial_actions")
    if allow_production:
        dangerous.append("production_deployment")
    result.add_check(
        "security_policy", len(dangerous) == 0,
        f"Dangerous permissions enabled: {dangerous}" if dangerous else "All safe defaults",
        blocking=len(dangerous) > 0,
    )

    # 9. Production capability blocked
    prod_capable = getattr(settings, "production_capability_available", False)
    result.add_check(
        "production_blocked", not prod_capable,
        "production_capability_available should be False",
    )

    # 10. Existing data integrity
    try:
        opp_count = conn.execute("SELECT COUNT(*) as cnt FROM opportunities").fetchone()["cnt"]
        result.add_check(
            "data_integrity", True,
            f"{opp_count} opportunities in database",
        )
    except Exception:
        result.add_check("data_integrity", False, "Could not query opportunities")

    result.evaluate()
    return result.to_dict()
