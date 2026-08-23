"""Enumeraciones centrales del dominio."""
from __future__ import annotations

from enum import Enum


class OpportunityStatus(str, Enum):
    draft = "draft"
    researching = "researching"
    evaluated = "evaluated"
    approved = "approved"
    needs_more_research = "needs_more_research"
    deferred = "deferred"
    rejected = "rejected"
    blocked = "blocked"


class Decision(str, Enum):
    approved = "approved"
    needs_more_research = "needs_more_research"
    deferred = "deferred"
    rejected = "rejected"
    blocked = "blocked"

    @property
    def label_es(self) -> str:
        return {
            "approved": "Aprobada (candidata a experimento)",
            "needs_more_research": "Necesita más investigación",
            "deferred": "Aplazada",
            "rejected": "Rechazada",
            "blocked": "Bloqueada",
        }[self.value]


class EvidenceType(str, Enum):
    demand_signal = "demand_signal"
    competitor = "competitor"
    price = "price"
    customer_profile = "customer_profile"
    platform_tos = "platform_tos"
    legal_risk = "legal_risk"
    technical = "technical"
    market_size = "market_size"
    other = "other"


class RiskSeverity(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class AgentName(str, Enum):
    scout = "scout"
    researcher = "researcher"
    skeptic = "skeptic"
    economist = "economist"
    builder = "builder"
    compliance = "compliance"
    judge = "judge"
    system = "system"
    human = "human"


class Basis(str, Enum):
    """Base de cada criterio de puntuación: evidencia, estimación o desconocido."""

    evidence = "evidence"
    estimate = "estimate"
    unknown = "unknown"

    @property
    def label_es(self) -> str:
        return {
            "evidence": "Evidencia",
            "estimate": "Estimación",
            "unknown": "Desconocido",
        }[self.value]


class CostMethod(str, Enum):
    free_mode = "free_mode"
    zero_offline = "zero (offline)"
    estimated_api = "estimated_api"
    simulation = "simulation"
    unknown = "unknown"


class OperatingMode(str, Enum):
    """Modos de operación del sistema (mecanismo inequívoco de selección).

    Ver docs/OPERATING_MODES.md. La transición previa PRODUCTION_ARMED existe
    desde la iteración 003: una variable de entorno puede, como máximo, llevar
    al sistema a PRODUCTION_ARMED. AUTONOMOUS_PRODUCTION sigue bloqueado por
    una regla explícita de capacidad (``production_capability_available=false``),
    no solo por ausencia de configuración. Los estados nunca se mezclan.
    """

    development_and_review = "development_and_review"
    simulation = "simulation"
    shadow_mode = "shadow_mode"
    production_armed = "production_armed"
    autonomous_production = "autonomous_production"
    safe_pause = "safe_pause"

    @property
    def label_es(self) -> str:
        return {
            "development_and_review": "Desarrollo y revisión",
            "simulation": "Simulación",
            "shadow_mode": "Modo sombra",
            "production_armed": "Producción armada (preparada, sin activar)",
            "autonomous_production": "Producción autónoma",
            "safe_pause": "Pausa segura",
        }[self.value]

    @property
    def blocks_spending(self) -> bool:
        """Modos que bloquean cualquier gasto (presupuesto protegido)."""
        return self in (OperatingMode.safe_pause, OperatingMode.shadow_mode, OperatingMode.production_armed)


class LedgerEntryType(str, Enum):
    initial_capital = "INITIAL_CAPITAL"
    simulated_income = "SIMULATED_INCOME"
    simulated_expense = "SIMULATED_EXPENSE"
    api_cost = "API_COST"
    infrastructure_cost = "INFRASTRUCTURE_COST"
    experiment_cost = "EXPERIMENT_COST"
    refund = "REFUND"
    reversal = "REVERSAL"
    manual_adjustment = "MANUAL_ADJUSTMENT"


class LedgerStatus(str, Enum):
    pending = "PENDING"
    committed = "COMMITTED"
    confirmed = "CONFIRMED"
    rejected = "REJECTED"
    reversed = "REVERSED"


class LedgerDirection(str, Enum):
    debit = "debit"  # reduce saldo (gasto)
    credit = "credit"  # aumenta saldo (ingreso/capital)


class IncomeSourceType(str, Enum):
    simulated_customer_payment = "simulated_customer_payment"
    imported_result = "imported_result"
    manual_simulation = "manual_simulation"
    experiment_outcome = "experiment_outcome"


class SurvivalStatus(str, Enum):
    unknown = "UNKNOWN"
    healthy = "HEALTHY"
    watch = "WATCH"
    critical = "CRITICAL"
    insolvent = "INSOLVENT"
    paused = "PAUSED"


class EngineState(str, Enum):
    """Máquina de estados del motor de supervivencia (ver docs/OPERATING_MODES.md)."""

    researching = "researching"
    validating = "validating"
    building = "building"
    experimenting = "experimenting"
    earning = "earning"
    optimizing = "optimizing"
    degraded = "degraded"
    safe_pause = "safe_pause"
    safe_shutdown = "safe_shutdown"

    @property
    def label_es(self) -> str:
        return {
            "researching": "Investigando",
            "validating": "Validando",
            "building": "Construyendo",
            "experimenting": "Experimentando",
            "earning": "Generando ingresos",
            "optimizing": "Optimizando",
            "degraded": "Degradado",
            "safe_pause": "Pausa segura",
            "safe_shutdown": "Apagado seguro",
        }[self.value]


class ReportPeriod(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    disabled = "disabled"


class AlertsMode(str, Enum):
    critical_only = "critical_only"
    all = "all"
    disabled = "disabled"
