"""BudgetGuard — control estricto de costes.

Reglas:
- Presupuesto diario configurable (USD estimados).
- Presupuesto por oportunidad.
- Máximo de evaluaciones profundas por día.
- Registro de coste estimado por acción (método siempre indicado).
- Bloqueo total opcional (``lock()``).
- Modo gratuito: nunca se gasta dinero real; costes registrados como 0.
- Modo simulación: los límites se calculan y registran, pero no bloquean.

En el MVP el coste real no se puede conocer sin API de pago: se registra la
estimación del proveedor o 0 (método ``zero (offline)``), indicando el método.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import Settings
from app.core.errors import BudgetExceededError
from app.models.decision_log import CostRecord
from app.repositories.costs import CostRepository


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BudgetGuard:
    def __init__(self, settings: Settings, costs: CostRepository, engine=None, economy=None) -> None:
        self.settings = settings
        self.costs = costs
        self.engine = engine  # EngineService opcional (guarda por modo de operación)
        self.economy = economy  # EconomyService opcional (saldo disponible, comprometidos)
        self._lock = False

    # ------------------------------------------------------------------
    def lock(self) -> None:
        self._lock = True

    def unlock(self) -> None:
        self._lock = False

    @property
    def locked(self) -> bool:
        return self._lock

    # ------------------------------------------------------------------
    def _guard_mode(self, *, action: str, estimated: float) -> None:
        """Guarda por modo de operación: propaga ``ModeBlockedError`` (409)."""
        if self.engine is not None:
            self.engine.guard(action=action, estimated=estimated)

    def _budget_reason(self, *, action: str, opportunity_id: str | None, estimated: float) -> str | None:
        """Razones de bloqueo de presupuesto (excluye la guarda de modo)."""
        if self._lock:
            return "BudgetGuard bloqueado manualmente."
        if self.settings.free_mode or self.settings.simulation_mode:
            return None  # se registra, pero nunca bloquea
        spent_today = self.costs.spent_today()
        if spent_today + estimated > self.settings.daily_budget_usd:
            return f"Presupuesto diario agotado (gastado {spent_today:.4f} USD de {self.settings.daily_budget_usd} USD)."
        if opportunity_id:
            spent_opp = self.costs.spent_for_opportunity(opportunity_id)
            if spent_opp + estimated > self.settings.per_opportunity_budget_usd:
                return f"Presupuesto por oportunidad agotado ({spent_opp:.4f} USD)."
        if action == "deep_evaluation":
            n = self.costs.deep_evaluations_today()
            if n >= self.settings.max_deep_evaluations_per_day:
                return f"Máximo de evaluaciones profundas por día alcanzado ({n})."
        return None

    def check(self, *, action: str, opportunity_id: str | None = None, estimated: float = 0.0) -> None:
        """Guarda de modo + límites. Lanza ``ModeBlockedError`` o ``BudgetExceededError``."""
        self._guard_mode(action=action, estimated=estimated)
        reason = self._budget_reason(action=action, opportunity_id=opportunity_id, estimated=estimated)
        if reason:
            raise BudgetExceededError(reason, details={"action": action})

    def spend(
        self,
        *,
        action: str,
        opportunity_id: str | None = None,
        provider: str | None = None,
        estimated_usd: float = 0.0,
        cost_method: str = "zero (offline)",
    ) -> CostRecord:
        """Registra el coste estimado de una acción. El bloqueo manual (lock)
        y la guarda de modo aplican siempre; en modo estricto también los límites.

        Si hay una simulación económica activa y el coste es > 0, se valida el
        saldo disponible y se registra un asiento de API cost en el ledger."""
        self._guard_mode(action=action, estimated=estimated_usd)
        reason = self._budget_reason(action=action, opportunity_id=opportunity_id, estimated=estimated_usd)
        if self.economy is not None and estimated_usd > 0:
            from decimal import Decimal as _D

            self.economy.validate_funds(_D(str(estimated_usd)), action=action)
            self.economy.record_api_cost(action, _D(str(estimated_usd)), provider=provider)
        if reason:
            self.costs.add(
                CostRecord(
                    timestamp=_now(),
                    action=action,
                    opportunity_id=opportunity_id,
                    provider=provider,
                    estimated_cost_usd=estimated_usd,
                    cost_method=cost_method,
                    simulation=self.settings.simulation_mode,
                    blocked=True,
                )
            )
            raise BudgetExceededError(reason, details={"action": action})
        record = CostRecord(
            timestamp=_now(),
            action=action,
            opportunity_id=opportunity_id,
            provider=provider,
            estimated_cost_usd=estimated_usd,
            cost_method=cost_method,
            simulation=self.settings.simulation_mode,
            blocked=False,
        )
        return self.costs.add(record)

    def guard_deep_evaluation(self, opportunity_id: str | None = None) -> CostRecord:
        """Registra una evaluación profunda (pipeline completo) y valida el tope diario."""
        return self.spend(
            action="deep_evaluation",
            opportunity_id=opportunity_id,
            provider="workflow",
            estimated_usd=0.0,
            cost_method="simulation" if self.settings.simulation_mode else "free_mode",
        )

    # ------------------------------------------------------------------
    def status(self) -> dict:
        spent_today = self.costs.spent_today()
        return {
            "free_mode": self.settings.free_mode,
            "simulation_mode": self.settings.simulation_mode,
            "locked": self._lock,
            "daily": {
                "spent": round(spent_today, 6),
                "limit": self.settings.daily_budget_usd,
                "reached": (not self.settings.free_mode and not self.settings.simulation_mode)
                and spent_today >= self.settings.daily_budget_usd,
            },
            "deep_evaluations": {
                "today": self.costs.deep_evaluations_today(),
                "max": self.settings.max_deep_evaluations_per_day,
            },
            "per_opportunity_limit": self.settings.per_opportunity_budget_usd,
            "recent": [r.model_dump() for r in self.costs.recent(10)],
        }
