# Manifiesto de iteración 018

- **Identificador de iteración**: 018
- **Fecha y hora**: 2026-08-26 (ventana OX Alpha termina el 2026-08-27 inclusive)
- **Objetivo**: sprint de inteligencia OX Alpha: verificar la identidad del
  modelo sin inventar el slug, benchmark reproducible, super-torneo
  determinista sobre todo el universo de la campaña (0-3 candidatas), plan de
  investigación real, contrato Autonomous Launch y centro de mando operativo.
- **Estado**: `entregado`

## Resumen de cambios

Implementado y probado automáticamente: super-torneo determinista de 20
criterios (dedupe, brief obligatorio, máx. 3, 0 válido), benchmark OX Alpha
reproducible, centro de mando con APIs reales (endpoint + panel), contrato
Autonomous Launch, 30 tests nuevos (suite 367 passed), versión v0.17.0 /
iteración 018. Verificado manualmente: reproducción offline completa y
resultado del torneo (3 ganadoras con `is_not_evidence=true`). Simulado: nada
nuevo; la investigación inicial es PROVISIONAL (no eleva puntuaciones).
Pendiente: benchmark OX Alpha real (identidad `OX_ALPHA_UNVERIFIED`,
gateway desactivado) y aplicación del plan portable en la instalación del
propietario.

## Archivos

- **Nuevos**:
  - `app/scoring/super_tournament.py`
  - `app/services/super_tournament.py`
  - `app/scoring/ox_alpha_benchmark.py`
  - `app/services/command_center.py`
  - `scripts/run_super_tournament.py`
  - `scripts/benchmark_ox_alpha.py`
  - `frontend/ops18.js`
  - `tests/test_ox_alpha_sprint_018.py`
  - `tests/__init__.py`
  - `docs/AUTONOMOUS_LAUNCH.md`
  - `docs/TOOL_ANALYSIS_018.md`
  - `deliverables/ITERATION_018_MANIFEST.md`
  - `deliverables/ITERATION_018_REPORT.md`
  - `deliverables/operacion_super_torneo_2026-08-26/` (resultado del torneo,
    plan portable, benchmark, investigación inicial provisional)
- **Modificados**:
  - `app/core/container.py`
  - `app/api/routes.py`
  - `app/core/config.py` (v0.17.0)
  - `frontend/index.html` (v0.17.0 / 018 / vista Centro de mando)
  - `frontend/styles.css`
  - `docs/ITERATION_HISTORY.md`
- **Eliminados**: ninguno

## Cambios

- **Arquitectura**: módulos internos `scoring/super_tournament.py` y
  `services/command_center.py`; endpoint `GET /api/command-center`; sin
  workers ni microservicios (regla MVP).
- **Agentes/prompts**: ninguno (las tareas P0 de OX Alpha ya existían).
- **Scoring y reglas de decisión**: `super_tournament_score` nuevo, etiquetado
  `is_not_evidence=true`; puntuaciones y bandas existentes intactas.
- **Seguridad**: el centro de mando no expone claves (solo `configured`);
  `READY_TO_LAUNCH` bloqueado sin autorización única.
- **Presupuesto**: sin cambios de límites; gasto real 0 €; PRE_CYCLE detenido.
- **Modelos de datos**: ninguno (esquema SQLite intacto).
- **Dependencias**: ninguna.

## Comandos

- **Instalar**: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- **Ejecutar**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Probar**: `pytest`

## Pruebas

- **Resultado exacto**: `367 passed, 1 warning`
- **Comandos usados**: `python3 -m pytest`; `node --check frontend/app.js
  frontend/ops17.js frontend/ops18.js`; `python3 scripts/run_super_tournament.py`;
  `python3 scripts/benchmark_ox_alpha.py`
- **Comprobaciones manuales**: endpoint `/api/command-center` con y sin
  campaña; torneo con 9 entradas → 3 ganadoras; benchmark
  `OX_ALPHA_UNVERIFIED`; sintaxis JS OK.

## Problemas conocidos / limitaciones / riesgos

- **Problemas conocidos**: ninguno en la suite (0 fallos).
- **Limitaciones**: identidad OX Alpha no verificada (gateway desactivado);
  investigación inicial PROVISIONAL; el torneo usa la campaña local activa.
- **Riesgos abiertos**: 0 finalistas si no se importa evidencia verificada;
  las 3 candidatas tienen `evidence_backed_venture_score=0`.
- **Deuda técnica**: benchmark OX Alpha real pendiente; conector de escucha
  de foros en `BENCHMARK_FIRST`; persistir el torneo en tabla propia.

## Revisión externa

- **Elementos que debe supervisar el revisor**: resultado del super-torneo
  (¿3 o 0?), investigación PROVISIONAL, centro de mando (diferenciación de
  naturaleza de datos), contrato Autonomous Launch, política 50 €/100 €.
- **Próxima acción recomendada**: aplicar el plan portable en la instalación
  real y ejecutar las 6 misiones Fase 1 por candidata.

## Paquete

- **Nombre del paquete**: autonomous-business-lab_iteracion-018_2026-08-26.zip.txt
- **Tamaño del paquete**: 6824166 bytes
- **SHA-256 del paquete**: d44dccbd229895067b6ba508c7be46613a8cbf6f7d1f03f98298317fffd8388e
- **SHA-256 (archivo completo, referencia)**: e8dd8e26a936ba6b30f108355d55a942e915569f96c400a3700a569b713ea510
- **Verificación**: VÁLIDO (15/15, `scripts/verify_review_package.py`)

## Git

- **Commit actual**: pendiente de publicar (autorizado por la macrooperación)
- **Estado del repositorio**: cambios pendientes en el workspace
- **git diff --stat**: pendiente de generar en el commit
- **Archivos cambiados**: ver sección Archivos
