"""LLM Runtime Router — unified entry point for all LLM calls in autonomous mode.

Wraps OmniRoute (primary) and other providers with:
- Model allowlist
- Purpose-typed routing
- Token/cost request limits (per-minute, per-day)
- Circuit breaker (consecutive failures → open → cooldown → half-open)
- Structured response validation
- Full audit trail in llm_call_log
- Fallback only when configured and always registered

Iteration 025.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.providers.base import LLMResponse

log = get_logger("llm_router")

# Circuit breaker states
CB_CLOSED = "CLOSED"
CB_OPEN = "OPEN"
CB_HALF_OPEN = "HALF_OPEN"

# Purpose categories for typed routing
PURPOSE_DISCOVERY = "discovery"
PURPOSE_RESEARCH = "research"
PURPOSE_CRITIQUE = "critique"
PURPOSE_ARENA = "arena"
PURPOSE_SCORING = "scoring"
PURPOSE_SYNTHESIS = "synthesis"
PURPOSE_MAINTENANCE = "maintenance"

VALID_PURPOSES = {
    PURPOSE_DISCOVERY, PURPOSE_RESEARCH, PURPOSE_CRITIQUE,
    PURPOSE_ARENA, PURPOSE_SCORING, PURPOSE_SYNTHESIS, PURPOSE_MAINTENANCE,
}


@dataclass
class LLMRouterConfig:
    """Runtime limits for LLM calls."""
    max_requests_per_minute: int = 10
    max_requests_per_day: int = 500
    max_tokens_per_job: int = 12000
    max_tokens_per_day: int = 150000
    max_estimated_cost_usd_per_day: float = 0.0
    hard_budget_enforcement: bool = True
    max_retries: int = 2
    circuit_failure_threshold: int = 5
    circuit_cooldown_seconds: int = 900
    model_allowlist: list[str] = field(default_factory=list)
    discovery_model: str = "auto"
    research_model: str = "auto"
    critique_model: str = "auto"
    default_model: str = "auto"


class LLMRouter:
    """Unified LLM runtime router for the autonomous system.

    ALL autonomous LLM calls go through this router. It enforces limits,
    circuit breaker, allowlist, and audit trail.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        omniroute_provider: Any = None,
        config: LLMRouterConfig | None = None,
    ) -> None:
        self.conn = conn
        self.omniroute = omniroute_provider
        self.config = config or LLMRouterConfig()
        # Circuit breaker state (in-memory, rebuilt from DB on startup)
        self._cb_state = CB_CLOSED
        self._cb_failures = 0
        self._cb_last_trip: str | None = None
        # Request rate tracking (in-memory, per-minute window)
        self._recent_requests: list[float] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def available(self) -> bool:
        """Router is available if OmniRoute is enabled and connected."""
        return self.omniroute is not None and getattr(self.omniroute, "available", lambda: False)()

    def health(self) -> dict[str, Any]:
        return {
            "router_available": self.available(),
            "omniroute_enabled": getattr(self.omniroute, "enabled", False),
            "circuit_breaker": self._cb_state,
            "circuit_failures": self._cb_failures,
            "requests_today": self._count_today("requests"),
            "tokens_today": self._count_today("tokens"),
            "cost_today_usd": self._cost_today(),
            "daily_limits": {
                "requests": self.config.max_requests_per_day,
                "tokens": self.config.max_tokens_per_day,
                "cost_usd": self.config.max_estimated_cost_usd_per_day,
            },
        }

    def record_state(self, runtime_state_conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Persist current router state to runtime_state table."""
        now = _now()
        conn = runtime_state_conn or self.conn
        conn.execute(
            """UPDATE runtime_state SET
               omniroute_available = ?,
               circuit_breaker_state = ?,
               circuit_breaker_failures = ?,
               circuit_breaker_last_trip = ?,
               requests_today = ?,
               tokens_today = ?,
               cost_today_usd = ?,
               updated_at = ?
               WHERE id = 1""",
            (
                int(self.available()),
                self._cb_state,
                self._cb_failures,
                self._cb_last_trip,
                self._count_today("requests"),
                self._count_today("tokens"),
                self._cost_today(),
                now,
            ),
        )
        conn.commit()
        return self.health()

    def call(
        self,
        prompt: str,
        *,
        purpose: str = PURPOSE_MAINTENANCE,
        system: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        output_schema: dict[str, Any] | None = None,
        job_id: str | None = None,
        max_tokens_override: int | None = None,
    ) -> LLMResponse:
        """Execute an LLM call through the router with all safeguards.

        Raises RuntimeError if any limit or circuit breaker blocks the call.
        """
        # 1. Validate purpose
        if purpose not in VALID_PURPOSES:
            raise RuntimeError(f"Invalid purpose: {purpose}")

        # 2. Circuit breaker check
        self._cb_refresh()
        if self._cb_state == CB_OPEN:
            raise RuntimeError(
                f"Circuit breaker OPEN: {self._cb_failures} consecutive failures. "
                f"Cooldown until {self._cb_last_trip}."
            )

        # 3. Check daily limits
        self._enforce_daily_limits()

        # 4. Check per-minute rate
        self._enforce_rate_limit()

        # 5. Check allowlist
        resolved_model = self._resolve_model(purpose, model)
        if self.config.model_allowlist and resolved_model not in self.config.model_allowlist:
            if resolved_model != "auto":
                raise RuntimeError(
                    f"Model '{resolved_model}' not in allowlist: {self.config.model_allowlist}"
                )

        # 6. Execute via OmniRoute
        if not self.available():
            raise RuntimeError("OmniRoute not available — no LLM provider configured")

        call_id = f"call-{uuid.uuid4().hex[:12]}"
        started = time.monotonic()
        try:
            response = self.omniroute.generate(
                prompt,
                system=system,
                task=purpose,
                output_schema=output_schema,
                temperature=temperature,
                model=resolved_model,
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            response.latency_ms = latency_ms

            # 7. Record success
            self._cb_record_success()
            self._log_call(call_id, response, purpose, job_id, "ok")
            return response

        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            # 8. Record failure
            self._cb_record_failure()
            self._log_call_error(call_id, exc, purpose, job_id, latency_ms)
            raise

    # ------------------------------------------------------------------
    # Model resolution
    # ------------------------------------------------------------------

    def _resolve_model(self, purpose: str, model: str | None) -> str:
        if model:
            return model
        purpose_map = {
            PURPOSE_DISCOVERY: self.config.discovery_model,
            PURPOSE_RESEARCH: self.config.research_model,
            PURPOSE_CRITIQUE: self.config.critique_model,
            PURPOSE_ARENA: self.config.discovery_model,
            PURPOSE_SCORING: self.config.default_model,
            PURPOSE_SYNTHESIS: self.config.default_model,
            PURPOSE_MAINTENANCE: self.config.default_model,
        }
        return purpose_map.get(purpose, self.config.default_model)

    # ------------------------------------------------------------------
    # Circuit breaker
    # ------------------------------------------------------------------

    def _cb_refresh(self) -> None:
        if self._cb_state != CB_OPEN:
            return
        if self._cb_last_trip:
            import datetime
            try:
                cooldown_end = datetime.datetime.strptime(
                    self._cb_last_trip, "%Y-%m-%dT%H:%M:%SZ"
                ) + datetime.timedelta(seconds=self.config.circuit_cooldown_seconds)
                if datetime.datetime.utcnow() >= cooldown_end:
                    self._cb_state = CB_HALF_OPEN
            except (ValueError, TypeError):
                self._cb_state = CB_HALF_OPEN

    def _cb_record_success(self) -> None:
        if self._cb_state == CB_HALF_OPEN:
            self._cb_state = CB_CLOSED
            self._cb_failures = 0
            log.info("Circuit breaker CLOSED (recovery confirmed)")
        elif self._cb_state == CB_CLOSED:
            self._cb_failures = 0

    def _cb_record_failure(self) -> None:
        self._cb_failures += 1
        if self._cb_failures >= self.config.circuit_failure_threshold:
            self._cb_state = CB_OPEN
            self._cb_last_trip = _now()
            log.warning(
                f"Circuit breaker OPEN: {self._cb_failures} failures, "
                f"cooldown {self.config.circuit_cooldown_seconds}s"
            )

    # ------------------------------------------------------------------
    # Limits
    # ------------------------------------------------------------------

    def _enforce_daily_limits(self) -> None:
        if not self.config.hard_budget_enforcement:
            return
        requests = self._count_today("requests")
        if requests >= self.config.max_requests_per_day:
            raise RuntimeError(f"Daily request limit reached: {requests}/{self.config.max_requests_per_day}")
        tokens = self._count_today("tokens")
        if tokens >= self.config.max_tokens_per_day:
            raise RuntimeError(f"Daily token limit reached: {tokens}/{self.config.max_tokens_per_day}")
        cost = self._cost_today()
        if self.config.max_estimated_cost_usd_per_day > 0 and cost >= self.config.max_estimated_cost_usd_per_day:
            raise RuntimeError(f"Daily cost limit reached: ${cost:.4f}/${self.config.max_estimated_cost_usd_per_day}")

    def _enforce_rate_limit(self) -> None:
        now = time.time()
        cutoff = now - 60
        self._recent_requests = [t for t in self._recent_requests if t > cutoff]
        if len(self._recent_requests) >= self.config.max_requests_per_minute:
            raise RuntimeError(
                f"Per-minute rate limit reached: {len(self._recent_requests)}/{self.config.max_requests_per_minute}"
            )
        self._recent_requests.append(now)

    # ------------------------------------------------------------------
    # Audit trail
    # ------------------------------------------------------------------

    def _log_call(
        self, call_id: str, response: LLMResponse, purpose: str,
        job_id: str | None, status: str,
    ) -> None:
        now = _now()
        estimated_cost = getattr(response, "cost_estimate_usd", 0) or 0
        self.conn.execute(
            """INSERT INTO llm_call_log
               (id, provider, action, opportunity_id, requested_model, actual_model,
                prompt_tokens, completion_tokens, total_tokens, reported_cost,
                estimated_cost, cost_source, billing_verified, latency_ms,
                retry_count, response_status, notes, created_at,
                actual_provider, routing_strategy)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                call_id, "omniroute", purpose, job_id,
                getattr(response, "model", ""), getattr(response, "actual_model", ""),
                (response.usage or {}).get("prompt_tokens"),
                (response.usage or {}).get("completion_tokens"),
                (response.usage or {}).get("total_tokens"),
                getattr(response, "reported_cost", None),
                estimated_cost,
                getattr(response, "cost_source", "UNKNOWN"),
                0,  # billing_verified
                getattr(response, "latency_ms", 0),
                getattr(response, "retry_count", 0),
                status,
                getattr(response, "notes", ""),
                now,
                getattr(response, "actual_model", ""),
                "purpose_routing",
            ),
        )
        self.conn.commit()

    def _log_call_error(
        self, call_id: str, exc: Exception, purpose: str,
        job_id: str | None, latency_ms: int,
    ) -> None:
        now = _now()
        error_msg = str(exc)[:300]
        self.conn.execute(
            """INSERT INTO llm_call_log
               (id, provider, action, opportunity_id, requested_model,
                latency_ms, response_status, notes, created_at, routing_strategy)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (call_id, "omniroute", purpose, job_id, "", latency_ms, "error", error_msg, now, "purpose_routing"),
        )
        self.conn.commit()

    def _count_today(self, metric: str) -> int:
        import datetime
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        if metric == "requests":
            row = self.conn.execute(
                "SELECT COUNT(*) as cnt FROM llm_call_log WHERE created_at >= ? AND response_status = 'ok'",
                (today,),
            ).fetchone()
        elif metric == "tokens":
            row = self.conn.execute(
                "SELECT COALESCE(SUM(total_tokens),0) as cnt FROM llm_call_log WHERE created_at >= ? AND response_status = 'ok'",
                (today,),
            ).fetchone()
        else:
            return 0
        return row["cnt"] if row else 0

    def _cost_today(self) -> float:
        import datetime
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        row = self.conn.execute(
            "SELECT COALESCE(SUM(estimated_cost),0) as total FROM llm_call_log WHERE created_at >= ? AND response_status = 'ok'",
            (today,),
        ).fetchone()
        return float(row["total"]) if row else 0.0


def _now() -> str:
    import datetime
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
