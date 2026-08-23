"""Repositorio del ledger contable (append-only).

- Los asientos confirmados nunca se editan ni se borran.
- idempotency_key UNIQUE en base de datos: reintentar devuelve el original.
- El saldo se calcula SIEMPRE desde los movimientos (nunca se persiste un
  saldo editable).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal

from app.core.errors import ConflictError
from app.models.enums import LedgerStatus
from app.models.ledger import LedgerEntry, money


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _row_to_entry(row: sqlite3.Row) -> LedgerEntry:
    data = dict(row)
    data["amount"] = money(Decimal(data["amount"]))
    data["metadata"] = json.loads(data.get("metadata") or "{}")
    return LedgerEntry.model_validate(data)


class LedgerRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ------------------------------------------------------------------
    def create(self, entry: LedgerEntry) -> tuple[LedgerEntry, bool]:
        """Inserta un asiento. Devuelve (entry, created).

        Si idempotency_key ya existe, devuelve el asiento original sin
        duplicar (created=False).
        """
        existing = self.get_by_idempotency(entry.idempotency_key)
        if existing is not None:
            return existing, False
        self.conn.execute(
            """INSERT INTO ledger_entries
               (id, entry_type, direction, amount, currency, status, source_type, source_id,
                opportunity_id, experiment_id, description, evidence_reference, idempotency_key,
                operating_mode, created_by, created_at, confirmed_at, reversed_entry_id, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.id,
                entry.entry_type,
                entry.direction,
                str(entry.amount),
                entry.currency,
                entry.status,
                entry.source_type,
                entry.source_id,
                entry.opportunity_id,
                entry.experiment_id,
                entry.description,
                entry.evidence_reference,
                entry.idempotency_key,
                entry.operating_mode,
                entry.created_by,
                entry.created_at,
                entry.confirmed_at,
                entry.reversed_entry_id,
                json.dumps(entry.metadata, ensure_ascii=False),
            ),
        )
        self.conn.commit()
        return entry, True

    def get(self, entry_id: str) -> LedgerEntry | None:
        row = self.conn.execute("SELECT * FROM ledger_entries WHERE id = ?", (entry_id,)).fetchone()
        return _row_to_entry(row) if row else None

    def get_by_idempotency(self, key: str) -> LedgerEntry | None:
        row = self.conn.execute("SELECT * FROM ledger_entries WHERE idempotency_key = ?", (key,)).fetchone()
        return _row_to_entry(row) if row else None

    def list(self, *, limit: int = 100, opportunity_id: str | None = None, experiment_id: str | None = None, status: str | None = None) -> list[LedgerEntry]:
        sql = "SELECT * FROM ledger_entries WHERE 1=1"
        params: list = []
        if opportunity_id:
            sql += " AND opportunity_id = ?"
            params.append(opportunity_id)
        if experiment_id:
            sql += " AND experiment_id = ?"
            params.append(experiment_id)
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)
        return [_row_to_entry(r) for r in self.conn.execute(sql, params).fetchall()]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS n FROM ledger_entries").fetchone()["n"]

    # ------------------------------------------------------------------
    def set_status(self, entry_id: str, status: LedgerStatus, *, confirmed_at: str | None = None) -> None:
        if status == LedgerStatus.confirmed and confirmed_at is None:
            confirmed_at = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE ledger_entries SET status=?, confirmed_at=COALESCE(?, confirmed_at) WHERE id=?",
            (status.value, confirmed_at, entry_id),
        )
        self.conn.commit()

    def set_reversed(self, entry_id: str) -> None:
        self.conn.execute(
            "UPDATE ledger_entries SET status=?, reversed_entry_id=? WHERE id=?",
            (LedgerStatus.reversed.value, entry_id, entry_id),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Agregados (siempre desde el ledger)
    # ------------------------------------------------------------------
    def sum_by(
        self,
        *,
        direction: str | None = None,
        statuses: list[str] | None = None,
        opportunity_id: str | None = None,
        experiment_id: str | None = None,
        exclude_types: list[str] | None = None,
    ) -> Decimal:
        """Suma en Decimal puro (nunca float): se recorren los asientos.

        ``exclude_types`` permite excluir tipos neutros para el saldo (p. ej.
        REVERSAL, que compensa el asiento original y no debe contar dos veces)."""
        rows = self.list(limit=100_000, opportunity_id=opportunity_id, experiment_id=experiment_id)
        total = Decimal("0")
        for entry in rows:
            if direction and entry.direction != direction:
                continue
            if statuses and entry.status not in statuses:
                continue
            if exclude_types and entry.entry_type in exclude_types:
                continue
            total += entry.amount
        return total

    def sum_today_debits(self, statuses: list[str]) -> Decimal:
        rows = self.list(limit=100_000)
        total = Decimal("0")
        for entry in rows:
            if entry.direction != "debit" or entry.status not in statuses:
                continue
            if entry.created_at.startswith(_today()):
                total += entry.amount
        return total

    def confirmed_debits_by_day(self) -> dict[str, Decimal]:
        """Gastos confirmados agrupados por día (para burn rate)."""
        rows = self.list(limit=100_000)
        by_day: dict[str, Decimal] = {}
        for entry in rows:
            if entry.direction != "debit" or entry.status != LedgerStatus.confirmed.value:
                continue
            day = (entry.confirmed_at or entry.created_at)[:10]
            by_day[day] = by_day.get(day, Decimal("0")) + entry.amount
        return by_day

    def has_initial_capital(self) -> bool:
        row = self.conn.execute(
            "SELECT id FROM ledger_entries WHERE entry_type = 'INITIAL_CAPITAL' LIMIT 1"
        ).fetchone()
        return row is not None

    # ------------------------------------------------------------------
    def add_reconciliation(self, *, reconciled: bool, issues: list[str], summary: dict, triggered_pause: bool) -> int:
        cur = self.conn.execute(
            """INSERT INTO reconciliation_runs (timestamp, reconciled, issues, summary, triggered_pause)
               VALUES (?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                int(reconciled),
                json.dumps(issues, ensure_ascii=False),
                json.dumps(summary, ensure_ascii=False, default=str),
                int(triggered_pause),
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def last_reconciliation(self) -> dict | None:
        row = self.conn.execute("SELECT * FROM reconciliation_runs ORDER BY id DESC LIMIT 1").fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "reconciled": bool(row["reconciled"]),
            "issues": json.loads(row["issues"] or "[]"),
            "summary": json.loads(row["summary"] or "{}"),
            "triggered_pause": bool(row["triggered_pause"]),
        }

    # ------------------------------------------------------------------
    def consistency_issues(self, *, check_references: bool = True) -> list[str]:
        """Escaneo read-only de consistencia (sin efectos secundarios)."""
        issues: list[str] = []
        entries = self.list(limit=100_000)
        by_id = {e.id: e for e in entries}
        seen_keys: dict[str, str] = {}

        for entry in entries:
            if entry.amount < 0:
                issues.append(f"Importe negativo en asiento {entry.id}")
            if entry.idempotency_key in seen_keys:
                issues.append(f"idempotency_key duplicada: {entry.idempotency_key}")
            else:
                seen_keys[entry.idempotency_key] = entry.id

        for entry in entries:
            if entry.entry_type == "REVERSAL":
                if not entry.reversed_entry_id or entry.reversed_entry_id not in by_id:
                    issues.append(f"REVERSAL {entry.id} referencia a entrada inexistente")
                else:
                    original = by_id[entry.reversed_entry_id]
                    if original.status != "REVERSED":
                        issues.append(f"REVERSAL {entry.id} pero el original {original.id} no está REVERSED")
            if entry.status == "REVERSED":
                has_reversal = any(e.reversed_entry_id == entry.id for e in entries)
                if not has_reversal:
                    issues.append(f"Entrada {entry.id} marcada REVERSED sin asiento de reversión")
            if entry.status == "CONFIRMED" and not entry.confirmed_at:
                issues.append(f"Entrada confirmada {entry.id} sin confirmed_at")

        if check_references:
            for entry in entries:
                if entry.opportunity_id:
                    row = self.conn.execute("SELECT id FROM opportunities WHERE id = ?", (entry.opportunity_id,)).fetchone()
                    if row is None:
                        issues.append(f"Entrada {entry.id} referencia oportunidad inexistente {entry.opportunity_id}")
                if entry.experiment_id:
                    row = self.conn.execute("SELECT id FROM experiments WHERE id = ?", (entry.experiment_id,)).fetchone()
                    if row is None:
                        issues.append(f"Entrada {entry.id} referencia experimento inexistente {entry.experiment_id}")
        return issues

    def duplicates_by_idempotency(self) -> list[str]:
        """Duplicados de idempotencia con contenido distinto (debería ser imposible)."""
        issues: list[str] = []
        entries = self.list(limit=100_000)
        by_key: dict[str, LedgerEntry] = {}
        for entry in entries:
            if entry.idempotency_key in by_key and by_key[entry.idempotency_key].id != entry.id:
                issues.append(f"idempotency_key repetida con distinto asiento: {entry.idempotency_key}")
            else:
                by_key[entry.idempotency_key] = entry
        return issues
