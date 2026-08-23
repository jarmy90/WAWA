# Manifiesto de iteración 002

- **Identificador de iteración**: 002
- **Fecha y hora**: 2026-08-23 (fecha de entrega; hora exacta en el historial)
- **Objetivo**: incorporar al repositorio el workflow permanente del proyecto:
  modos de operación (DEVELOPMENT_AND_REVIEW → AUTONOMOUS_PRODUCTION),
  máquina de estados del motor, guardas de gasto, huevo vivo v1 en el panel,
  documentación del workflow de revisión externa y scripts de empaquetado +
  verificación de paquetes `.zip.txt`.
- **Estado**: `entregado`

## Resumen de cambios

Se añade el mecanismo inequívoco de selección de modo (`OperatingMode` +
`EngineState`) con persistencia, transiciones auditadas y guardas
deterministas que bloquean gastos en `safe_pause`/`shadow_mode`/`safe_shutdown`.
AUTONOMOUS_PRODUCTION está desactivado por defecto y exige clave de activación
o variable de entorno del propietario. Se implementa el timeline en vivo
(`engine_events`), el huevo vivo (orb CSS animado) en el dashboard, la
documentación permanente del workflow y los scripts de empaquetado y
verificación de paquetes. 91 tests, todos superados.

## Archivos

- **Nuevos**:
  - `docs/EXTERNAL_REVIEW_WORKFLOW.md`
  - `docs/OPERATING_MODES.md`
  - `docs/AUTONOMOUS_PRODUCTION.md`
  - `docs/ITERATION_HISTORY.md`
  - `deliverables/MANIFEST_TEMPLATE.md`
  - `deliverables/ITERATION_001_MANIFEST.md` (registro retroactivo)
  - `deliverables/ITERATION_002_MANIFEST.md` (este)
  - `scripts/package_for_review.py`, `scripts/verify_review_package.py`,
    `scripts/_review_common.py`
  - `app/models/engine.py`
  - `app/repositories/engine.py`
  - `app/services/engine.py`
  - `tests/test_engine_modes.py`
- **Modificados**:
  - `app/models/enums.py` (OperatingMode, EngineState, ReportPeriod, AlertsMode)
  - `app/core/config.py` (operating_mode, engine_activation_key, economía)
  - `app/core/errors.py` (ModeBlockedError)
  - `app/repositories/db.py` (tablas engine_state, mode_transitions, engine_events)
  - `app/repositories/__init__.py` (EngineRepository en Repos)
  - `app/core/container.py` (EngineService)
  - `app/services/budget.py` (guarda de modo)
  - `app/services/__init__.py`
  - `app/workflows/pipeline.py` (eventos de actividad por agente)
  - `app/api/routes.py` (endpoints de engine + health)
  - `frontend/index.html`, `frontend/styles.css`, `frontend/app.js` (huevo, tarjeta motor, feed)
  - `AGENTS.md`, `README.md` (resumen del workflow permanente)
- **Eliminados**: ninguno.

## Cambios

- **Arquitectura**: motor de operación (`EngineService`) con estado único
  persistido, transiciones y eventos; BudgetGuard conectado al motor.
- **Agentes/prompts**: sin cambios de prompts; el pipeline emite eventos de
  actividad por agente al timeline.
- **Scoring y reglas de decisión**: sin cambios en fórmulas (los bloqueadores
  económicos siguen en el Judge; las guardas de modo son otra capa).
- **Seguridad**: nueva guarda de modo (409) en pausa/apagado/sombra;
  activación de producción protegida con clave.
- **Presupuesto**: BudgetGuard ahora respeta el modo de operación antes de los
  límites clásicos.
- **Modelos de datos**: 3 tablas nuevas (`engine_state`, `mode_transitions`,
  `engine_events`).
- **Dependencias**: ninguna añadida ni retirada.

## Comandos

- **Instalar**: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- **Ejecutar**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Probar**: `pytest`
- **Empaquetar**: `python3 scripts/package_for_review.py --iteration 2`
- **Verificar**: `python3 scripts/verify_review_package.py`

## Pruebas

- **Resultado exacto**: 91 passed, 0 failed.
- **Comandos usados**: `python3 -m pytest tests/ -q --tb=short` (varias
  ejecuciones durante la iteración).
- **Comprobaciones manuales**: arranque real de uvicorn (iteración anterior,
  sin cambios de arranque); `node --check frontend/app.js`; ejecución del
  empaquetado y de la verificación (ver sección Paquete).

## Problemas conocidos / limitaciones / riesgos

- **Problemas conocidos**: ninguno bloqueante.
- **Limitaciones**: el huevo vivo es una v1 CSS (el panel completo de
  producción con economía, experimentos y salud técnica es trabajo pendiente
  documentado en `docs/AUTONOMOUS_PRODUCTION.md`); la detección de secretos
  cubre formatos reales de credenciales, no entropía genérica.
- **Riesgos abiertos**: la fase económica (ingresos/gastos reales) no está
  implementada; producción autónoma desactivada por diseño.
- **Deuda técnica**: `mode_transitions` reutiliza la tabla de transiciones
  para cambios de estado del motor (campo `decision` guarda el estado);
  aceptable para v1.

## Revisión externa

- **Elementos que debe supervisar el revisor**:
  - Reglas de activación de AUTONOMOUS_PRODUCTION (clave + entorno).
  - Guardas de gasto por modo (pausa/sombra/apagado) y su integración con el
    BudgetGuard.
  - Empaquetado: exclusiones, escaneo de secretos y verificación 15/15.
  - Experiencia del huevo vivo y del feed de actividad.
- **Próxima acción recomendada**: probar el flujo completo de revisión (los
  scripts de paquete), revisar el informe de esta iteración y decidir la
  siguiente iteración (p. ej. contabilidad económica o conectores de
  investigación).

## Paquete

- **Nombre del paquete**: autonomous-business-lab_iteracion-002_2026-08-23.zip.txt
- **Tamaño del paquete**: 144746 bytes
- **SHA-256 del paquete**: 3e4a0ac6341a8887170c8b7966f1a4d46a31932bbe4118bb0f389ed50b6a2af0

## Git

- **Commit actual**: `598fcc0 Create REAME.MD` (solo el archivo previo)
- **Estado del repositorio**: 13 entradas sin trackear (todo el proyecto),
  listo para revisión en el Changes panel de Freebuff.
- **git diff --stat**: sin cambios sobre HEAD (archivos sin trackear).
- **Archivos cambiados**: todos los listados arriba (nuevos/modificados,
  sin commitear).
