# MANIFIESTO ITERACIÓN 010 — CIERRE END-TO-END, PRE_CYCLE Y PRIMERA CAMPAÑA REAL

- **Iteración**: 010
- **Fecha**: 2026-08-23
- **Estado**: COMPLETADA
- **Objetivo**: dejar Autonomous Business Lab utilizable desde una única web
  (`/`), corregir el inicio involuntario del ciclo económico (PRE_CYCLE),
  añadir un orquestador end-to-end auditable y preparar la PRIMERA CAMPAÑA
  REAL 001 (diversa, sin ventaja MQL5/trading, sin inventar evidencia).

## Resumen de cambios

### Corrección crítica: PRE_CYCLE (sección 2 del encargo)

- `cycle_state.started_at` admite NULL (migración idempotente).
- `GET /api/economy/cycle` ya **no inicia el reloj** (abrir la web, crear
  campañas, generar ideas, investigar o entrar al comité no arranca el ciclo).
- Estado inicial obligatorio: `PRE_CYCLE` con
  `{status, clock_running:false, started_at:null, days_elapsed:0,
  days_remaining:30, cycle_capital_usd:50, confirmed_real_income_usd:0,
  real_money_moved:false}`.
- Nuevo `POST /api/economy/cycle/start`: explícito, determinista, idempotente,
  auditable y bloqueado si faltan precondiciones (12): oportunidad
  seleccionada, experimento aprobado, oferta concreta, precio, comprador,
  canal autorizado, métrica de éxito, condición de abandono, método de
  confirmación de pago, sin bloqueadores críticos, producción bloqueada y
  activación deliberada del propietario. Respuesta de rechazo:
  `started:false, status:PRE_CYCLE, missing_conditions, next_action,
  clock_running:false`.
- Contradicción eliminada: `initial_cycle_days=20` vs `cycle_length_days=30`
  → única fuente `cycle_length_days=30`; `initial_cycle_days` deprecado,
  fijado a 30 y con prueba de divergencia.

### Orquestador end-to-end (sección 4-5)

- `app/models/orchestrator.py` + `app/repositories/orchestrator.py` +
  `app/services/orchestrator.py`: `CampaignOrchestrator` interno que coordina
  servicios EXISTENTES (DiscoveryService, PipelineService, ReviewService,
  CycleEvaluator, repositorios, BudgetGuard). No es un microservicio ni
  duplica servicios.
- Estados auditados: CAMPAIGN_CREATED → DISCOVERING → DEDUPLICATING →
  FILTERING_COMMODITIES → STRUCTURAL_ANALYSIS → RECOMBINING → SHORTLISTING →
  TOURNAMENT → RESEARCH_PLANNED → RESEARCH_PENDING → RESEARCH_IMPORTED →
  REEVALUATING → CANDIDATES_READY → FINALISTS_READY → COMMITTEE_READY →
  COMMITTEE_PENDING → COMMITTEE_COMPLETED → DECIDING → EXPERIMENT_READY /
  EXPERIMENT_BLOCKED → PRE_CYCLE → READY_TO_START_CYCLE → COMPLETED (+
  PAUSED / FAILED / CANCELLED).
- Cada transición registra: timestamp, estado anterior/siguiente, actor,
  motivo, entradas, salidas, conceptos considerados/rechazados, coste
  (real/estimado/desconocido), errores, bloqueadores, siguiente acción,
  `owner_action_required`, datos sintéticos o reales.
- `advance()` resumible (no repite fases completadas) y se detiene
  honestamente en `RESEARCH_PENDING` si el entorno no puede investigar en
  web: **no inventa evidencia para continuar**.
- Acciones: INICIAR CAMPAÑA REAL (crea la ejecución + campaña y avanza),
  pausar, reanudar, avanzar hasta el próximo bloqueo, cancelar, exportar,
  preparar investigación, pegar investigación.

### PRIMERA CAMPAÑA REAL 001 (sección 6)

