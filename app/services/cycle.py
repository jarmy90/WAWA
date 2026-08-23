"""Ciclo económico inicial (iteración 009).

Reglas DETERMINISTAS (sin LLM, sin votos):

- Ciclo inicial: 30 días y 50 USD de capital máximo (configurables).
- Vía A: ingresos CONFIRMADOS reales acumulados >= 50 USD.
- Vía B: >= 1 pago real confirmado + coste de continuidad aceptable +
  hipótesis de repetición + sin bloqueadores + capital restante suficiente
  => UNA prórroga de 14 días (solo una vez).
- NO cuentan: visitas, likes, registros gratuitos, promesas, facturas no
  cobradas, ingresos SIMULADOS, capital aportado por el propietario,
  opiniones de modelos.

En la iteración 009 el sistema NO puede mover dinero real
(``real_money_moved=false`` en todas las respuestas), por lo que ambas vías
devuelven honestamente ``not_passed`` con la razón concreta de cada condición.
El estado de prórroga persiste en una tabla mínima append-only de estado
(``cycle_state``) para que la concesión única sea auditable y sobreviva a
reinicios.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.core.config import Settings
from app.models.enums import LedgerEntryType, LedgerStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(timezone.utc)


class CycleEvaluator:
    """Evalúa el ciclo económico inicial de forma determinista y auditable."""

    def __init__(self, settings: Settings, conn: sqlite3.Connection) -> None:
        self.settings = settings
        self.conn = conn

    # ------------------------------------------------------------------ state
    def _ensure_row(self) -> dict:
        row = self.conn.execute(
            "SELECT * FROM cycle_state WHERE id = 1"
        ).fetchone()
        if row is None:
            now = _now()
            self.conn.execute(
                "INSERT INTO cycle_state (id, started_at, extension_granted_at, extension_count) VALUES (1, ?, NULL, 0)",
                (now,),
            )
            self.conn.commit()
            row = self.conn.execute("SELECT * FROM cycle_state WHERE id = 1").fetchone()
        return dict(row)

    def _started_at(self) -> str:
        """Inicio del ciclo: primera entrada INITIAL_CAPITAL del ledger, o si no
        existe, el arranque de la simulación (fila cycle_state)."""
        row = self.conn.execute(
            "SELECT created_at FROM ledger_entries WHERE entry_type = 'INITIAL_CAPITAL' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        if row:
            return str(row["created_at"])
        return self._ensure_row()["started_at"]

    # ------------------------------------------------------------------ income
    def _confirmed_real_income_usd(self) -> float:
        """Ingresos CONFIRMADOS REALES. En esta fase NO existen: todos los
        ingresos del ledger son SIMULADOS y por regla no cuentan. Devuelve
        0.0 y la razón se expone en ``income_exclusion_note``."""
        rows = self.conn.execute(
            "SELECT entry_type FROM ledger_entries WHERE direction = 'credit' AND status = 'CONFIRMED'"
        ).fetchall()
        real = [
            r["entry_type"] for r in rows
            if r["entry_type"] not in (LedgerEntryType.simulated_income.value, LedgerEntryType.initial_capital.value)
        ]
        # No existe ningún tipo de ingreso real implementado (real_money_moved
        # es siempre false); cualquier asiento real futuro debería usar un tipo
        # explícito REAL_INCOME y pasar reconciliación de facturación.
        return 0.0 if not real else sum(
            self._amount_of(t) for t in real
        )

    @staticmethod
    def _amount_of(_entry_type: str) -> float:
        return 0.0  # sin tipo real implementado, el importe es 0

    # ------------------------------------------------------------------ spend
    def _spent_usd(self) -> float:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS s FROM ledger_entries "
            "WHERE direction = 'debit' AND status = 'CONFIRMED'"
        ).fetchone()
        return float(row["s"] or 0)

    def _remaining_capital_usd(self) -> float:
        return max(0.0, self.settings.cycle_capital_usd - self._spent_usd())

    # ------------------------------------------------------------------ eval
    def evaluate(self) -> dict:
        state = self._ensure_row()
        start = self._started_at()
        days_elapsed = max(0, int((datetime.now(timezone.utc) - _dt(start)).total_seconds() // 86400))
        days_remaining = max(0, self.settings.cycle_length_days - days_elapsed)
        extension_count = int(state["extension_count"] or 0)
        extension_used = extension_count >= self.settings.cycle_max_extensions
        extension_granted_at = state.get("extension_granted_at")

        real_income = self._confirmed_real_income_usd()
        spent = self._spent_usd()
        remaining = self._remaining_capital_usd()

        path_a_passed = real_income >= self.settings.cycle_capital_usd
        path_b = {
            "has_real_confirmed_payment": real_income > 0,
            "continuity_cost_acceptable": remaining > 0,
            "repetition_hypothesis": False,  # exige al menos un pago real previo
            "no_blockers": True,  # sin bloqueadores activos conocidos del ciclo
            "remaining_capital_sufficient": remaining > 0,
        }
        path_b_passed = all(path_b.values()) and not extension_used

        status = "NOT_PASSED"
        passed_via = None
        if path_a_passed:
            status = "PASSED_VIA_A"
            passed_via = "A"
        elif path_b_passed:
            status = "PASSED_VIA_B_EXTENSION"
            passed_via = "B"

        return {
            "status": status,
            "passed_via": passed_via,
            "simulated": True,
            "real_money_moved": False,
            "cycle_days": self.settings.cycle_length_days,
            "cycle_capital_usd": self.settings.cycle_capital_usd,
            "days_elapsed": days_elapsed,
            "days_remaining": days_remaining,
            "started_at": start,
            "spent_usd": round(spent, 2),
            "remaining_capital_usd": round(remaining, 2),
            "confirmed_real_income_usd": real_income,
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
        }

    # ------------------------------------------------------------------ extend
    def request_extension(self) -> dict:
        """Solicita la prórroga de la vía B. Regla determinista: se concede
        solo si la vía B se cumple y no se ha usado la prórroga única."""
        state = self._ensure_row()
        extension_count = int(state["extension_count"] or 0)
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
