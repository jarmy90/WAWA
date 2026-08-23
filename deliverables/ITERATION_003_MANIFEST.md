# Manifiesto de iteración 003

- **Identificador de iteración**: 003
- **Fecha y hora**: 2026-08-23 (fecha de entrega; hora exacta en el historial)
- **Objetivo**: implementar la capa completa de **contabilidad económica
  SIMULADA y auditable** (ledger append-only, idempotencia, reversiones,
  métricas deterministas, reconciliación), el estado previo `PRODUCTION_ARMED`,
  la regla explícita de capacidad de producción y el panel económico con el
  huevo reaccionando al estado de supervivencia. Sin dinero real.
- **Estado**: `entregado`

## Resumen de cambios

- **Implementado**: ledger append-only (`ledger_entries`), idempotencia por
  clave, reversiones vinculadas con doble reversión bloqueada, flujo
  request→committed→confirmed/rejected, métricas deterministas (runway, burn
  rate, coste por oportunidad/experimento, margen, budget utilization,
  survival status), reconciliación con entrada automática en `SAFE_PAUSE`,
  `PRODUCTION_ARMED` (estado previo que una variable de entorno puede alcanzar
  como máximo), regla de capacidad (`production_capability_available=false`)
  que bloquea AUTONOMOUS_PRODUCTION, arranque seguro ante configuraciones
  inconsistentes y endpoints `/api/economy/*` con `simulated:true` /
  `real_money_moved:false`.
- **Probado automáticamente**: 125 tests (91 previos + 30 de economía + 4
  nuevos de modos), todos superados.
- **Verificado manualmente**: 17/17 comprobaciones en vivo (flujo completo,
  persistencia tras reinicio, límite diario, reconciliación, SAFE_PAUSE sin
  capital, gasto bloqueado en pausa).
- **Simulado**: toda la economía (por diseño).
- **Pendiente**: ejecución financiera real (requiere iteración futura
  auditada); producción desactivada por capacidad.

## Archivos

- **Nuevos**:
  - `app/models/ledger.py` (LedgerEntry + contratos API)
  - `app/repositories/ledger.py` (LedgerRepository)
  - `app/services/economy.py` (EconomyService)
  - `docs/ECONOMY.md`, `docs/LEDGER.md`, `docs/RECONCILIATION.md`
  - `tests/test_economy.py` (30 tests)
  - `deliverables/ITERATION_003_MANIFEST.md` (este)
