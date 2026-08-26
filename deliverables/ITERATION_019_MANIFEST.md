# Manifiesto de iteración 019

- **Identificador de iteración**: 019
- **Fecha y hora**: 2026-08-26 (corrección ejecutiva del Centro de mando)
- **Objetivo**: corregir cinco errores semánticos del Centro de mando para que
  ningún indicador transmita una conclusión más optimista de lo que permiten
  los datos reales: contrato explícito de launch readiness, independencia de
  evidencias solo con verificación completa, costes LLM con desconocidos
  separados de ceros, síntesis del comité separada de las revisiones y salud
  del sistema sin inferencias optimistas.
- **Estado**: `entregado`

## Resumen de cambios

Implementado y probado automáticamente (suite 367 passed): el readiness ya no
se infiere de la mera existencia de misiones — `READY_TO_CONNECT_SERVICES` exige
todas las precondiciones (candidata activa y válida, brief completo, Quality
Gate, decisión válida, experimento, oferta/precio hipótesis, comprador, canal,
métrica de éxito, condición de abandono, presupuesto autorizado, misiones
obligatorias de la candidata SELECCIONADA, sin deuda crítica ni bloqueadores) y
devuelve `readiness_state`, `readiness_met`, `readiness_missing`,
`readiness_blockers`, `candidate_id`, `opportunity_id`, `experiment_id` y
`explanation`. Las evidencias solo cuentan verificadas con URL http(s) + fecha
parseable + fragmento + asociación local válida, deduplicadas entre la tabla
`evidence` y los `mission_results` (materialización), con `evidence_total /
verified / unverified / rejected` separados y `max_evidence_score` dependiendo
únicamente de grupos verificados (nunca 3 URLs no verificadas elevan el tope).
Los costes LLM distinguen `reported_total` / `estimated_total` / `unknown_cost_calls`
/ `zero_cost_calls` / `cost_source` / `display_status`; un coste desconocido
NUNCA se convierte en cero (`cost_since` suma solo costes conocidos;
`cost_detail_since` expone el desglose y `reported_total`/`estimated_total`
son `None` si no hay llamadas de esa clase). Las misiones creadas desde
candidatas persisten `opportunity_id` en su `target` para que el readiness y el
resumen de evidencias solo usen misiones de la candidata seleccionada. Las
síntesis del comité se listan separadas de las revisiones. Versión v0.18.0 /
build 019-command-center-contract.

## Archivos

- **Nuevos**: ninguno.
- **Modificados**:
  - `app/services/command_center.py` (contratos de readiness, evidencias, costes, síntesis, salud)
  - `app/repositories/llm_calls.py` (`cost_since` honesto + `cost_detail_since`)
  - `app/repositories/reviews.py` (`list_syntheses`)
  - `app/services/discovery.py` (`create_mission` con `opportunity_id` trazable)
  - `app/services/orchestrator.py` (misiones con `opportunity_id` de la candidata)
  - `app/core/config.py` (v0.18.0)
  - `frontend/index.html` (v0.18.0 / 019 / build 019-command-center-contract)
  - `tests/test_ox_alpha_sprint_018.py` (sincronización de versión al nuevo vocabulario)
  - `deliverables/ITERATION_019_MANIFEST.md`, `deliverables/ITERATION_019_REPORT.md`
- **Eliminados**: ninguno

## Cambios

- **Arquitectura**: contrato explícito de readiness en `command_center.py`
  (sin LLM, determinista); misiones trazables a la candidata seleccionada.
- **Agentes/prompts**: ninguno.
- **Scoring y reglas de decisión**: `max_evidence_score` depende solo de
  evidencias verificadas completas; 3 URLs no verificadas nunca elevan el tope.
- **Seguridad**: sin cambios de superficie; ningún dato nuevo expuesto.
- **Presupuesto**: sin cambios de límites; gasto real 0 €; PRE_CYCLE detenido.
- **Modelos de datos**: sin cambio de esquema SQLite; `opportunity_id` se
  persiste dentro del JSON `target` de las misiones creadas desde candidatas.
- **Dependencias**: ninguna.

## Comandos

- **Instalar**: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- **Ejecutar**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Probar**: `pytest`

## Pruebas

- **Resultado exacto**: `367 passed, 1 warning in 26.70s`
- **Comandos usados**: `python3 -m pytest -q`; `python3 -m py_compile app/services/command_center.py app/repositories/llm_calls.py app/services/discovery.py app/services/orchestrator.py`
- **Comprobaciones manuales**: snapshot `/api/command-center` sin candidata ⇒
  `NOT_READY` con `readiness_missing` explícito; `cost_detail_since` con y sin
  llamadas; `reported_total=None` sin llamadas reportadas (no `0` falso).

## Problemas conocidos / limitaciones / riesgos

- **Problemas conocidos**: ninguno en la suite (0 fallos).
- **Limitaciones**: el vocabulario de estados del readiness incorpora
  `NOT_READY` (precondiciones ausentes) diferenciado de `BLOCKED` (bloqueadores
  duros); los tests históricos 018 esperaban el vocabulario anterior y se
  sincronizaron con la versión 019.
- **Riesgos abiertos**: sin candidata seleccionada el readiness permanece
  `NOT_READY`; las candidatas siguen con `evidence_backed_venture_score=0`
  hasta evidencias verificadas con URL+fecha+fragmento.
- **Deuda técnica**: la corrección visual (iteración 020) representará estos
  indicadores exactos.

## Revisión externa

- **Elementos que debe supervisar el revisor**: el contrato de readiness
  (¿faltan precondiciones?), el conteo de evidencias (deduplicación
  evidencia↔mission_results), el desglose de costes (desconocidos ≠ 0).
- **Próxima acción recomendada**: iteración 020 — telemetría de agentes y
  vistas visuales (Sistema Solar + Mission Control) sobre indicadores exactos.

## Paquete

- **Nombre del paquete**: autonomous-business-lab_iteracion-019_2026-08-26.zip.txt
- **Tamaño del paquete**: 6834827 bytes
- **SHA-256 del paquete**: 431dfafc4e40c8ab5729e887fc22fe1d433a8bd23bdbda9f5dc6304fdebc9818

## Git

- **Commit actual**: pendiente de publicar
- **Estado del repositorio**: cambios locales de la iteración 019 listos
- **git diff --stat**: 8 archivos modificados, 443 inserciones / 267 borrados
- **Archivos cambiados**: ver sección Archivos