- Título: PRIMERA CAMPAÑA REAL 001 · tipo `real_market_discovery`.
- Config: 60 conceptos iniciales → máx. 30 tras dedup → máx. 15 tras filtro
  IA/commodity → máx. 6 candidatas a investigación → máx. 3 finalistas →
  máx. 1 experimento · máx. 10 USD · 5 días de construcción · objetivo de
  primer pago en 10 días · sin publicidad pagada, spam, trading ni servicios
  financieros/sanitarios regulados · sin prometer rentabilidad · sin construir
  una plataforma antes de validar pago.
- Territorios diversos; **sin ventaja** para MQL5/trading/MetaTrader/
  Quantora/inmobiliario/sectores del propietario (compiten sin preferencia).

### Investigación Freebuff-first (secciones 7-8)

- Misiones por candidata: DEMAND_REALITY_CHECK, BUYER_BUDGET_CHECK,
  CURRENT_ALTERNATIVE_CHECK, GENERAL_AI_SUBSTITUTION_CHECK,
  COMPETITOR_EQUIVALENT_SEARCH, DISTRIBUTION_ACCESS_CHECK,
  MOAT_REALITY_CHECK, DATA_AVAILABILITY_CHECK, TOS_AND_LEGAL_CHECK,
  EXPERIMENT_FEASIBILITY_CHECK (export Markdown + JSON).
- Endpoint `GET /orchestrator/runs/{id}/missions` con el Markdown listo para
  copiar; `POST /orchestrator/runs/{id}/import-research` para pegar la
  respuesta (asociada a la misión; solo cuenta como evidencia con URL +
  fecha + fragmento; texto libre se guarda como nota sin inventar evidencia).
- Reevaluación automática tras importar (sin botón): validar campos,
  deduplicar, clasificar evidencias, actualizar comprador/competidores/
  precios/canal, Compliance, Skeptic, Judge, Venture Quality Score, registrar
  diferencias y continuar el orquestador.

### Exportaciones (sección 9)

- `app/services/campaign_exports.py`: CSV (una fila por idea, 30+ columnas
  incluyendo passed_dedup/passed_ai_filter/rejection_stage/rejection_reason/
  synthetic_or_real), JSON completo, Markdown legible (embudo, ideas,
  descartadas con motivo, shortlist, candidatas, finalistas, comparación,
  recomendación, evidencias pendientes, próximo paso), finalistas MD y
  paquete de investigación `.zip`. Las ideas descartadas no se ocultan.
- Endpoints: `GET /orchestrator/runs/{id}/exports/{csv|json|md|finalists|research_zip}`.

### Panel (secciones 10-15)

- Pestañas: Oportunidades · Descubrimiento · Laboratorio · **Campaña real** ·
  **Ideas** · Campañas.
- Campaña real: estado del embudo, próxima acción, intervención del
  propietario, misiones con **Copiar misión**, cuadro **Pegar investigación**,
  comité y plan de experimento.
- Ideas: filtros (todas/activas/descartadas/commodity/shortlist/finalistas/
  en investigación) + tarjetas (título, problema, comprador, estado, Venture
  Score, clasificación IA, motivo) + descargas CSV/MD/JSON/finalistas/zip.
- Scripts locales: `start_wawa.sh`, `stop_wawa.sh`, `START_WAWA.bat`,
  `STOP_WAWA.bat` (venv, deps, SQLite, uvicorn en 127.0.0.1:8000, espera de
  /api/health, apertura de navegador, sin 0.0.0.0, sin imprimir secretos) y
  `COMO_ABRIR_WAWA.md` con instrucciones sencillas.

### Seguridad local (sección 16)

- CORS por defecto restringido a `http://127.0.0.1:8000` /
  `http://localhost:8000` (`settings.cors_origins`).
- Panel solo en 127.0.0.1; documentado que exponer a Internet requiere
  auth/TLS/rate limiting.
- Test de escape XSS: ejecuta la `esc()` real de `frontend/app.js` con
  contenido hostil y verifica que no llega `<img`/`<script>`/`onerror` a
  `innerHTML`.

