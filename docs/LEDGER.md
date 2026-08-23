# Ledger contable (append-only)

> **Estado: implementado (simulado).** El ledger registra movimientos
> económicos simulados; ningún movimiento toca dinero real.

## Modelo

`app/models/ledger.py` — `LedgerEntry` (contrato Pydantic estricto,
`extra="forbid"`):

| Campo | Descripción |
|---|---|
| `id` | uuid4 hex (32) |
| `entry_type` | `INITIAL_CAPITAL`, `SIMULATED_INCOME`, `SIMULATED_EXPENSE`, `API_COST`, `INFRASTRUCTURE_COST`, `EXPERIMENT_COST`, `REFUND`, `REVERSAL`, `MANUAL_ADJUSTMENT` |
| `direction` | `debit` (reduce saldo) / `credit` (aumenta saldo) |
| `amount` | `Decimal` ≥ 0, 2 decimales `ROUND_HALF_UP`; nunca float |
| `currency` | moneda base única (USD por defecto) |
| `status` | `PENDING`, `COMMITTED`, `CONFIRMED`, `REJECTED`, `REVERSED` |
| `source_type` | origen del movimiento (p. ej. `manual_simulation`, `simulated_customer_payment`, `economy_request`, `reversal`) |
| `opportunity_id` / `experiment_id` | atribución opcional (para coste por oportunidad/experimento) |
| `description` | motivo legible (3–2000 caracteres) |
| `evidence_reference` | referencia opcional a evidencia |
| `idempotency_key` | clave única de idempotencia (UNIQUE en BD) |
| `operating_mode` | modo en el que se creó el asiento |
| `created_by` | actor (`owner`, `economy`, `budget`, `system`, `human`…) |
| `created_at` / `confirmed_at` | marcas de tiempo ISO |
| `reversed_entry_id` | si es una reversión, id del asiento original |
| `metadata` | JSON seguro (máx. 4 KB); incluye `simulated: true`, `real_money_moved: false` |

Validación: importes negativos rechazados; `entry_type`/`status`/`direction`
restringidos a enumerados; moneda distinta de la base rechazada con mensaje
explícito; `metadata` limitada.

## Reglas de negocio (EconomyService)

- `start_simulation(SimulationStartIn)` — crea el capital inicial simulado.
  Solo en `development_and_review` o `simulation`. Idempotente por clave; si
  ya existe una simulación activa, **no reinicia** el ledger (409).
- `record_income(IncomeIn)` — ingreso simulado con `source_type` obligatorio
  (`simulated_customer_payment`, `imported_result`, `manual_simulation`,
  `experiment_outcome`) y `description` obligatoria.
- `request_expense(ExpenseRequestIn)` — flujo
  `validate_mode → validate_capability → validate_balance → validate_limits →
  crear asiento COMMITTED`. La confirmación ejecuta la acción simulada.
- `confirm_expense(id)` / `reject_expense(id)` — solo desde `COMMITTED`.
- `reverse_entry(id, reason, actor)` — solo desde `CONFIRMED`; crea el
  `REVERSAL` vinculado, marca el original `REVERSED`, bloquea dobles
  reversiones y reversiones de reversiones.

### Límites verificados en `request_expense`

1. Saldo disponible suficiente.
2. Límite diario (`maximum_daily_spend` de la simulación o
   `max_daily_spend_usd`).
3. Límite por oportunidad (`per_opportunity_budget_usd`).
4. Límite por experimento (`max_per_experiment_usd`).

Ninguna reserva/confirmación de gasto se hace porque un LLM lo haya pedido:
son reglas deterministas sobre el ledger.

## Integración con BudgetGuard

`BudgetGuard` consulta, en orden:

1. OperatingMode (guarda de modo: pausa/apagado/sombra/armado bloquean).
2. Capacidad de producción.
3. Saldo disponible (`economy.validate_funds`).
4. Límites diario/oportunidad/experimento.

Y registra los costes de API simulados como asientos `API_COST` confirmados
(`economy.record_api_cost`), de modo que el gasto en proveedores también queda
en el ledger.

## Persistencia

`app/repositories/ledger.py` + tablas en `app/repositories/db.py`:
`ledger_entries` (importes como TEXT para precisión Decimal) y
`reconciliation_runs`. El esquema se crea con `CREATE TABLE IF NOT EXISTS`:
compatible con bases de iteraciones anteriores, sin borrar datos.
