# Informe de iteración 019 — Corrección ejecutiva del Centro de mando (v0.18.0)

1. **Número de iteración**: 019.
2. **Objetivo**: corregir los errores semánticos del Centro de mando para que
   ningún indicador transmita una conclusión más optimista de lo que permiten
   los datos reales: (1) launch readiness solo con precondiciones demostradas;
   (2) independencia de evidencias solo con verificación completa; (3) costes
   desconocidos nunca convertidos en cero; (4) síntesis del comité separada de
   las revisiones; (5) salud del sistema sin inferencias optimistas. Sin
   reabrir la auditoría 018 y sin añadir decoración.
3. **Resumen del trabajo realizado**: `_launch_readiness()` ahora exige la
   candidata activa y válida (estado no rechazado/aplazado/bloqueado), brief
   completo validado, Quality Gate superado (coherencia + venture sin
   bloqueadores), decisión válida (`approved` / `SMALL_EXPERIMENT` /
   `PRIORITY_EXPERIMENT`), plan de experimento con oferta, precio > 0,
   comprador, canal, métrica de éxito, condición de abandono y presupuesto
   autorizado, y misiones obligatorias completadas SOLO de la candidata
   seleccionada (se ignoran misiones antiguas, canceladas, superseded o de
   otras candidatas). Se añaden bloqueadores económicos reales: deuda crítica
   (`survival_status` CRITICAL/INSOLVENT), ciclo económico fallido, problemas
   de reconciliación del ledger y `SAFE_PAUSE`. Devuelve `readiness_state`,
   `readiness_met`, `readiness_missing`, `readiness_blockers`, `candidate_id`,
   `opportunity_id`, `experiment_id` y `explanation`. `_evidence_summary()`
   solo cuenta evidencias que cumplen TODO: `verified=true`, URL http(s)
   concreta, fecha de consulta parseable, fragmento original no vacío y
   asociación local válida con una oportunidad; los duplicados entre la tabla
   `evidence` y los `mission_results` (materialización) se cuentan una sola
   vez; se separan `evidence_total / verified / unverified / rejected` y
   `independent_verified_groups` / `independent_unverified_groups`;
   `max_evidence_score` depende únicamente de grupos verificados (0 sin
   grupos, 40 con 1-2, 100 con ≥3): tres URLs no verificadas nunca elevan el
   tope. `_llm_summary()` usa `cost_detail_since()` que distingue coste real 0
   de coste desconocido NULL; `reported_total`/`estimated_total` son `None`
   cuando no hay llamadas de esa clase (no `0` falso); `cost_since()` suma solo
   costes conocidos (cota inferior honesta). Las misiones creadas desde
   candidatas persisten `opportunity_id` en `target` para trazabilidad local.
   `ReviewRepository.list_syntheses()` separa síntesis de revisiones. Suite
   367 passed; versión v0.18.0 / build 019-command-center-contract.
4. **Archivos nuevos**: ninguno.
5. **Archivos modificados**: `app/services/command_center.py`,
   `app/repositories/llm_calls.py`, `app/repositories/reviews.py`,
   `app/services/discovery.py`, `app/services/orchestrator.py`,
   `app/core/config.py` (v0.18.0), `frontend/index.html` (v0.18.0 / 019 /
   019-command-center-contract), `tests/test_ox_alpha_sprint_018.py`
   (sincronización de versión), `deliverables/ITERATION_019_MANIFEST.md`,
   `deliverables/ITERATION_019_REPORT.md`.
6. **Archivos eliminados**: ninguno.
7. **Decisiones técnicas**: (a) `READY_TO_CONNECT_SERVICES` solo con TODAS las
   precondiciones; el vocabulario distingue `NOT_READY` (faltan
   precondiciones) de `BLOCKED` (bloqueadores duros); `READY_TO_LAUNCH` sigue
   bloqueado hasta conectar y verificar servicios (producción bloqueada);
   (b) la deduplicación de evidencias usa clave estable
   `(opportunity_id, url, captured_at, excerpt)` para que la materialización en
   `evidence` + el raw en `mission_results` cuente una sola vez; (c) un coste
   desconocido es NULL, no 0: se informa `unknown_cost_calls` y `display_status`
   (`UNKNOWN` / `KNOWN_WITH_UNKNOWN_CALLS` / `KNOWN` / `NO_CALLS`); (d) la
   asociación misión→oportunidad se persiste en `target.opportunity_id` sin
   tocar el esquema SQLite (JSON); (e) las misiones de candidatas inactivas o
   superseded se excluyen del readiness y del resumen de evidencias.
8. **Dependencias añadidas o retiradas**: ninguna.
9. **Cambios en arquitectura**: contrato determinista de readiness y agregado
   de costes con completitud explícita; sin workers ni microservicios.