### Trazabilidad del paquete 009 (sección 17)

- Sección nueva en `docs/ITERATION_HISTORY.md`: artefacto anterior
  (413955 bytes / `87351f49…`) marcado **SUPERSEDED**; artefacto final
  auditado (414022 bytes, canónico `0cb0a09d…`, binario completo
  `9618cba1…`, commit `7307e1f`, verificación 15/15). Nada se borra.

## Archivos nuevos

- `app/models/orchestrator.py`
- `app/repositories/orchestrator.py`
- `app/services/orchestrator.py`
- `app/services/campaign_exports.py`
- `tests/test_orchestrator_010.py` (12 tests: PRE_CYCLE no inicia reloj,
  cycle/start con precondiciones, orquestador end-to-end, reanudación sin
  repetir fases, RESEARCH_PENDING honesto, exportaciones, escape XSS,
  divergencia initial_cycle_days, imposibilidad de autorizar gasto/ingreso)
- `start_wawa.sh`, `stop_wawa.sh`, `START_WAWA.bat`, `STOP_WAWA.bat`
- `COMO_ABRIR_WAWA.md`
- `deliverables/ITERATION_010_MANIFEST.md`

## Archivos modificados

- `app/core/config.py` (cors_origins, cycle_length_days=30, initial_cycle_days
  deprecado, revisión del ciclo, config de la primera campaña real)
- `app/repositories/db.py` (started_at NULL + migración, tablas orchestrator_runs,
  orchestrator_transitions, experiment_plans)
- `app/repositories/__init__.py`
- `app/core/container.py`
- `app/services/cycle.py` (reescrito: PRE_CYCLE, start con precondiciones)
- `app/services/discovery.py` (evaluate_structural público, export de misiones)
- `app/api/routes.py` (orchestrator start/detail/current/advance/pause/resume/
  cancel/import-research/missions/exports, economy/cycle/start)
- `app/main.py` (CORS restringido)
- `frontend/index.html`, `frontend/app.js` (pestañas Campaña real + Ideas,
  panel del orquestador, copiar misión, pegar investigación, descargas)
- `README.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/SECURITY.md`,
  `docs/ITERATION_HISTORY.md`

## Eliminados

Ninguno.

## Validación

- **283 tests** pasan (271 previos + 12 nuevos): `python3 -m pytest tests/`
- `node --check frontend/app.js` OK
- Validación en vivo (TestClient con base temporal): PRE_CYCLE sin reloj →
  `POST /orchestrator/start` → RESEARCH_PENDING con 66 conceptos y 30
  misiones → importación de respuesta pegada → exportaciones CSV/JSON/MD/
  finalists/research_zip → el reloj sigue parado tras todo el flujo.
- Producción autónoma sigue bloqueada; economía simulada intacta;
  `real_money_moved: false` en todas las respuestas.

## Qué debe revisar el supervisor

1. `app/services/cycle.py`: que el reloj solo arranca con `/cycle/start` y
   las 12 precondiciones (ninguna consulta lo inicia).
2. `app/services/orchestrator.py`: que no duplica servicios, que cada
   transición es auditable y que se detiene en RESEARCH_PENDING sin inventar
   evidencia.
3. `app/services/campaign_exports.py`: columnas del CSV y que las ideas
   descartadas no se ocultan.
4. `frontend/app.js` + `index.html`: vista Ideas y panel del orquestador.
5. `app/main.py` + `docs/SECURITY.md`: CORS restringido y política local.
6. Trazabilidad del paquete 009 en `docs/ITERATION_HISTORY.md`.

- **Nombre del paquete**: autonomous-business-lab_iteracion-010_2026-08-23.zip.txt

- **Tamaño del paquete**: 453498 bytes

- **SHA-256 del paquete**: 6af9ccc8088b126165ed3ff959cfdafeae4e73af3a160845c4cfb576ee7f2fb0
