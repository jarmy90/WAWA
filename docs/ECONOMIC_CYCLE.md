# Ciclo económico inicial (iteración 009)

## Reglas

- **Ciclo inicial**: 30 días y 50 USD de capital máximo (configurables:
  `cycle_length_days`, `cycle_capital_usd`).
- **Vía A**: ingresos **confirmados reales** acumulados >= 50 USD.
- **Vía B**: al menos **un pago real confirmado** + coste de continuidad
  aceptable + hipótesis de repetición + ausencia de bloqueadores + capital
  restante suficiente ⇒ concede **una prórroga de 14 días** (solo una vez;
  `cycle_extension_days`, `cycle_max_extensions`).
- **NO cuentan**: visitas, likes, registros gratuitos, promesas, facturas no
  cobradas, **ingresos simulados**, capital aportado por el propietario,
  opiniones de modelos.

## Implementación (determinista, sin LLM)

`app/services/cycle.py` → `CycleEvaluator`:

- `GET /api/economy/cycle` → estado del ciclo.
- `POST /api/economy/cycle/extend` → solicita la prórroga (vía B).

El estado de prórroga persiste en `cycle_state` (fila única, append-only):
la concesión queda auditada y solo puede ocurrir **una vez por ciclo**.

## Honestidad en la iteración 009

En esta fase **no existe ejecución financiera real** (`real_money_moved=false`
en todas las respuestas; no hay pagos, wallets ni integraciones bancarias).
Por lo tanto:

- `confirmed_real_income_usd = 0` (los ingresos del ledger son SIMULADOS y por
  regla no cuentan; cualquier ingreso real futuro requeriría un tipo explícito
  `REAL_INCOME` y reconciliación de facturación).
- El ciclo devuelve **`NOT_PASSED`** con la razón concreta de cada condición.
- `request_extension` se rechaza ("requiere al menos un pago real confirmado")
  y un intento rechazado **no consume** el cupo único.

Nunca se presenta el ciclo como superado ni se concede la prórroga sin la
evidencia real exigida. Esto es el comportamiento correcto y deseado hasta que
exista una vía de pago real verificada (fase futura, auditada).
