# AUTONOMOUS_PRODUCTION (diseño de la fase final)

> **Estado: fase futura, desactivada y bloqueada por capacidad.** Esta fase no
> puede activarse (ver `docs/OPERATING_MODES.md`): ni una variable de entorno
> ni una clave bastan; existe una regla explícita
> (`production_capability_available=false`) porque la ejecución financiera
> real no está implementada ni verificada. Lo implementado hasta la iteración
> 003: mecanismo de modos (incluido `PRODUCTION_ARMED`), máquina de estados,
> guardas de presupuesto, timeline en vivo y **economía simulada auditada**
> (ledger append-only — ver `docs/ECONOMY.md`). Lo económico *real* y
> operativo de esta fase se describe aquí como diseño.

## Objetivo

Un sistema autónomo que:

- Investiga problemas y oportunidades de negocio.
- Recopila evidencias reales.
- Evalúa con criterios objetivos y critica sus propias hipótesis.
- Diseña pruebas comerciales económicas.
- Crea y mantiene productos o servicios digitales permitidos.
- Mide resultados reales; descarta lo que no funciona y escala con prudencia
  lo que demuestra demanda.
- Controla sus costes y administra un presupuesto limitado.
- Trabaja de forma continua, sin instrucciones rutinarias.
- Muestra toda su actividad en un panel visual.
- Produce ingresos legítimos si encuentra una oportunidad viable.
- Se pausa de forma segura si consume el capital operativo sin resultados
  suficientes.

Objetivo económico principal:

> “Obtener la máxima evidencia comercial y el máximo ingreso legítimo
> utilizando la menor cantidad posible del capital autorizado.”

El capital es un **límite máximo de riesgo**, no una obligación de gasto.

## Máquina de estados del motor (implementada)

Estados: `researching → validating → building → experimenting → earning →
optimizing → degraded → safe_pause → safe_shutdown`.

Cada transición se registra con: estado anterior, estado nuevo, fecha/hora,
motivo, evidencias, presupuesto consumido, ingresos, decisión y agente/regla
responsable (tabla `mode_transitions`, append-only). Las decisiones de
continuar/detener **no** las toma un LLM: las controlan reglas deterministas.

## Economía (iteración 003: simulada, implementada)

Desde la iteración 003 existe un **ledger contable append-only simulado** con
capital inicial, ingresos, gastos (request→committed→confirmed/rejected),
reversiones auditadas, idempotencia, métricas deterministas (runway, burn
rate, coste por oportunidad/experimento, margen, survival status) y
reconciliación con entrada automática en `SAFE_PAUSE` ante inconsistencias.
Toda la documentación en `docs/ECONOMY.md`, `docs/LEDGER.md` y
`docs/RECONCILIATION.md`. **Nada de ello mueve dinero real**: es la base
medible sobre la que, en una fase futura y auditada, podría construirse la
ejecución financiera real.

### Variables económicas (configurables; desactivadas por defecto)

Variables ya presentes en configuración (todas a 0/desactivadas salvo que el
propietario las defina):

```
capital_total_usd            # p. ej. 50 USD (límite máximo de riesgo)
reserve_intocable_usd        # p. ej. 15 USD (nunca se gasta)
operating_budget_usd         # p. ej. 35 USD
max_daily_spend_usd          # p. ej. 2 USD
max_per_experiment_usd       # p. ej. 8 USD
max_simultaneous_experiments # p. ej. 1
initial_cycle_days           # p. ej. 20 días (presión temporal medible)
report_period                # daily | weekly | monthly | disabled (default weekly)
alerts_mode                  # critical_only | all | disabled (default critical_only)
```

El sistema debe además disponer de: duración máxima de cada experimento,
pérdida máxima acumulada, ratio máximo costes/ingresos, política de
reinversión, condiciones para degradar modelos y condiciones para detener
gastos.

Al terminar el ciclo inicial se evalúa objetivamente: ingresos cobrados,
costes reales, beneficio/pérdida, evidencia de demanda, clientes reales,
experimentos completados, coste de adquisición, margen, probabilidad de
sostenibilidad y valor de los activos creados.

## SAFE_SHUTDOWN (implementado como estado; sin destrucción)

- Detiene nuevos gastos y experimentos.
- Conserva evidencias, productos, logs, balances y dashboard en modo lectura.
- Genera un informe final.
- **No** elimina claves, **no** transfiere fondos, **no** destruye el
  repositorio.

Una “muerte” irreversible (destrucción de claves/fondos/código) **solo** podrá
evaluarse en una fase futura, separada y auditada, y nunca antes de demostrar
que todo el sistema económico y de seguridad funciona correctamente.

## Criterios de candidatura a producción

Una versión es candidata a producción solo cuando:

1. Tests críticos superados.
2. Pruebas de seguridad superadas.
3. Pruebas presupuestarias superadas.
4. Verificación de recuperación ante fallos.
5. Prueba en modo simulación.
6. Prueba en shadow mode sin gasto.
7. Auditoría externa cerrada (vía el workflow de revisión).
8. Sin observaciones críticas pendientes.
9. Activación explícita del propietario, con
   `production_capability_available=true` (regla de capacidad).

## Autonomía sin Freebuff como dependencia de producción

Freebuff es la herramienta principal para **construir y mantener** el
repositorio. La ejecución 24/7 debe apoyarse en componentes controlables,
documentados y disponibles técnicamente (hosting Python + scheduler) — no se
inventa ninguna API de Freebuff (ver `docs/FREEBUFF_WORKFLOW.md`).

## Trabajo pendiente para completar esta fase (lista honesta)

- [x] Contabilidad simulada auditada: ledger append-only, idempotencia,
      reversiones, métricas y reconciliación (iteración 003; ver
      `docs/ECONOMY.md`).
- [ ] Bucle económico **real**: ejecución financiera verificada (requiere
      iteración futura separada y auditada; mientras tanto
      `production_capability_available=false`).
- [ ] Conectores de investigación autorizados (robots.txt/ToS).
- [ ] Gestor de experimentos con presupuesto, duración y métricas.
- [ ] Scheduler 24/7 (hosting + cron) y heartbeat persistente.
- [ ] Panel completo con economía, trabajo realizado y salud técnica
      (el huevo vivo actual es la v1 visual).
- [ ] Integración de pagos **solo** tras aprobación explícita por iteración.
- [ ] Política de reinversión y degradación de modelos por coste.
- [ ] Informes periódicos (diario/semanal/mensual) configurables.
