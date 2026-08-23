# Reconciliación contable

> **Estado: implementado (simulado).** La reconciliación comprueba la
> consistencia interna del ledger y, ante una inconsistencia grave, entra en
> `SAFE_PAUSE` de forma auditada.

## Qué comprueba

`EconomyService.reconcile()` (endpoint `POST /api/economy/reconcile`):

1. **Importes inválidos** — asientos con importe negativo o no cuantificable.
2. **Duplicados de idempotencia** — la misma `idempotency_key` en asientos
   distintos (debería ser imposible por la UNIQUE de SQLite; se detecta por si
   acaso).
3. **Reversiones inconsistentes** — `REVERSAL` sin original, o un original
   marcado `REVERSED` sin su asiento de reversión.
4. **Referencias inexistentes** — `opportunity_id`/`experiment_id` que no
   existen en sus tablas.
5. **Confirmaciones sin `confirmed_at`** — un asiento `CONFIRMED` sin marca de
   confirmación.

## Comportamiento

- Reconstruye **desde cero** todos los saldos derivados a partir de los
  asientos (no confía en ninguna caché o snapshot).
- Guarda una fila en `reconciliation_runs` con `reconciled`, `issues`,
  `summary` (saldos reconstruidos) y `triggered_pause`.
- Si hay inconsistencia **grave** (negativos, idempotencia, reversiones o
  referencias rotas): llama a `engine.safe_pause(...)` con regla
  `reconciliation.grave_inconsistency`. Queda registrada una transición y un
  evento `critical`, y **todo gasto queda bloqueado**.
- No intenta auto-recuperarse activando producción.

## Arranque

`EngineService._startup_safety_check()` revisa el ledger al arrancar: si
existe cualquier inconsistencia, el sistema entra en `SAFE_PAUSE` con motivo
auditable (`rule=startup.safety_check`) y evento crítico. La comprobación es
idempotente: si el modo ya es `safe_pause`, no se repiten efectos.

## Endpoint manual

`POST /api/economy/reconcile` — respuesta de ejemplo:

```json
{
  "simulated": true,
  "real_money_moved": false,
  "run_id": 1,
  "reconciled": true,
  "issues": [],
  "triggered_pause": false,
  "summary": {
    "confirmed_income": "0.00",
    "confirmed_expenses": "0.00",
    "committed_expenses": "0.00",
    "accounting_balance": "100.00",
    "available_balance": "100.00",
    "entries": 1
  }
}
```

## Pruebas

- `tests/test_economy.py::test_reconciliation_ok` — ledger sano ⇒
  `reconciled=true`, sin pausa.
- `tests/test_economy.py::test_reconciliation_detects_inconsistency_and_pauses`
  — asiento huérfano inyectado ⇒ `reconciled=false`, `triggered_pause=true`,
  modo `safe_pause`, evento crítico.
- `tests/test_economy.py::test_startup_safe_pause_with_inconsistent_ledger` —
  ledger corrupto persistido ⇒ el arranque siguiente entra en `SAFE_PAUSE`.
