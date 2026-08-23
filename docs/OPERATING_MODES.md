# Modos de operación

El sistema tiene un **mecanismo inequívoco de selección de modo**. Los modos
nunca se mezclan y cualquier cambio queda auditado en `mode_transitions`
(append-only).

## Modos

| Modo | Valor | Comportamiento |
|---|---|---|
| Desarrollo y revisión | `development_and_review` | **Por defecto.** Iteración con supervisión externa, proveedor simulado, costes registrados. |
| Simulación | `simulation` | Ejecuta simulaciones explícitas con límites de presupuesto calculados pero sin bloquear. |
| Modo sombra | `shadow_mode` | Calcula decisiones sin gastar: **bloquea gasto real** (coste estimado > 0); permite operaciones de coste cero. |
| Producción armada | `production_armed` | (desde iteración 003) Estado **previo y preparado** que una variable de entorno puede alcanzar **como máximo**. Exige precondiciones económicas (capital > 0, moneda, presupuesto diario); bloquea gasto real. La **activación final** de producción sigue bloqueada por la regla de capacidad. |
| Producción autónoma | `autonomous_production` | **Desactivado por defecto y bloqueado por capacidad** (`production_capability_available=false`). Ni una variable de entorno ni una clave pueden activarlo en la iteración actual. |
| Pausa segura | `safe_pause` | **Bloquea gastos y experimentos.** Conserva datos, logs, balances y dashboard en modo lectura. Alcanzable desde cualquier modo. Reversible. |

Flujo de estados previos a producción:

`development_and_review → simulation → shadow_mode → production_armed →
autonomous_production`

`SAFE_PAUSE` puede alcanzarse desde **cualquier** modo.

El estado interno del motor (máquina de supervivencia) es independiente del
modo:

`researching → validating → building → experimenting → earning →
optimizing → degraded → safe_pause → safe_shutdown`

(ver `docs/AUTONOMOUS_PRODUCTION.md`). Cada transición de estado se registra
con: estado anterior, estado nuevo, fecha/hora, motivo, evidencias, presupuesto
consumido, ingresos, decisión y agente/regla responsable.

## Activación de AUTONOMOUS_PRODUCTION

Requisitos (todos deben cumplirse):

1. Tests críticos superados.
2. Pruebas de seguridad superadas.
3. Pruebas presupuestarias superadas.
4. Verificación de recuperación ante fallos.
5. Prueba en modo simulación.
6. Prueba en shadow mode sin gasto.
7. Auditoría externa cerrada.
8. Ausencia de observaciones críticas pendientes.
9. **Activación explícita del propietario.**

### Regla de capacidad (iteración 003)

AUTONOMOUS_PRODUCTION permanece **inaccesible** aunque se cumplan las
precondiciones: existe una regla explícita y auditable

```
production_capability_available = false
production_block_reason = "Real financial execution is not implemented or verified"
```

Una variable de entorno puede, **como máximo**, llevar al sistema a
`PRODUCTION_ARMED` (si las precondiciones económicas se cumplen). La
activación final exige además, en una iteración futura:

1. Tests críticos, de seguridad y presupuestarios superados.
2. Verificación de recuperación ante fallos; prueba en simulación y shadow.
3. Auditoría externa cerrada; sin observaciones críticas pendientes.
4. Activación explícita del propietario (clave `ENGINE_ACTIVATION_KEY` vía
   API, con `production_capability_available=true`).

### Arranque seguro

Si el sistema arranca con configuraciones inconsistentes (producción sin
capital, capital ≤ 0, moneda ausente, presupuesto diario inválido, ledger
inconsistente, producción no disponible, claves contradictorias), entra
**automáticamente en `SAFE_PAUSE`**: registra el motivo, crea un evento
crítico y una transición auditada, bloquea todo gasto, expone el problema por
API y **no intenta recuperarse activando producción por sí solo**.

La desactivación (reversión a `safe_pause` o a `development_and_review`) se
permite siempre y también queda auditada.

## Guardas deterministas (no LLM)

Las decisiones económicas importantes las controlan reglas verificables, no el
modelo de lenguaje:

- `safe_pause` (modo o estado) → bloquea cualquier gasto y evaluación.
- `safe_shutdown` (estado) → bloquea gasto y ejecución; modo lectura total.
- `shadow_mode` y `production_armed` → bloquean coste estimado > 0.
- `autonomous_production` → se rige por los límites económicos de
  `docs/AUTONOMOUS_PRODUCTION.md` (capital, reserva, gasto diario, etc.).

La economía simulada (ledger) también integra la guarda: en `safe_pause`
ninguna operación económica (simulación, ingreso, gasto, reversión) es
posible; en `shadow_mode`/`production_armed` las operaciones económicas están
bloqueadas (ver `docs/ECONOMY.md`).

La API expone:

- `GET /api/engine/status` — estado completo.
- `POST /api/engine/mode` — cambio de modo (con clave para producción).
- `POST /api/engine/heartbeat` — latido.
- `GET /api/engine/events` — timeline en vivo.
- `GET /api/engine/transitions` — auditoría de transiciones.

## Excepciones y alertas

“No molestar al propietario” no significa ocultar riesgos graves. Alerta
inmediata solo ante: posible robo de credenciales, riesgo de pérdida superior
al autorizado, comportamiento inesperado de pagos, incumplimiento legal o
regulatorio, bloqueo de cuenta crítica, corrupción de datos, fallo repetido
sin recuperación, vulnerabilidad crítica, intento de superar el presupuesto,
cambio no autorizado de wallet/destino de pagos, o acción irreversible no
contemplada.

Ante una excepción: bloquear solo la acción afectada, conservar las funciones
seguras, registrar todas las evidencias, pasar a `SAFE_PAUSE` si el riesgo
afecta al núcleo, emitir una única alerta clara (sin repetir la misma
notificación) y no improvisar soluciones financieras o legales.

Las notificaciones ordinarias se agrupan en resúmenes configurables
(`report_period`: daily/weekly/monthly/disabled; por defecto **weekly**) y
`alerts_mode` (por defecto `critical_only`).
