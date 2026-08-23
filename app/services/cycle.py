"""Ciclo económico inicial (iteraciones 009-010).

Reglas DETERMINISTAS (sin LLM, sin votos):

- Ciclo inicial: 30 días y 50 USD de capital máximo (configurables).
- Estado inicial: **PRE_CYCLE**. Consultar el estado, abrir la web, crear una
  campaña, generar ideas o investigar **NUNCA inicia el reloj**.
- El reloj arranca SOLO con ``POST /api/economy/cycle/start``: activación
  explícita del propietario + precondiciones cumplidas (12). Determinista,
  idempotente y auditable.
- Vía A: ingresos CONFIRMADOS reales acumulados >= 50 USD.
- Vía B: >= 1 pago real confirmado + coste de continuidad aceptable +
  hipótesis de repetición + sin bloqueadores + capital restante suficiente
  => UNA prórroga de 14 días (solo una vez).
- NO cuentan: visitas, likes, registros gratuitos, promesas, facturas no
  cobradas, ingresos SIMULADOS, capital aportado por el propietario,
  opiniones de modelos.

En esta fase NO existe ejecución financiera real (``real_money_moved=false``),
por lo que ``/cycle/start`` devuelve honestamente ``started: false`` con la
lista de ``missing_conditions`` y el estado sigue en PRE_CYCLE.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.core.config import Settings
from app.models.enums import LedgerEntryType


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


class CycleEvaluator:
    """Evalúa el ciclo económico inicial de forma determinista y auditable.

    IMPORTANTE (corrección crítica de la iteración 010): ninguna operación de
    LECTURA escribe en ``cycle_state``. La fila solo se crea en el arranque
    explícito (``start``).
    """

    def __init__(self, settings: Settings, conn: sqlite3.Connection, repos=None, orchestrator=None) -> None:
        self.settings = settings
        self.conn = conn
        self.repos = repos
        self.orchestrator = orchestrator  # opcional: para precondiciones del ciclo

    # ------------------------------------------------------------------ state
    def _row(self) -> dict | None:
        row = self.conn.execute("SELECT * FROM cycle_state WHERE id = 1").fetchone()
        return dict(row) if row else None

    def _started_at(self) -> str | None:
        """Inicio del ciclo SOLO desde cycle_state (nunca se infiere del ledger:
        la simulación económica no inicia el reloj de 30 días)."""
        row = self._row()
        if row and row.get("started_at"):
            return str(row["started_at"])
        # Compatibilidad: si una base anterior de la 009 dejó una fila con
        # started_at (la corrupción detectada), se ignora como inicio y se
        # devuelve None: el estado correcto es PRE_CYCLE.
        return None

    # ------------------------------------------------------------------ income
    def _confirmed_real_income_usd(self) -> float:
        """Ingresos CONFIRMADOS REALES. En esta fase NO existen: todos los
        ingresos del ledger son SIMULADOS y por regla no cuentan."""
        rows = self.conn.execute(
            "SELECT entry_type FROM ledger_entries WHERE direction = 'credit' AND status = 'CONFIRMED'"
        ).fetchall()
        real = [
            r["entry_type"] for r in rows
            if r["entry_type"] not in (LedgerEntryType.simulated_income.value, LedgerEntryType.initial_capital.value)
        ]
        # No existe ningún tipo de ingreso real implementado (real_money_moved
        # es siempre false); cualquier ingreso real futuro requeriría un tipo
        # explícito REAL_INCOME y reconciliación de facturación.
        return 0.0 if not real else sum(0.0 for _ in real)

    def _spent_usd(self) -> float:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS s FROM ledger_entries "
            "WHERE direction = 'debit' AND status = 'CONFIRMED'"
        ).fetchone()
        return float(row["s"] or 0)

    # ------------------------------------------------------------------ preconditions
    def preconditions(self) -> dict:
        """Las 12 precondiciones para arrancar el ciclo. Deterministas."""
        orc = self.orchestrator
        run = orc.current_run() if orc is not None else None
        run_state = (run or {}).get("state", "PRE_CYCLE")
        experiment = None
        if orc is not None and run:
            experiment = orc.current_experiment_plan(run.get("id"))

        def _ok(label: str, value: bool) -> tuple[str, bool]:
            return label, value

        checks: list[tuple[str, bool]] = [
            _ok("oportunidad_seleccionada", bool(run and run.get("selected_opportunity_id"))),
            _ok("experimento_aprobado", bool(experiment)),
            _ok("oferta_concreta", bool(experiment and experiment.get("offer"))),
            _ok("precio_definido", bool(experiment and experiment.get("price_usd") is not None and float(experiment.get("price_usd") or 0) > 0)),
            _ok("comprador_definido", bool(experiment and experiment.get("buyer"))),
            _ok("canal_autorizado", bool(experiment and experiment.get("channel"))),
            _ok("metrica_exito", bool(experiment and experiment.get("success_metric"))),
            _ok("condicion_abandono", bool(experiment and experiment.get("kill_condition"))),
            _ok("metodo_pago_real_permitido", bool(self.settings.real_payment_confirmation_method)),
            _ok("sin_bloqueadores_criticos", not bool(experiment and experiment.get("blockers"))),
            _ok("produccion_bloqueada", True),  # por diseño: la producción sigue bloqueada
            _ok("activacion_deliberada_propietario", True),  # el propio POST es la activación
        ]
        missing = [label for label, ok in checks if not ok]
        return {
            "all_met": not missing,
            "missing": missing,
            "orchestrator_state": run_state,
            "count": len(checks),
        }

    # ------------------------------------------------------------------ eval
    def evaluate(self) -> dict:
        """Estado del ciclo. LECTURA PURA: no escribe nada, no crea filas y no
        arranca el reloj. Estado inicial: PRE_CYCLE."""
        row = self._row()
        started = bool(row and row.get("started_at"))
        started_at = str(row["started_at"]) if started else None
        if started:
            days_elapsed = max(0, int((datetime.now(timezone.utc) - _dt(started_at)).total_seconds() // 86400))
        else:
            days_elapsed = 0
        days_remaining = max(0, self.settings.cycle_length_days - days_elapsed) if started else self.settings.cycle_length_days

        extension_count = int((row or {}).get("extension_count") or 0)
        extension_used = extension_count >= self.settings.cycle_max_extensions
        extension_granted_at = (row or {}).get("extension_granted_at")

        real_income = self._confirmed_real_income_usd()
        spent = self._spent_usd()
        remaining = max(0.0, self.settings.cycle_capital_usd - spent)

        path_a_passed = started and real_income >= self.settings.cycle_capital_usd
        path_b = {
            "has_real_confirmed_payment": real_income > 0,
            "continuity_cost_acceptable": remaining > 0,
            "repetition_hypothesis": False,  # exige al menos un pago real previo
            "no_blockers": True,
            "remaining_capital_sufficient": remaining > 0,
        }
        path_b_passed = started and all(path_b.values()) and not extension_used

        if not started:
            status = "PRE_CYCLE"
            passed_via = None
        elif path_a_passed:
            status = "PASSED_VIA_A"
            passed_via = "A"
        elif path_b_passed:
            status = "PASSED_VIA_B_EXTENSION"
            passed_via = "B"
        else:
            status = "RUNNING"
            passed_via = None

        return {
            "status": status,
            "clock_running": started,
            "started_at": started_at,
            "days_elapsed": days_elapsed,
            "days_remaining": days_remaining,
            "cycle_days": self.settings.cycle_length_days,
            "checkpoint_day": self.settings.cycle_checkpoint_day,
            "cycle_capital_usd": self.settings.cycle_capital_usd,
            "confirmed_real_income_usd": real_income,
            "spent_usd": round(spent, 2),
            "remaining_capital_usd": round(remaining, 2),
            "simulated": True,
            "real_money_moved": False,
            "income_exclusion_note": (
                "Los ingresos SIMULADOS, promesas, likes, registros gratuitos, "
                "facturas no cobradas, capital del propietario y opiniones de "
                "modelos NO cuentan. En esta fase no existe ejecución financiera "
                "real: real_money_moved=false en todas las respuestas."
            ),
            "path_a": {
                "passed": path_a_passed,
                "requirement": f"{self.settings.cycle_capital_usd:.0f} USD de ingresos confirmados reales",
                "current": real_income,
            },
            "path_b": {
                "passed": path_b_passed,
                "conditions": path_b,
                "extension_days": self.settings.cycle_extension_days,
                "extension_used": extension_used,
                "extension_max": self.settings.cycle_max_extensions,
                "extension_granted_at": extension_granted_at,
            },
            "limits": {
                "max_products": self.settings.max_products_buildable,
                "max_experiments": self.settings.max_experiments_per_cycle,
                "max_pivots_per_product": self.settings.max_pivots_per_product,
                "max_simultaneous_experiments": self.settings.max_simultaneous_experiments,
            },
        }

    # ------------------------------------------------------------------ start
    def start(self, *, actor: str = "owner") -> dict:
        """Arranque EXPLÍCITO del ciclo. Determinista e idempotente.

        - Si el ciclo ya está en marcha: devuelve el estado actual (idempotente).
        - Si faltan precondiciones: ``started: false``, estado PRE_CYCLE y la
          lista de condiciones ausentes.
        """
        row = self._row()
        if row and row.get("started_at"):
            return {**self.evaluate(), "started": True, "idempotent": True, "actor": actor}

        pre = self.preconditions()
        if not pre["all_met"]:
            next_action = "Completar: " + "; ".join(pre["missing"]) if pre["missing"] else "Sin condiciones pendientes."
            return {
                "started": False,
                "status": "PRE_CYCLE",
                "clock_running": False,
                "started_at": None,
                "days_elapsed": 0,
                "days_remaining": self.settings.cycle_length_days,
                "cycle_capital_usd": self.settings.cycle_capital_usd,
                "confirmed_real_income_usd": 0.0,
                "real_money_moved": False,
                "missing_conditions": pre["missing"],
                "next_action": next_action,
            }

        now = _now()
        if row is None:
            self.conn.execute(
                "INSERT INTO cycle_state (id, started_at, extension_granted_at, extension_count) VALUES (1, ?, NULL, 0)",
                (now,),
            )
        else:
            self.conn.execute(
                "UPDATE cycle_state SET started_at = ?, extension_count = 0 WHERE id = 1", (now,)
            )
        self.conn.commit()
        result = {**self.evaluate(), "started": True, "idempotent": False, "actor": actor}
        return result

    # ------------------------------------------------------------------ extend
    def request_extension(self) -> dict:
        """Solicita la prórroga de la vía B (solo con el reloj en marcha)."""
        row = self._row()
        if not row or not row.get("started_at"):
            return {
                "granted": False,
                "reason": "El ciclo no está en marcha (estado PRE_CYCLE): la prórroga solo aplica a un ciclo activo.",
                "status": "PRE_CYCLE",
                "simulated": True,
                "real_money_moved": False,
            }
        extension_count = int(row.get("extension_count") or 0)
        if extension_count >= self.settings.cycle_max_extensions:
            return {
                "granted": False,
                "reason": "La prórroga de 14 días ya se usó (una sola vez por ciclo).",
                "simulated": True,
                "real_money_moved": False,
            }
        result = self.evaluate()
        if result["path_b"]["passed"]:
            now = _now()
            self.conn.execute(
                "UPDATE cycle_state SET extension_granted_at = ?, extension_count = extension_count + 1 WHERE id = 1",
                (now,),
            )
            self.conn.commit()
            return {
                "granted": True,
                "extension_days": self.settings.cycle_extension_days,
                "granted_at": now,
                "simulated": True,
                "real_money_moved": False,
            }
        failed = [k for k, v in result["path_b"]["conditions"].items() if not v]
        return {
            "granted": False,
            "reason": "La vía B no se cumple: " + ", ".join(failed) + ". Requiere al menos un pago real confirmado.",
            "conditions": result["path_b"]["conditions"],
            "simulated": True,
            "real_money_moved": False,
        }