10. **Cambios en modelos de datos**: sin cambio de esquema; `opportunity_id`
    persistido en el JSON `target` de las misiones creadas desde candidatas.
11. **Cambios en prompts o agentes**: ninguno.
12. **Cambios en scoring y reglas de decisión**: `max_evidence_score` y
    `independent_verified_groups` derivan solo de evidencias verificadas
    completas; el tope no sube con URLs sin verificar.
13. **Cambios en seguridad o gestión presupuestaria**: sin cambios de
    límites; gasto real 0 €; PRE_CYCLE detenido; AUTONOMOUS_PRODUCTION
    bloqueado; el snapshot sigue sin exponer claves.
14. **Pruebas ejecutadas**: `python3 -m pytest -q` (suite completa 367),
    `python3 -m py_compile` sobre los módulos tocados.
15. **Comandos exactos utilizados**:
    - `python3 -m pytest -q`
    - `python3 -m py_compile app/services/command_center.py app/repositories/llm_calls.py app/services/discovery.py app/services/orchestrator.py`
16. **Número de pruebas superadas**: 367 (367 previas + 0 nuevas; 30 de 018
    ya cubrían el contrato y se sincronizaron al vocabulario nuevo).
17. **Número de pruebas fallidas**: 0.
18. **Errores encontrados y correcciones aplicadas**:
    - El snapshot podía lanzar excepción al leer `evaluation.decision` nulo:
      ahora se accede de forma tolerante y la ausencia de decisión añade
      `valid_decision_or_priority` a `readiness_missing`.
    - `cost_since()` usaba `COALESCE(..., 0)` y convertía costes desconocidos
      en cero en el agregado: ahora filtra solo costes conocidos y el desglose
      expone los desconocidos por separado.
    - El resumen de evidencias ignoraba los `mission_results` que no se
      materializan en la tabla `evidence`: ahora se incorporan solo con
      `opportunity_id` local válido y deduplicados.
    - Un mismo hallazgo se contaba dos veces (tabla `evidence` + raw de
      misión): deduplicación por clave estable.
    - Los tests históricos 018 esperaban `0.17.0`/018: sincronizados a
      v0.18.0/019 y al vocabulario `NOT_READY`.
19. **Comprobaciones manuales realizadas**: snapshot `/api/command-center` sin
    candidata ⇒ `readiness_state=NOT_READY` con la lista de precondiciones
    faltantes; `cost_detail_since` devuelve `reported_total=None` sin llamadas
    reportadas (no `0`); sintaxis de los módulos tocados OK.
20. **Funcionalidades no verificadas**: readiness completo con todas las
    precondiciones satisfechas (requiere candidata seleccionada con plan y
    misiones importadas); no se ejecutó ninguna campaña nueva en esta
    iteración (solo se corrigieron contratos).
21. **Elementos simulados o mock**: ninguno nuevo; la economía sigue simulada
    (`simulated=true`, `real_money_moved=false`).
22. **Dependencias de servicios externos**: ninguna obligatoria; todo corre
    offline.
23. **Limitaciones conocidas**: el readiness depende de la persistencia real
    de `target.opportunity_id` (misiones creadas ANTES de esta iteración sin
    ese campo se resuelven por `concept_id` equivalente); la deduplicación de
    evidencias usa la clave estable descrita (un fragmento reescrito a mano
    podría contar como evidencia nueva).
24. **Riesgos abiertos**: sin candidata seleccionada el readiness permanece
    `NOT_READY`; las candidatas actuales siguen con
    `evidence_backed_venture_score=0` y `proven_demand=0` hasta evidencias con
    URL+fecha+fragmento importadas.
25. **Deuda técnica**: la iteración 020 representará visualmente estos
    indicadores exactos (telemetría de agentes + Sistema Solar + Mission
    Control); persisten los pendientes de la 018 (benchmark OX Alpha real,
    slug verificado).
26. **Elementos concretos para el revisor externo**: (a) el contrato de
    readiness (¿faltan precondiciones aplicables?); (b) el conteo de
    evidencias con deduplicación y verificación estricta; (c) el desglose de
    costes (desconocidos ≠ 0, `reported_total=None` sin llamadas); (d) la
    separación síntesis/revisiones.
27. **Instrucciones de instalación y ejecución**: descomprimir el paquete,
    `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`,
    `uvicorn app.main:app --host 0.0.0.0 --port 8000`; abrir la pestaña
    **Centro de mando** para ver los indicadores corregidos.
28. **Próximo paso recomendado**: iteración 020 — endpoint `GET
    /api/agent-telemetry` y vistas premium (Sistema Solar Canvas 2D +
    Mission Control cyberpunk) que representen exactamente estos indicadores,
    con modo demo separado y sin inventar actividad.
