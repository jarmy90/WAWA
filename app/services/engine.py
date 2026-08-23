"""Motor de operación: modos, máquina de estados, guardas y auditoría.

Reglas deterministas (no LLM):
- AUTONOMOUS_PRODUCTION está bloqueado por una regla explícita de capacidad
  (``production_capability_available=false``): ni una variable de entorno ni
  una clave pueden activarlo en esta iteración. Una variable de entorno puede,
  como máximo, llevar al sistema a PRODUCTION_ARMED.
- SAFE_PAUSE y SAFE_SHUTDOWN bloquean gastos y experimentos nuevos.
- SHADOW_MODE / PRODUCTION_ARMED no permiten gasto real (coste estimado > 0).
- Arranque seguro: si la configuración es inconsistente (producción sin
  capital, moneda ausente, ledger inconsistente, producción no disponible…),
  el sistema entra automáticamente en SAFE_PAUSE, registra motivo, evento
  crítico y transición auditada, y no intenta recuperarse solo.

Ver docs/OPERATING_MODES.md y docs/AUTONOMOUS_PRODUCTION.md.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import Settings
from app.core.errors import ModeBlockedError
from app.models.decision_log import DecisionLog, _now
from app.models.engine import EngineEvent, EngineSnapshot, ModeTransition
from app.models.enums import AgentName, EngineState, OperatingMode
from app.repositories.engine import EngineRepository

PRODUCTION_MODE = OperatingMode.autonomous_production
ARMED_MODE = OperatingMode.production_armed


class EngineService:
    def __init__(self, settings: Settings, repos_engine: EngineRepository, ledger=None) -> None:
        self.settings = settings
        self.repos = repos_engine
        self.ledger = ledger  # LedgerRepository opcional (consistencia al arrancar)
        self._apply_config_mode()
        self._startup_safety_check()

    # ------------------------------------------------------------------
    def _apply_config_mode(self) -> None:
        """Aplica el modo definido por el propietario en configuración.

        Una variable de entorno puede, como máximo, llevar a PRODUCTION_ARMED.
        Si pide AUTONOMOUS_PRODUCTION, se fuerza SAFE_PAUSE (capacidad false)."""
        snapshot = self.repos.snapshot()
        desired = OperatingMode(self.settings.operating_mode)

        if desired == PRODUCTION_MODE:
            self._transition_to_safe_pause(
                from_mode=snapshot.mode,
                reason=(
                    f"Arranque con operating_mode=autonomous_production solicitado, pero "
                    f"production_capability_available=false: {self.settings.production_block_reason}. "
                    "El entorno no puede activar producción directamente."
                ),
                actor="owner/config",
                rule="startup.production_not_available",
                critical=True,
            )
            return

        if desired == ARMED_MODE:
            preconditions = self._production_precondition_issues()
            if preconditions:
                self._transition_to_safe_pause(
                    from_mode=snapshot.mode,
                    reason="Arranque con PRODUCTION_ARMED solicitado pero precondiciones fallidas: " + "; ".join(preconditions),
                    actor="owner/config",
                    rule="startup.armed_preconditions_failed",
                    critical=True,
                )
                return

        if desired != snapshot.mode:
            self.repos.add_transition(
                ModeTransition(
                    from_mode=snapshot.mode.value,
                    to_mode=desired.value,
                    reason="Modo definido por el propietario en configuración (variable de entorno).",
                    actor="owner/config",
                    decision=desired.value,
                    rule="config.operating_mode",
                )
            )
            snapshot.mode = desired
            if snapshot.activated_at is None:
                snapshot.activated_at = _now()
            self.repos.update_snapshot(snapshot)

    def _production_precondition_issues(self) -> list[str]:
        """Precondiciones económicas deterministas para armar/activar producción.

        La capacidad de producción (``production_capability_available``) NO es
        una precondición de este nivel: PRODUCTION_ARMED es un estado previo
        preparado que una variable de entorno puede alcanzar como máximo; la
        capacidad bloquea únicamente la activación final de
        AUTONOMOUS_PRODUCTION (``_require_production_capability``)."""
        issues: list[str] = []
        if self.settings.capital_total_usd <= 0:
            issues.append("capital_total_usd no definido o <= 0")
        if not self.settings.base_currency:
            issues.append("moneda base no configurada")
        if self.settings.max_daily_spend_usd <= 0:
            issues.append("presupuesto diario inválido (max_daily_spend_usd <= 0)")
        return issues

    def _startup_safety_check(self) -> None:
        """Verificación de arranque: ante inconsistencias → SAFE_PAUSE auditado.

        Condiciones: capital <= 0 en contexto económico, moneda ausente,
        presupuesto diario inválido, ledger inconsistente, producción no
        disponible. No intenta recuperarse activando producción."""
        snapshot = self.repos.snapshot()
        if snapshot.mode == OperatingMode.safe_pause:
            return  # ya pausado (no repetir efectos)

        economic_context = snapshot.mode in (ARMED_MODE, PRODUCTION_MODE) or (
            snapshot.mode in (OperatingMode.simulation, OperatingMode.development_and_review)
            and self.settings.capital_total_usd > 0
        )

        reasons: list[str] = []
        if economic_context:
            reasons.extend(self._production_precondition_issues())

        if self.ledger is not None and self.ledger.count() > 0:
            ledger_issues = self.ledger.consistency_issues()
            if ledger_issues:
                reasons.append("ledger inconsistente al arrancar: " + "; ".join(ledger_issues[:3]))

        if reasons:
            self._transition_to_safe_pause(
                from_mode=snapshot.mode,
                reason="Arranque seguro: " + " | ".join(reasons),
                actor="system",
                rule="startup.safety_check",
                critical=True,
            )

    def _transition_to_safe_pause(self, *, from_mode: OperatingMode, reason: str, actor: str, rule: str, critical: bool) -> None:
        """Entra en SAFE_PAUSE registrando motivo, transición y evento crítico."""
        snapshot = self.repos.snapshot()
        self.repos.add_transition(
            ModeTransition(
                from_mode=from_mode.value,
                to_mode=OperatingMode.safe_pause.value,
                reason=reason,
                actor=actor,
                decision=OperatingMode.safe_pause.value,
                rule=rule,
            )
        )
        snapshot.mode = OperatingMode.safe_pause
        if snapshot.activated_at is None:
            snapshot.activated_at = _now()
        self.repos.update_snapshot(snapshot)
        self.record_event(
            event_type="critical" if critical else "mode_change",
            summary=f"SAFE_PAUSE: {reason[:400]}",
            engine_state=snapshot.engine_state,
            mode=snapshot.mode,
        )

    def safe_pause(self, *, reason: str, actor: str = AgentName.system.value, rule: str = "engine.safe_pause", critical: bool = True) -> EngineSnapshot:
        """Entra en SAFE_PAUSE de forma auditada (usado por reconciliación y guardas)."""
        if self.snapshot().mode == OperatingMode.safe_pause:
            return self.snapshot()
        self._transition_to_safe_pause(from_mode=self.snapshot().mode, reason=reason, actor=actor, rule=rule, critical=critical)
        return self.snapshot()

    # ------------------------------------------------------------------
    def snapshot(self) -> EngineSnapshot:
        return self.repos.snapshot()

    def status(self) -> dict:
        snap = self.repos.snapshot()
        now = datetime.now(timezone.utc)
        uptime = None
        if snap.activated_at:
            try:
                uptime = round((now - datetime.fromisoformat(snap.activated_at)).total_seconds())
            except (TypeError, ValueError):
                uptime = None
        return {
            "mode": snap.mode.value,
            "mode_label": snap.mode.label_es,
            "engine_state": snap.engine_state.value,
            "engine_state_label": snap.engine_state.label_es,
            "current_task": snap.current_task,
            "task_started_at": snap.task_started_at,
            "last_result": snap.last_result,
            "next_action": snap.next_action,
            "heartbeat_at": snap.heartbeat_at,
            "activated_at": snap.activated_at,
            "updated_at": snap.updated_at,
            "uptime_seconds": uptime,
            "production_enabled": snap.mode == PRODUCTION_MODE,
            "production_armed": snap.mode == ARMED_MODE,
            "production_capability_available": self.settings.production_capability_available,
            "production_block_reason": self.settings.production_block_reason,
            "production_activatable": False,  # regla explícita de capacidad
            "counts": {
                "events": self.repos.event_count(),
                "transitions": self.repos.transition_count(),
            },
            "economy": {
                "base_currency": self.settings.base_currency,
                "capital_total_usd": self.settings.capital_total_usd,
                "reserve_intocable_usd": self.settings.reserve_intocable_usd,
                "operating_budget_usd": self.settings.operating_budget_usd,
                "max_daily_spend_usd": self.settings.max_daily_spend_usd,
                "max_per_experiment_usd": self.settings.max_per_experiment_usd,
                "max_simultaneous_experiments": self.settings.max_simultaneous_experiments,
                "initial_cycle_days": self.settings.initial_cycle_days,
                "report_period": self.settings.report_period,
                "alerts_mode": self.settings.alerts_mode,
            },
        }

    # ------------------------------------------------------------------
    def set_mode(
        self,
        mode: OperatingMode,
        *,
        reason: str | None = None,
        actor: str = AgentName.human.value,
        activation_key: str | None = None,
    ) -> EngineSnapshot:
        """Cambia el modo de operación. La activación de producción está
        bloqueada por la regla de capacidad (nunca solo por configuración)."""
        snapshot = self.repos.snapshot()

        if mode == PRODUCTION_MODE:
            self._require_production_capability(activation_key)
        if mode == ARMED_MODE:
            preconditions = self._production_precondition_issues()
            if preconditions:
                raise ModeBlockedError("No se puede armar producción: " + "; ".join(preconditions))

        transition = ModeTransition(
            from_mode=snapshot.mode.value,
            to_mode=mode.value,
            reason=reason or f"Cambio de modo solicitado por {actor}.",
            actor=actor,
            decision=mode.value,
            rule="engine.set_mode",
        )
        self.repos.add_transition(transition)

        snapshot.mode = mode
        if snapshot.activated_at is None:
            snapshot.activated_at = _now()
        self.repos.update_snapshot(snapshot)

        self.record_event(
            event_type="mode_change",
            summary=f"Modo de operación: {snapshot.mode.label_es}",
            engine_state=snapshot.engine_state,
            mode=snapshot.mode,
        )
        return snapshot

    def _require_production_capability(self, activation_key: str | None) -> None:
        """Regla explícita: la capacidad de producción debe estar disponible."""
        if not self.settings.production_capability_available:
            raise ModeBlockedError(
                f"AUTONOMOUS_PRODUCTION bloqueado: {self.settings.production_block_reason}. "
                "No se puede activar producción en esta iteración (sin economía real verificada)."
            )
        configured = self.settings.engine_activation_key
        if configured and activation_key == configured:
            return
        if self.settings.operating_mode == PRODUCTION_MODE.value and not configured:
            return
        raise ModeBlockedError(
            "La activación de AUTONOMOUS_PRODUCTION requiere ENGINE_ACTIVATION_KEY "
            "configurado y una clave de activación válida (activación deliberada y auditable)."
        )

    # ------------------------------------------------------------------
    def set_engine_state(
        self,
        state: EngineState,
        *,
        reason: str | None = None,
        rule: str | None = None,
        task: str | None = None,
        actor: str = AgentName.system.value,
    ) -> EngineSnapshot:
        """Transición de la máquina de estados del motor (registrada)."""
        snapshot = self.repos.snapshot()
        self.repos.add_transition(
            ModeTransition(
                from_mode=snapshot.mode.value,
                to_mode=snapshot.mode.value,
                reason=reason,
                actor=actor,
                decision=state.value,
                rule=rule or "engine.set_engine_state",
            )
        )
        self.repos.set_engine_state(state, task=task)
        self.record_event(
            event_type="engine_state",
            summary=f"Estado del motor: {state.label_es}",
            engine_state=state,
            mode=snapshot.mode,
        )
        return self.repos.snapshot()

    # ------------------------------------------------------------------
    def guard(self, *, action: str, estimated: float = 0.0) -> None:
        """Guarda determinista: bloquea acciones según el modo/estado actual."""
        snapshot = self.repos.snapshot()
        if snapshot.engine_state == EngineState.safe_shutdown:
            raise ModeBlockedError(
                f"Motor en SAFE_SHUTDOWN: acción '{action}' bloqueada. Conserve los datos; no hay gasto ni ejecución.",
                details={"action": action, "engine_state": snapshot.engine_state.value},
            )
        if snapshot.mode == OperatingMode.safe_pause or snapshot.engine_state == EngineState.safe_pause:
            raise ModeBlockedError(
                f"Modo SAFE_PAUSE: acción '{action}' bloqueada. El sistema conserva datos y estado en modo lectura.",
                details={"action": action, "mode": snapshot.mode.value},
            )
        if snapshot.mode in (OperatingMode.shadow_mode, ARMED_MODE) and estimated > 0:
            raise ModeBlockedError(
                f"Modo {snapshot.mode.value}: no se permite gasto real (acción '{action}', coste estimado {estimated:.4f} USD).",
                details={"action": action, "estimated_usd": estimated},
            )

    # ------------------------------------------------------------------
    def heartbeat(self, *, task: str | None = None, last_result: str | None = None, next_action: str | None = None) -> EngineSnapshot:
        self.repos.heartbeat(task=task, last_result=last_result, next_action=next_action)
        return self.repos.snapshot()

    def record_event(
        self,
        *,
        event_type: str,
        summary: str,
        opportunity_id: str | None = None,
        engine_state: EngineState | None = None,
        mode: OperatingMode | None = None,
        cost_usd: float = 0.0,
        confidence: float | None = None,
    ) -> EngineEvent:
        snap = self.repos.snapshot()
        return self.repos.add_event(
            EngineEvent(
                event_type=event_type,
                summary=summary[:2_000],
                opportunity_id=opportunity_id,
                engine_state=(engine_state or snap.engine_state).value,
                mode=(mode or snap.mode).value,
                cost_usd=cost_usd,
                confidence=confidence,
            )
        )

    def events(self, limit: int = 20) -> list[EngineEvent]:
        return self.repos.events(limit)

    def transitions(self, limit: int = 20) -> list[ModeTransition]:
        return self.repos.transitions(limit)
