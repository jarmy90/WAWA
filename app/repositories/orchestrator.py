"""Repositorio del orquestador end-to-end (iteración 010).

Persiste: ejecuciones (orchestrator_runs), transiciones AUDITADAS append-only
(orchestrator_transitions) y planes de experimento (experiment_plans). SQL
parametrizada; nunca interpolación.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.models.orchestrator import ExperimentPlan


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrchestratorRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ------------------------------------------------------------------ runs
    def create_run(self, *, run_id: str, title: str, config: dict) -> dict[str, Any]:
        now = _now()
        self.conn.execute(
            "INSERT INTO orchestrator_runs (id, title, campaign_type, state, status, config, discovery_campaign_id, selected_opportunity_id, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,NULL,NULL,?,?)",
            (run_id, title, config.get("campaign_type", "real_market_discovery"), "CAMPAIGN_CREATED", "active",
             json.dumps(config, ensure_ascii=False), now, now),
        )
        self.conn.commit()
        return self.get_run(run_id)  # type: ignore[return-value]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM orchestrator_runs WHERE id = ?", (run_id,)).fetchone()
        return self._row(row) if row else None

    def list_runs(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM orchestrator_runs WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM orchestrator_runs ORDER BY created_at DESC").fetchall()
        return [self._row(r) for r in rows]

    def update_run(self, run_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {"state", "status", "discovery_campaign_id", "selected_opportunity_id"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return self.get_run(run_id)
        sets["updated_at"] = _now()
        cols = ", ".join(f"{k} = ?" for k in sets)
        self.conn.execute(f"UPDATE orchestrator_runs SET {cols} WHERE id = ?", (*sets.values(), run_id))
        self.conn.commit()
        return self.get_run(run_id)

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        try:
            d["config"] = json.loads(d.get("config") or "{}")
        except json.JSONDecodeError:
            d["config"] = {}
        return d

    # ------------------------------------------------------------- transitions
    def add_transition(
        self,
        *,
        run_id: str,
        from_state: str,
        to_state: str,
        actor: str = "system",
        reason: str | None = None,
        inputs: dict | None = None,
        outputs: dict | None = None,
        concepts_considered: int = 0,
        concepts_rejected: int = 0,
        cost_usd: float | None = None,
        cost_source: str | None = None,
        errors: list[str] | None = None,
        blockers: list[str] | None = None,
        next_action: str | None = None,
        owner_action_required: bool = False,
        synthetic: bool = True,
    ) -> dict[str, Any]:
        self.conn.execute(
            "INSERT INTO orchestrator_transitions "
            "(run_id, from_state, to_state, timestamp, actor, reason, inputs, outputs, concepts_considered, "
            " concepts_rejected, cost_usd, cost_source, errors, blockers, next_action, owner_action_required, synthetic) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id, from_state, to_state, _now(), actor, reason,
                json.dumps(inputs or {}, ensure_ascii=False),
                json.dumps(outputs or {}, ensure_ascii=False),
                concepts_considered, concepts_rejected, cost_usd, cost_source,
                json.dumps(errors or [], ensure_ascii=False),
                json.dumps(blockers or [], ensure_ascii=False),
                next_action, 1 if owner_action_required else 0, 1 if synthetic else 0,
            ),
        )
        self.conn.commit()
        return self.last_transition(run_id)  # type: ignore[return-value]

    def transitions_for(self, run_id: str, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM orchestrator_transitions WHERE run_id = ? ORDER BY id DESC LIMIT ?",
            (run_id, limit),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for k in ("inputs", "outputs", "errors", "blockers"):
                try:
                    d[k] = json.loads(d.get(k) or "[]" if k in ("errors", "blockers") else d.get(k) or "{}")
                except json.JSONDecodeError:
                    d[k] = [] if k in ("errors", "blockers") else {}
            out.append(d)
        return out

    def last_transition(self, run_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM orchestrator_transitions WHERE run_id = ? ORDER BY id DESC LIMIT 1", (run_id,)
        ).fetchone()
        return dict(row) if row else {}

    # ------------------------------------------------------------ experiments
    def create_experiment_plan(self, plan: ExperimentPlan) -> dict[str, Any]:
        self.conn.execute(
            "INSERT INTO experiment_plans "
            "(id, run_id, opportunity_id, decision, offer, buyer, user, problem, value_proposition, price_usd, "
            " delivery_format, demo, channel, initial_message, min_sample, max_contacts, acquisition_method, "
            " max_cost_usd, duration_days, success_metric, success_threshold, kill_condition, product_death_condition, "
            " possible_pivots, automatable_tasks, owner_tasks, risks, dependencies, payment_readiness, "
            " missing_capabilities, blockers, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                plan.id, plan.run_id, plan.opportunity_id, plan.decision, plan.offer, plan.buyer, plan.user,
                plan.problem, plan.value_proposition, plan.price_usd, plan.delivery_format, plan.demo, plan.channel,
                plan.initial_message, plan.min_sample, plan.max_contacts, plan.acquisition_method, plan.max_cost_usd,
                plan.duration_days, plan.success_metric, plan.success_threshold, plan.kill_condition,
                plan.product_death_condition, json.dumps(plan.possible_pivots, ensure_ascii=False),
                json.dumps(plan.automatable_tasks, ensure_ascii=False), json.dumps(plan.owner_tasks, ensure_ascii=False),
                json.dumps(plan.risks, ensure_ascii=False), json.dumps(plan.dependencies, ensure_ascii=False),
                plan.payment_readiness, json.dumps(plan.missing_capabilities, ensure_ascii=False),
                json.dumps(plan.blockers, ensure_ascii=False), plan.created_at,
            ),
        )
        self.conn.commit()
        return self.get_experiment_plan(plan.id)  # type: ignore[return-value]

    def get_experiment_plan(self, plan_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM experiment_plans WHERE id = ?", (plan_id,)).fetchone()
        return self._plan_row(row) if row else None

    def experiment_plan_for_run(self, run_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM experiment_plans WHERE run_id = ? ORDER BY created_at DESC LIMIT 1", (run_id,)
        ).fetchone()
        return self._plan_row(row) if row else None

    def experiment_plan_for_opportunity(self, opportunity_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM experiment_plans WHERE opportunity_id = ? ORDER BY created_at DESC LIMIT 1",
            (opportunity_id,),
        ).fetchone()
        return self._plan_row(row) if row else None

    @staticmethod
    def _plan_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        for k in ("possible_pivots", "automatable_tasks", "owner_tasks", "risks", "dependencies",
                  "missing_capabilities", "blockers"):
            try:
                d[k] = json.loads(d.get(k) or "[]")
            except json.JSONDecodeError:
                d[k] = []
        return d
