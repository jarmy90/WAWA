"""EconomyService — contabilidad económica SIMULADA y auditable.

Reglas (deterministas, sin LLM):
- Ledger append-only; el saldo se deriva SIEMPRE de los movimientos.
- Importes en Decimal (redondeo ROUND_HALF_UP a 2 decimales); nunca float.
- Importes negativos rechazados; la dirección debit/credit determina el efecto.
- Idempotencia por idempotency_key (única); reintentar devuelve el original.
- Reversión: entrada de reversión vinculada; el original nunca se edita.
- Moneda única (base_currency); otra moneda => rechazo explícito.
- NADA de esto mueve dinero real: simulated=true, real_money_moved=false.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.core.config import Settings
from app.core.errors import BudgetExceededError, ConflictError, ModeBlockedError, ValidationError
from app.models.decision_log import DecisionLog, _now
from app.models.enums import (
    AgentName,
    EngineState,
    LedgerDirection,
    LedgerEntryType,
    LedgerStatus,
    OperatingMode,
    SurvivalStatus,
)
from app.models.ledger import (
    ExpenseRequestIn,
    IncomeIn,
    LedgerEntry,
    SimulationStartIn,
    money,
)
from app.repositories import Repos
from app.services.budget import BudgetGuard
from app.services.engine import EngineService

ALLOWED_INCOME_SOURCES = {
    "simulated_customer_payment",
    "imported_result",
    "manual_simulation",
    "experiment_outcome",
}


def _f(value: Decimal | None) -> float | None:
    """Decimal → float redondeado (solo para salida JSON)."""
    return round(float(value), 2) if value is not None else None


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


class EconomyService:
    def __init__(self, settings: Settings, repos: Repos, engine: EngineService, budget: BudgetGuard) -> None:
        self.settings = settings
        self.repos = repos
        self.engine = engine
        self.budget = budget

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def is_active(self) -> bool:
        """¿Existe una simulación económica iniciada (capital inicial)?"""
        return self.repos.ledger.has_initial_capital()

    def _require_active(self) -> None:
        if not self.is_active():
            raise ValidationError(
                "No hay simulación económica activa. Inicia una con POST /api/economy/simulation/start.",
                details={"simulated": True, "real_money_moved": False},
            )

    def _require_mode(self, *, allow_production_armed: bool = False) -> None:
        """Solo se permiten operaciones económicas en modos de desarrollo/simulación."""
        self.engine.guard(action="economy_operation", estimated=0.0)
        mode = self.engine.snapshot().mode
        if mode in (OperatingMode.shadow_mode, OperatingMode.production_armed, OperatingMode.autonomous_production):
            raise ModeBlockedError(f"Operaciones económicas no permitidas en modo {mode.value}.")

    def _validate_currency(self, currency: str) -> str:
        currency = (currency or self.settings.base_currency).strip().upper()
        if currency != self.settings.base_currency.upper():
            raise ValidationError(
                f"Moneda '{currency}' no soportada: la moneda base es {self.settings.base_currency}. "
                "No hay conversión automática de divisas.",
            )
        return currency

    def _simulation(self) -> LedgerEntry | None:
        for entry in self.repos.ledger.list(limit=100_000):
            if entry.entry_type == LedgerEntryType.initial_capital.value:
                return entry
        return None

    def _audit(self, *, agent: str, summary: str, opportunity_id: str | None = None, event_type: str = "economy") -> None:
        self.repos.decision_log.add(
            DecisionLog(
                agent=agent,
                opportunity_id=opportunity_id,
                input_summary=summary[:1_000],
                output_summary=summary[:5_000],
                model_or_method="determinista (ledger)",
                estimated_cost=0.0,
                cost_method="simulated",
            )
        )
        self.engine.record_event(event_type=event_type, summary=summary[:2_000], opportunity_id=opportunity_id)

    # ------------------------------------------------------------------
    # Simulación
    # ------------------------------------------------------------------
    def start_simulation(self, payload: SimulationStartIn) -> dict:
        """Inicia una simulación económica con capital ficticio.

        - Solo en DEVELOPMENT_AND_REVIEW o SIMULATION.
        - Nunca crea dinero real.
        - Idempotente por idempotency_key; no reinicia un ledger existente."""
        self._require_mode()
        if self.is_active():
            existing = self._simulation()
            raise ConflictError(
                "Ya existe una simulación económica activa (INITIAL_CAPITAL). No se reinicia silenciosamente el ledger.",
                details={"existing_simulation": existing.id if existing else None, "simulated": True},
            )

        currency = self._validate_currency(payload.currency)
        key = payload.idempotency_key or f"sim-start-{uuid.uuid4().hex}"
        existing = self.repos.ledger.get_by_idempotency(key)
        if existing is not None:
            return {"simulation_started": False, "entry": existing.model_dump(mode="json")}

        entry = LedgerEntry(
            entry_type=LedgerEntryType.initial_capital.value,
            direction=LedgerDirection.credit.value,
            amount=payload.initial_capital,
            currency=currency,
            status=LedgerStatus.confirmed.value,
            source_type="manual_simulation",
            description=f"Capital inicial simulado: {payload.simulation_name}",
            idempotency_key=key,
            operating_mode=self.engine.snapshot().mode.value,
            created_by="owner",
            confirmed_at=_now(),
            metadata={
                "simulation_name": payload.simulation_name,
                "notes": payload.notes or "",
                "maximum_daily_spend": str(payload.maximum_daily_spend) if payload.maximum_daily_spend else "",
                "simulated": True,
                "real_money_moved": False,
            },
        )
        self.repos.ledger.create(entry)
        self._audit(
            agent="economy",
            summary=f"Simulación iniciada '{payload.simulation_name}' con capital {payload.initial_capital} {currency} (SIMULADO).",
            event_type="economy:simulation_start",
        )
        return {
            "simulation_started": True,
            "simulated": True,
            "real_money_moved": False,
            "entry": entry.model_dump(mode="json"),
            "warning": "SIMULACIÓN — NO REPRESENTA DINERO REAL",
        }

    # ------------------------------------------------------------------
    # Ingresos
    # ------------------------------------------------------------------
    def record_income(self, payload: IncomeIn) -> dict:
        self._require_mode()
        self._require_active()
        currency = self._validate_currency(payload.currency)
        if payload.source_type not in ALLOWED_INCOME_SOURCES:
            raise ValidationError(f"source_type no permitido: {payload.source_type}")

        key = payload.idempotency_key or f"income-{uuid.uuid4().hex}"
        existing = self.repos.ledger.get_by_idempotency(key)
        if existing is not None:
            return {"created": False, "simulated": True, "real_money_moved": False, "entry": existing.model_dump(mode="json")}

        entry = LedgerEntry(
            entry_type=LedgerEntryType.simulated_income.value,
            direction=LedgerDirection.credit.value,
            amount=payload.amount,
            currency=currency,
            status=LedgerStatus.confirmed.value,
            source_type=payload.source_type,
            opportunity_id=payload.opportunity_id,
            experiment_id=payload.experiment_id,
            description=payload.description,
            evidence_reference=payload.evidence_reference,
            idempotency_key=key,
            operating_mode=self.engine.snapshot().mode.value,
            created_by="economy",
            confirmed_at=_now(),
            metadata={"simulated": True, "real_money_moved": False},
        )
        self.repos.ledger.create(entry)
        self._audit(
            agent="economy",
            summary=f"Ingreso simulado {payload.amount} {currency} ({payload.source_type}): {payload.description}",
            opportunity_id=payload.opportunity_id,
            event_type="economy:income",
        )
        return {"created": True, "simulated": True, "real_money_moved": False, "entry": entry.model_dump(mode="json")}

    # ------------------------------------------------------------------
    # Gastos: request → committed → confirm / reject
    # ------------------------------------------------------------------
    def request_expense(self, payload: ExpenseRequestIn) -> dict:
        """Flujo request_spend:
        validate_mode → validate_capability → validate_balance → validate_limits
        → crear asiento COMMITTED → (la acción simulada se ejecuta al confirmar)."""
        self._require_mode()
        self._require_active()
        currency = self._validate_currency(payload.currency)

        key = payload.idempotency_key or f"expense-{uuid.uuid4().hex}"
        existing = self.repos.ledger.get_by_idempotency(key)
        if existing is not None:
            return {"created": False, "simulated": True, "real_money_moved": False, "entry": existing.model_dump(mode="json")}

        # validate_balance
        available = self._available_balance()
        if available < payload.amount:
            raise BudgetExceededError(
                f"Fondos insuficientes: disponibles {available} {currency}, solicitados {payload.amount}.",
                details={"available": str(available), "requested": str(payload.amount), "simulated": True},
            )
        # validate_limits
        self._validate_limits(payload)

        entry = LedgerEntry(
            entry_type=payload.entry_type,
            direction=LedgerDirection.debit.value,
            amount=payload.amount,
            currency=currency,
            status=LedgerStatus.committed.value,
            source_type="economy_request",
            opportunity_id=payload.opportunity_id,
            experiment_id=payload.experiment_id,
            description=payload.description,
            evidence_reference=payload.evidence_reference,
            idempotency_key=key,
            operating_mode=self.engine.snapshot().mode.value,
            created_by="economy",
            metadata={"simulated": True, "real_money_moved": False},
        )
        self.repos.ledger.create(entry)
        self._audit(
            agent="economy",
            summary=f"Gasto simulado COMMITTED {payload.amount} {currency}: {payload.description}",
            opportunity_id=payload.opportunity_id,
            event_type="economy:expense_request",
        )
        return {"created": True, "simulated": True, "real_money_moved": False, "entry": entry.model_dump(mode="json"), "status": "COMMITTED"}

    def _validate_limits(self, payload: ExpenseRequestIn) -> None:
        committed_statuses = [LedgerStatus.committed.value, LedgerStatus.confirmed.value]
        # Límite diario
        daily = self.repos.ledger.sum_today_debits(committed_statuses)
        sim = self._simulation()
        daily_limit = None
        if sim and sim.metadata.get("maximum_daily_spend"):
            daily_limit = money(sim.metadata["maximum_daily_spend"])
        if daily_limit is None and self.settings.max_daily_spend_usd > 0:
            daily_limit = money(self.settings.max_daily_spend_usd)
        if daily_limit is not None and daily + payload.amount > daily_limit:
            raise BudgetExceededError(
                f"Límite diario alcanzado: {daily + payload.amount} > {daily_limit} (consumido hoy {daily}).",
                details={"simulated": True},
            )
        # Por oportunidad
        if payload.opportunity_id and self.settings.per_opportunity_budget_usd > 0:
            spent_opp = self.repos.ledger.sum_by(direction="debit", statuses=committed_statuses, opportunity_id=payload.opportunity_id)
            limit = money(self.settings.per_opportunity_budget_usd)
            if spent_opp + payload.amount > limit:
                raise BudgetExceededError(f"Límite por oportunidad alcanzado: {spent_opp + payload.amount} > {limit}.")
        # Por experimento
        if payload.experiment_id and self.settings.max_per_experiment_usd > 0:
            spent_exp = self.repos.ledger.sum_by(direction="debit", statuses=committed_statuses, experiment_id=payload.experiment_id)
            limit = money(self.settings.max_per_experiment_usd)
            if spent_exp + payload.amount > limit:
                raise BudgetExceededError(f"Límite por experimento alcanzado: {spent_exp + payload.amount} > {limit}.")

    def confirm_expense(self, entry_id: str) -> dict:
        self._require_mode()
        entry = self.repos.ledger.get(entry_id)
        if entry is None:
            raise ValidationError("Asiento no encontrado.")
        if entry.status != LedgerStatus.committed.value:
            raise ConflictError(f"Solo se pueden confirmar gastos COMMITTED (estado actual: {entry.status}).")
        self.repos.ledger.set_status(entry_id, LedgerStatus.confirmed)
        self._audit(
            agent="economy",
            summary=f"Gasto simulado CONFIRMADO: {entry.description}",
            opportunity_id=entry.opportunity_id,
            event_type="economy:expense_confirm",
        )
        return {"simulated": True, "real_money_moved": False, "status": "CONFIRMED", "entry_id": entry_id}

    def reject_expense(self, entry_id: str, reason: str | None = None) -> dict:
        self._require_mode()
        entry = self.repos.ledger.get(entry_id)
        if entry is None:
            raise ValidationError("Asiento no encontrado.")
        if entry.status != LedgerStatus.committed.value:
            raise ConflictError(f"Solo se pueden rechazar gastos COMMITTED (estado actual: {entry.status}).")
        self.repos.ledger.set_status(entry_id, LedgerStatus.rejected)
        self._audit(
            agent="economy",
            summary=f"Gasto simulado RECHAZADO ({reason or 'sin motivo'}): {entry.description}",
            opportunity_id=entry.opportunity_id,
            event_type="economy:expense_reject",
        )
        return {"simulated": True, "real_money_moved": False, "status": "REJECTED", "entry_id": entry_id}

    # ------------------------------------------------------------------
    # Reversión
    # ------------------------------------------------------------------
    def reverse_entry(self, entry_id: str, reason: str, actor: str = "human") -> dict:
        """Corrige un movimiento confirmado sin editarlo: crea un REVERSAL
        vinculado y marca el original como REVERSED. Impide doble reversión."""
        self._require_mode()
        entry = self.repos.ledger.get(entry_id)
        if entry is None:
            raise ValidationError("Asiento no encontrado.")
        if entry.status != LedgerStatus.confirmed.value:
            raise ConflictError(f"Solo se pueden revertir asientos CONFIRMED (estado actual: {entry.status}).")
        if entry.entry_type == LedgerEntryType.reversal.value:
            raise ConflictError("No se puede revertir un asiento de reversión.")
        if entry.reversed_entry_id:
            raise ConflictError("Este asiento ya fue revertido (doble reversión bloqueada).")

        reversal_key = f"rev:{entry.id}"
        if self.repos.ledger.get_by_idempotency(reversal_key) is not None:
            raise ConflictError("Este asiento ya tiene una reversión registrada.")

        direction = LedgerDirection.credit.value if entry.direction == LedgerDirection.debit.value else LedgerDirection.debit.value
        reversal = LedgerEntry(
            entry_type=LedgerEntryType.reversal.value,
            direction=direction,
            amount=entry.amount,
            currency=entry.currency,
            status=LedgerStatus.confirmed.value,
            source_type="reversal",
            opportunity_id=entry.opportunity_id,
            experiment_id=entry.experiment_id,
            description=f"Reversión de {entry.description} — {reason}",
            evidence_reference=entry.id,
            idempotency_key=reversal_key,
            operating_mode=self.engine.snapshot().mode.value,
            created_by=actor,
            confirmed_at=_now(),
            reversed_entry_id=entry.id,
            metadata={"simulated": True, "real_money_moved": False, "reverse_reason": reason},
        )
        self.repos.ledger.create(reversal)
        self.repos.ledger.set_reversed(entry.id)
        self._audit(
            agent="economy",
            summary=f"Reversión del asiento {entry.id} por {actor}: {reason}",
            opportunity_id=entry.opportunity_id,
            event_type="economy:reversal",
        )
        return {
            "simulated": True,
            "real_money_moved": False,
            "reversed_entry_id": entry.id,
            "reversal_entry": reversal.model_dump(mode="json"),
        }

    # ------------------------------------------------------------------
    # Integración con BudgetGuard (costes de proveedor)
    # ------------------------------------------------------------------
    def validate_funds(self, amount: Decimal, *, action: str) -> None:
        """Comprueba saldo disponible antes de un gasto con coste > 0."""
        if not self.is_active():
            return
        available = self._available_balance()
        if available < amount:
            raise BudgetExceededError(
                f"Fondos insuficientes para '{action}': disponibles {available}, requeridos {amount}.",
                details={"simulated": True},
            )

    def record_api_cost(self, action: str, amount: Decimal, *, provider: str | None = None) -> None:
        """Registra un coste de API simulado como asiento CONFIRMED."""
        if not self.is_active() or amount <= 0:
            return
        entry = LedgerEntry(
            entry_type=LedgerEntryType.api_cost.value,
            direction=LedgerDirection.debit.value,
            amount=amount,
            currency=self.settings.base_currency,
            status=LedgerStatus.confirmed.value,
            source_type="api_cost",
            description=f"Coste de API simulado ({action}, {provider or 'desconocido'})",
            idempotency_key=f"api-{action}-{uuid.uuid4().hex}",
            operating_mode=self.engine.snapshot().mode.value,
            created_by="budget",
            confirmed_at=_now(),
            metadata={"simulated": True, "real_money_moved": False},
        )
        self.repos.ledger.create(entry)

    # ------------------------------------------------------------------
    # Saldos derivados (siempre desde el ledger; nunca un saldo editable)
    # ------------------------------------------------------------------
    # Reglas de agregación:
    # - El capital inicial es un ingreso de financiación (métrica separada), no
    #   "ingreso confirmado" (ingresos ganados por el negocio).
    # - Los asientos REVERSAL son neutros para el saldo: compensan al original
    #   (marcado REVERSED, que deja de contar) y no deben sumarse dos veces.
    def _confirmed_capital(self) -> Decimal:
        """Capital inicial confirmado (financiación, no ingreso ganado)."""
        total = Decimal("0")
        for entry in self.repos.ledger.list(limit=100_000):
            if (
                entry.entry_type == LedgerEntryType.initial_capital.value
                and entry.status == LedgerStatus.confirmed.value
            ):
                total += entry.amount
        return total

    def _confirmed_income(self) -> Decimal:
        """Ingresos ganados confirmados (excluye capital inicial y reversiones)."""
        return self.repos.ledger.sum_by(
            direction="credit",
            statuses=[LedgerStatus.confirmed.value],
            exclude_types=[LedgerEntryType.initial_capital.value, LedgerEntryType.reversal.value],
        )

    def _confirmed_expenses(self) -> Decimal:
        return self.repos.ledger.sum_by(
            direction="debit",
            statuses=[LedgerStatus.confirmed.value],
            exclude_types=[LedgerEntryType.reversal.value],
        )

    def _pending_income(self) -> Decimal:
        return self.repos.ledger.sum_by(
            direction="credit",
            statuses=[LedgerStatus.pending.value],
            exclude_types=[LedgerEntryType.initial_capital.value, LedgerEntryType.reversal.value],
        )

    def _committed_expenses(self) -> Decimal:
        return self.repos.ledger.sum_by(
            direction="debit",
            statuses=[LedgerStatus.committed.value, LedgerStatus.pending.value],
            exclude_types=[LedgerEntryType.reversal.value],
        )

    def _accounting_balance(self) -> Decimal:
        return self._confirmed_capital() + self._confirmed_income() - self._confirmed_expenses()

    def _available_balance(self) -> Decimal:
        return self._accounting_balance() - self._committed_expenses()

    # ------------------------------------------------------------------
    # Métricas deterministas
    # ------------------------------------------------------------------
    def metrics(self) -> dict:
        confirmed_income = self._confirmed_income()
        confirmed_expenses = self._confirmed_expenses()
        pending_income = self._pending_income()
        committed = self._committed_expenses()
        accounting = self._accounting_balance()
        available = self._available_balance()

        sim = self._simulation()
        initial_capital = sim.amount if sim else Decimal("0")

        # Burn rate: media diaria de gastos confirmados desde el primer gasto.
        daily_expenses = self.repos.ledger.confirmed_debits_by_day()
        burn_rate: Decimal | None = None
        if daily_expenses:
            days = max(1, (datetime.now(timezone.utc).date() - min(datetime.fromisoformat(d).date() for d in daily_expenses)).days + 1)
            burn_rate = confirmed_expenses / Decimal(days)
        else:
            burn_rate = None

        # Runway: solo con historial de consumo; null con explicación si no.
        runway_days: Decimal | None = None
        runway_explanation = None
        if burn_rate is not None and burn_rate > 0 and available > 0:
            runway_days = available / burn_rate
        elif burn_rate is None:
            runway_explanation = "No hay gastos confirmados: sin historial de consumo, el runway es desconocido (no infinito)."
        elif available <= 0:
            runway_explanation = "Saldo disponible <= 0: sin runway."

        # Coste por oportunidad / experimento
        opp_entries = [e for e in self.repos.ledger.list(limit=100_000) if e.opportunity_id and e.direction == "debit"]
        exp_entries = [e for e in self.repos.ledger.list(limit=100_000) if e.experiment_id and e.direction == "debit"]
        active_opps = {e.opportunity_id for e in opp_entries if e.status in (LedgerStatus.committed.value, LedgerStatus.confirmed.value)}
        active_exps = {e.experiment_id for e in exp_entries if e.status in (LedgerStatus.committed.value, LedgerStatus.confirmed.value)}
        cost_per_opportunity = sum(e.amount for e in opp_entries if e.status in (LedgerStatus.committed.value, LedgerStatus.confirmed.value)) / Decimal(len(active_opps)) if active_opps else None
        cost_per_experiment = sum(e.amount for e in exp_entries if e.status in (LedgerStatus.committed.value, LedgerStatus.confirmed.value)) / Decimal(len(active_exps)) if active_exps else None

        # Margen bruto
        gross_margin = (confirmed_income - confirmed_expenses) / confirmed_income if confirmed_income > 0 else None

        # Uso del presupuesto
        budget_utilization = (confirmed_expenses + committed) / initial_capital if initial_capital > 0 else None

        # Gasto diario de hoy vs límite
        daily_limit = None
        if sim and sim.metadata.get("maximum_daily_spend"):
            daily_limit = money(sim.metadata["maximum_daily_spend"])
        if daily_limit is None and self.settings.max_daily_spend_usd > 0:
            daily_limit = money(self.settings.max_daily_spend_usd)
        today_spent = self.repos.ledger.sum_today_debits([LedgerStatus.committed.value, LedgerStatus.confirmed.value])

        def tagged(value, unit: str, quality: str, explanation: str | None = None) -> dict:
            return {"value": _f(value), "unit": unit, "data_quality": quality, "explanation": explanation}

        survival = self.survival_status()
        return {
            "simulated": True,
            "real_money_moved": False,
            "currency": self.settings.base_currency,
            "initial_capital": tagged(initial_capital, "USD", "simulated"),
            "confirmed_income": tagged(confirmed_income, "USD", "simulated"),
            "confirmed_expenses": tagged(confirmed_expenses, "USD", "simulated"),
            "pending_income": tagged(pending_income, "USD", "simulated"),
            "committed_expenses": tagged(committed, "USD", "simulated"),
            "accounting_balance": tagged(accounting, "USD", "simulated"),
            "available_balance": tagged(available, "USD", "simulated"),
            "daily_burn_rate": tagged(burn_rate, "USD/día", "simulated_derived" if burn_rate is not None else "unknown", None if burn_rate is not None else "Sin gastos confirmados."),
            "runway_days": tagged(runway_days, "días", "simulated_derived" if runway_days is not None else "unknown", runway_explanation),
            "cost_per_opportunity": tagged(cost_per_opportunity, "USD", "simulated_derived" if cost_per_opportunity is not None else "unknown", None if cost_per_opportunity is not None else "Sin costes atribuidos a oportunidades."),
            "cost_per_experiment": tagged(cost_per_experiment, "USD", "simulated_derived" if cost_per_experiment is not None else "unknown", None if cost_per_experiment is not None else "Sin costes atribuidos a experimentos."),
            "gross_margin": tagged(gross_margin, "ratio", "simulated_derived" if gross_margin is not None else "unknown", None if gross_margin is not None else "Sin ingresos confirmados: margen desconocido."),
            "budget_utilization": tagged(budget_utilization, "ratio", "simulated_derived" if budget_utilization is not None else "unknown", None if budget_utilization is not None else "Sin capital inicial: uso de presupuesto desconocido."),
            "daily_limit": tagged(daily_limit, "USD", "simulated"),
            "today_spent": tagged(today_spent, "USD", "simulated"),
            "survival_status": survival,
            "reconciliation": self.repos.ledger.last_reconciliation(),
        }

    def survival_status(self) -> dict:
        """Clasificación determinista (sin LLM). SAFE_PAUSE prevalece siempre."""
        snapshot = self.engine.snapshot()
        if snapshot.mode == OperatingMode.safe_pause or snapshot.engine_state == EngineState.safe_pause:
            return {"status": SurvivalStatus.paused.value, "label": "Pausada", "thresholds": "SAFE_PAUSE prevalece sobre cualquier estado económico"}

        available = self._available_balance()
        if available < 0:
            return {"status": SurvivalStatus.insolvent.value, "label": "Insolvente", "thresholds": "saldo disponible < 0"}

        confirmed_expenses = self._confirmed_expenses()
        daily_expenses = self.repos.ledger.confirmed_debits_by_day()
        if not daily_expenses or confirmed_expenses <= 0:
            return {
                "status": SurvivalStatus.unknown.value,
                "label": "Desconocido",
                "thresholds": "Sin historial de gastos confirmados: estado no clasificable (no se inventa).",
            }
        burn = confirmed_expenses / Decimal(max(1, (datetime.now(timezone.utc).date() - min(datetime.fromisoformat(d).date() for d in daily_expenses)).days + 1))
        runway = available / burn if burn > 0 else None
        if runway is None or runway <= 0:
            return {"status": SurvivalStatus.insolvent.value, "label": "Insolvente", "thresholds": "runway <= 0"}
        if runway < Decimal(str(self.settings.survival_critical_days)):
            return {"status": SurvivalStatus.critical.value, "label": "Crítico", "thresholds": f"runway < {self.settings.survival_critical_days} días"}
        if runway < Decimal(str(self.settings.survival_watch_days)):
            return {"status": SurvivalStatus.watch.value, "label": "Vigilancia", "thresholds": f"runway < {self.settings.survival_watch_days} días"}
        return {"status": SurvivalStatus.healthy.value, "label": "Saludable", "thresholds": f"runway >= {self.settings.survival_watch_days} días"}

    # ------------------------------------------------------------------
    # Reconciliación
    # ------------------------------------------------------------------
    def reconcile(self) -> dict:
        """Reconstruye saldos desde cero y comprueba consistencia.

        Detecta: importes inválidos, duplicados de idempotencia, reversiones
        inconsistentes, referencias inexistentes. Ante una inconsistencia
        grave, entra en SAFE_PAUSE (auditado)."""
        issues = list(self.repos.ledger.consistency_issues())
        issues.extend(self.repos.ledger.duplicates_by_idempotency())

        confirmed_income = self._confirmed_income()
        confirmed_expenses = self._confirmed_expenses()
        committed = self._committed_expenses()
        accounting = self._accounting_balance()
        available = self._available_balance()

        grave = any(
            "Importe negativo" in i or "idempotency_key" in i or "REVERSAL" in i or "REVERSED" in i or "referencia" in i.lower()
            for i in issues
        )

        triggered_pause = False
        if grave:
            self.engine.safe_pause(
                reason="Reconciliación detectó inconsistencia grave: " + "; ".join(issues[:3]),
                actor="system",
                rule="reconciliation.grave_inconsistency",
            )
            triggered_pause = True

        run_id = self.repos.ledger.add_reconciliation(
            reconciled=not issues,
            issues=issues,
            summary={
                "confirmed_income": str(confirmed_income),
                "confirmed_expenses": str(confirmed_expenses),
                "committed_expenses": str(committed),
                "accounting_balance": str(accounting),
                "available_balance": str(available),
                "entries": self.repos.ledger.count(),
            },
            triggered_pause=triggered_pause,
        )
        self._audit(
            agent="economy",
            summary=f"Reconciliación #{run_id}: {'OK' if not issues else f'{len(issues)} problema(s)'} (grave={grave})",
            event_type="economy:reconcile",
        )
        return {
            "simulated": True,
            "real_money_moved": False,
            "run_id": run_id,
            "reconciled": not issues,
            "issues": issues,
            "triggered_pause": triggered_pause,
            "summary": {
                "confirmed_income": str(confirmed_income),
                "confirmed_expenses": str(confirmed_expenses),
                "committed_expenses": str(committed),
                "accounting_balance": str(accounting),
                "available_balance": str(available),
                "entries": self.repos.ledger.count(),
            },
        }

    def status(self) -> dict:
        metrics = self.metrics()
        return {
            "simulated": True,
            "real_money_moved": False,
            "simulation_active": self.is_active(),
            "currency": self.settings.base_currency,
            "survival_status": metrics["survival_status"],
            "reconciliation": metrics["reconciliation"],
            "available_balance": metrics["available_balance"],
            "committed_expenses": metrics["committed_expenses"],
            "warning": "SIMULACIÓN — NO REPRESENTA DINERO REAL",
        }
