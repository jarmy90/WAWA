# Economía simulada (iteración 003)

> **Estado: implementado (simulado).** Nada de lo descrito aquí mueve dinero
> real: no hay wallet, pasarela de pago, banco ni cripto. Toda la economía es
> un **ledger contable simulado** con `simulated=true` y
> `real_money_moved=false` en cada respuesta y en cada asiento.

## Qué es

Una capa de contabilidad append-only que permite medir, con cifras
**deterministas y auditables**:

- Capital inicial simulado.
- Ingresos y gastos (confirmados, comprometidos, pendientes).
- Saldo contable y saldo disponible.
- Burn rate diario, runway estimado.
- Coste por oportunidad y por experimento.
- Margen bruto y uso del presupuesto.
- Estado de supervivencia (`survival_status`).

## Reglas contables (deterministas, sin LLM)

1. **Ledger append-only.** Los asientos (`ledger_entries`) nunca se editan ni
   se borran. El saldo se **deriva siempre** de los movimientos; no existe un
   saldo editable.
2. **Decimal, nunca float.** Importes redondeados a 2 decimales con
   `ROUND_HALF_UP`. Importes negativos rechazados: la dirección
   `debit`/`credit` determina el efecto.
3. **Idempotencia.** `idempotency_key` única (UNIQUE en SQLite). Reintentar la
   misma operación devuelve el asiento original (`created=false`), nunca un
   duplicado.
4. **Reversión.** Un movimiento confirmado se corrige creando una entrada
   `REVERSAL` vinculada (`reversed_entry_id`) y marcando el original como
   `REVERSED`. La doble reversión está bloqueada. El original permanece
   intacto (auditoría).
5. **Moneda única.** `base_currency` (USD por defecto). Una moneda distinta
   rechaza la operación explícitamente; no hay conversión automática.
6. **Distinción capital vs ingreso.** `INITIAL_CAPITAL` es financiación
   (métrica separada `initial_capital`); `confirmed_income` es **ingreso
   ganado** (pagos simulados de clientes, resultados de experimentos…).
7. **Reversiones neutras.** Los asientos `REVERSAL` no cuentan dos veces en
   los agregados: compensan al original (que, al pasar a `REVERSED`, deja de
   contar).
8. **Desconocido ≠ cero.** Si no hay historial o denominador, las métricas
   devuelven `null` con una `explanation` (p. ej. runway sin gastos
   confirmados). Nunca se muestra un infinito sin explicación.

## Estados de un asiento

`PENDING → COMMITTED → CONFIRMED | REJECTED → REVERSED`

| Estado | Saldo contable | Saldo disponible | Fondos comprometidos | Ingresos/gastos confirmados |
|---|---|---|---|---|
| `PENDING` | no | no | sí | no |
| `COMMITTED` | no | no (reduce disponible) | sí | no |
| `CONFIRMED` | sí | sí | no | sí |
| `REJECTED` | no | no | no | no |
| `REVERSED` | no | no | no | no |

## Tipos de asiento

`INITIAL_CAPITAL`, `SIMULATED_INCOME`, `SIMULATED_EXPENSE`, `API_COST`,
`INFRASTRUCTURE_COST`, `EXPERIMENT_COST`, `REFUND`, `REVERSAL`,
`MANUAL_ADJUSTMENT`.

## Métricas

`EconomyService.metrics()` devuelve cada métrica etiquetada con `value`,
`unit`, `data_quality` (`simulated`, `simulated_derived`, `unknown`) y una
`explanation` cuando el valor es `null`. Ninguna cifra se inventa.

Fórmulas:

- `accounting_balance = confirmed_capital + confirmed_income − confirmed_expenses`
- `available_balance = accounting_balance − committed_expenses`
- `burn_rate = confirmed_expenses / días_desde_el_primer_gasto_confirmado`
- `runway_days = available_balance / burn_rate` (solo con historial de gasto)
- `cost_per_opportunity = Σ gastos activos atribuidos / nº oportunidades activas`
- `gross_margin = (confirmed_income − confirmed_expenses) / confirmed_income`
  (solo si hay ingreso ganado; si no, `null`)
- `budget_utilization = (confirmed_expenses + committed) / initial_capital`

## Survival status

Clasificación determinista (sin LLM) con umbrales configurables
(`survival_watch_days=7`, `survival_critical_days=3`):

`UNKNOWN` (sin historial) · `HEALTHY` · `WATCH` · `CRITICAL` · `INSOLVENT` ·
`PAUSED`.

**`PAUSED` prevalece siempre**: si el modo es `safe_pause`, el estado
económico se muestra como pausado por encima de cualquier otra clasificación.

## API

Ver `docs/LEDGER.md` para los contratos y `docs/RECONCILIATION.md` para la
verificación. Endpoints:

- `GET /api/economy/status`
- `GET /api/economy/metrics`
- `GET /api/economy/ledger`
- `POST /api/economy/simulation/start`
- `POST /api/economy/income`
- `POST /api/economy/expense/request`
- `POST /api/economy/expense/{id}/confirm`
- `POST /api/economy/expense/{id}/reject`
- `POST /api/economy/ledger/{id}/reverse`
- `POST /api/economy/reconcile`

Todas las respuestas económicas incluyen `simulated: true` y
`real_money_moved: false`.

## Qué NO es esta capa

- No es dinero real, no hay saldos reales, no hay clientes reales.
- No hay integración bancaria, Stripe, wallets ni pagos en cripto.
- No hay ejecución de compras ni publicación automática.
- AUTONOMOUS_PRODUCTION sigue **bloqueado** (ver `docs/OPERATING_MODES.md`):
  la economía real requeriría una iteración futura separada y auditada.

## Implementado / simulado / pendiente

- **Implementado**: ledger, idempotencia, reversión, métricas, reconciliación,
  integración con BudgetGuard, panel económico, persistencia.
- **Simulado**: todos los movimientos (por diseño).
- **Pendiente**: ejecución financiera real, conversión de divisas, informes
  periódicos automáticos, conectores de pago.