- **Modificados**:
  - `app/models/enums.py` (PRODUCTION_ARMED, LedgerEntryType/Status/Direction,
    SurvivalStatus)
  - `app/core/config.py` (base_currency, capacidad de producción, umbrales
    survival, economía)
  - `app/repositories/db.py` (tablas ledger_entries + reconciliation_runs)
  - `app/repositories/__init__.py`, `app/services/__init__.py`
  - `app/services/engine.py` (PRODUCTION_ARMED, arranque seguro, safe_pause)
  - `app/services/budget.py` (integración con economía)
  - `app/core/container.py` (EconomyService)
  - `app/api/routes.py` (endpoints /api/economy/*)
  - `frontend/index.html`, `frontend/styles.css`, `frontend/app.js` (sección
    económica + huevo por survival)
  - `tests/test_engine_modes.py` (semántica de capacidad)
  - `README.md`, `AGENTS.md`, `docs/OPERATING_MODES.md`,
    `docs/AUTONOMOUS_PRODUCTION.md`, `docs/ARCHITECTURE.md`,
    `docs/SECURITY.md`, `docs/ITERATION_HISTORY.md`
- **Eliminados**: ninguno.

## Cambios

- **Arquitectura**: nueva capa `EconomyService` (ledger) conectada a
  `BudgetGuard` (modo → capacidad → saldo → límites → asiento COMMITTED) y al
  motor (SAFE_PAUSE ante inconsistencias).
- **Modelos de datos**: 2 tablas nuevas (`ledger_entries` con
  `idempotency_key` UNIQUE e importes como TEXT; `reconciliation_runs`).
  Esquema con `CREATE TABLE IF NOT EXISTS`: compatible con bases de
  iteraciones anteriores, sin borrar datos.
- **Reglas económicas**: Decimal estricto (ROUND_HALF_UP), sin negativos,
  moneda única, capital ≠ ingreso ganado, reversiones neutras, desconocido ≠
  0. Documentadas en `docs/ECONOMY.md`.
- **Seguridad**: nueva regla de capacidad de producción; arranque seguro →
  `SAFE_PAUSE`; ledger append-only; toda respuesta económica etiquetada como
  simulada.
- **Presupuesto**: BudgetGuard consulta saldo disponible, comprometidos y
  límites del ledger antes de autorizar gasto.
- **Dependencias**: ninguna añadida ni retirada.

## Comandos

- **Instalar**: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- **Ejecutar**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Probar**: `pytest`
- **Empaquetar**: `python3 scripts/package_for_review.py --iteration 3`
- **Verificar**: `python3 scripts/verify_review_package.py`

## Pruebas

- **Resultado exacto**: 125 passed, 0 failed.
- **Comandos usados**: `python3 -m pytest tests/ -q --tb=short` (múltiples
  ejecuciones durante la iteración).
- **Comprobaciones manuales**: script de validación en vivo (uvicorn real,
  3 arranques): flujo económico completo por HTTP, idempotencia, límite
  diario (429), métricas (saldo 62.0), persistencia tras reinicio,
  reconciliación OK, arranque `production_armed` sin capital → SAFE_PAUSE con
  evento crítico, operaciones bloqueadas en pausa (409). Resultado: 17/17.

## Problemas conocidos / limitaciones / riesgos

- **Problemas conocidos**: ninguno bloqueante. Durante la iteración se
  corrigieron tres hallazgos reales: (1) las reversiones contaban dos veces en
  los agregados (REVERSAL sumado como ingreso y original excluido) — corregido
  excluyendo REVERSAL y tratando el capital como financiación, no ingreso;
  (2) el margen bruto contaba el capital como ingreso — corregido; (3) los
  endpoints HTTP de confirm/reject/reverse fallaban porque `Depends(valid_id)`
  no resolvía el parámetro `entry_id` — corregido con `valid_entry_id` y
  cubierto con test de regresión.
- **Limitaciones**: la economía es 100% simulada; sin conversión de divisas;
  burn rate y runway se calculan con historial real del ledger (no se
  inventan); el panel económico es v1 (sin exportación CSV ni gráficas).
- **Riesgos abiertos**: la ejecución financiera real no existe (bloqueada por
  capacidad); ver `docs/ROADMAP.md`.
- **Deuda técnica**: `sum_by` recorre asientos en Python (suficiente para el
  MVP; migrar a agregados SQL si el volumen crece); `mode_transitions`
  reutilizada para estados del motor.

## Revisión externa

- **Elementos que debe supervisar el revisor**:
  - Reglas contables: capital vs ingreso ganado, reversiones neutras,
    estados PENDING/COMMITTED/CONFIRMED/REJECTED/REVERSED y su efecto en
    saldos.
  - Reconciliación y entrada automática en SAFE_PAUSE (incluido el arranque).
  - PRODUCTION_ARMED y la regla de capacidad (la variable de entorno nunca
    activa producción).
  - Endpoints económicos: `simulated:true` / `real_money_moved:false` en
    todas las respuestas.
  - Panel económico y reacción del huevo al survival status.
- **Próxima acción recomendada**: revisar el informe y el paquete 003; como
  siguiente iteración, conectar el BudgetGuard real al ledger para registrar
  costes de proveedor por oportunidad, o avanzar el gestor de experimentos con
  presupuesto vinculado al ledger.

## Paquete

- **Nombre del paquete**: autonomous-business-lab_iteracion-003_2026-08-23.zip.txt
- **Tamaño del paquete**: 181458 bytes
- **SHA-256 del paquete**: 2e93847f6db4d3425bcd7c1fac3efcc51e9dfef95f3220b0b8192ccc235b7ddc

## Git

- **Commit actual**: `598fcc0 Create REAME.MD` (solo el archivo previo; el
  proyecto vive en el Changes panel / commits de esta iteración).
- **Estado del repositorio**: ver sección Git del informe de la iteración.
- **git diff --stat**: ver informe de la iteración.
- **Archivos cambiados**: todos los listados arriba.
