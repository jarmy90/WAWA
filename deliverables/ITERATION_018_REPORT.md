# Informe de iteración 018 — OX Alpha Grand Intelligence Sprint (v0.17.0)

1. **Número de iteración**: 018.
2. **Objetivo**: sprint de inteligencia sobre el universo completo de la
   campaña (66 conceptos + 6 reformulaciones) para producir hasta 3 candidatas
   superiores con su plan de investigación, verificar la identidad OX Alpha
   sin inventar el slug, diseñar Autonomous Launch y entregar un centro de
   mando operativo con datos reales. Resultado permitido: 0-3 candidatas.
3. **Resumen del trabajo realizado**: verificación honesta de la puerta OX
   Alpha (identidad `OX_ALPHA_UNVERIFIED` porque el gateway está desactivado y
   el slug no está verificado contra el catálogo; benchmark reproducible con
   veredicto `OX_ALPHA_UNVERIFIED`); super-torneo determinista de 20 criterios
   sobre la campaña local (deduplicación de títulos repetidos, brief completo
   obligatorio, máx. 3 ganadoras, 0 válido) → **3 candidatas priorizadas** con
   plan portable de 6 misiones Fase 1 por candidata (consultas ES/EN, fuentes,
   contradicciones, kill conditions); investigación web inicial real con
   fuentes marcadas PROVISIONAL (nunca evidencia en BD); diseño del contrato
   Autonomous Launch con estados verificables `READY_TO_CONNECT_SERVICES` /
   `READY_TO_LAUNCH` (bloqueado hasta autorización única); centro de mando
   cyberpunk (`GET /api/command-center` + panel `frontend/ops18.js`) que
   consume APIs reales y diferencia REAL/SIMULADO/HIPÓTESIS/MODELO/
   DESCONOCIDO; análisis de herramientas externas con decisiones honestas;
   30 tests nuevos offline; versión v0.17.0 / build 018-ox-alpha-sprint.
4. **Archivos nuevos**:
   - `app/scoring/super_tournament.py` (torneo 20 criterios, dedupe, 0-3)
   - `app/services/super_tournament.py` (servicio + decision_log append-only)
   - `app/scoring/ox_alpha_benchmark.py` (rúbrica determinista)
   - `app/services/command_center.py` (snapshot agregado honesto)
   - `scripts/run_super_tournament.py`, `scripts/benchmark_ox_alpha.py`
   - `frontend/ops18.js` (centro de mando)
   - `tests/test_ox_alpha_sprint_018.py` (30 tests), `tests/__init__.py`
   - `docs/AUTONOMOUS_LAUNCH.md`, `docs/TOOL_ANALYSIS_018.md`
   - `deliverables/operacion_super_torneo_2026-08-26/` (resultado, plan
     portable, benchmark, investigación inicial provisional)
   - `deliverables/ITERATION_018_MANIFEST.md`, este informe.
5. **Archivos modificados**: `app/core/container.py` (servicios nuevos),
   `app/api/routes.py` (endpoint `/api/command-center`), `app/core/config.py`
   (v0.17.0), `frontend/index.html` (vista Centro de mando, v0.17.0/018,
   script ops18), `frontend/styles.css` (estilos cyberpunk),
   `docs/ITERATION_HISTORY.md`.
6. **Archivos eliminados**: ninguno.
7. **Decisiones técnicas**: (a) el super-torneo es 100 % determinista (sin
   LLM, sin timestamps) y emite `super_tournament_score` como prioridad de
   investigación, NUNCA evidencia; `proven_demand`, `evidence_backed_venture_score`
   y grupos de evidencia quedan intactos (probado); (b) deduplicación por
   título normalizado conservando el estado más avanzado (defecto real
   encontrado: el mismo negocio ganó 3 veces); (c) brief completo obligatorio
   en la puerta del torneo; (d) OX Alpha solo se declara con slug verificado
   contra el catálogo del gateway; `auto` y vacío ⇒ `OX_ALPHA_UNVERIFIED`;
   fallo ⇒ ausencia neutral; (e) el centro de mando agrega datos persistidos
   reales y etiqueta cada bloque por naturaleza; nunca inventa cifras
   (DESCONOCIDO/NO CONECTADO/SIN DATOS/SIMULACIÓN); (f) la investigación web
   se guarda como PROVISIONAL en el paquete, no como evidencia en BD (la
   verificación exige el flujo de importación local contra `mission_id`).
8. **Dependencias añadidas o retiradas**: ninguna.
9. **Cambios en arquitectura**: módulos internos `scoring/super_tournament.py`
   y `services/command_center.py` + 3 scripts + 1 endpoint; sin workers ni
   microservicios (regla MVP respetada).
10. **Cambios en modelos de datos**: ninguno (esquema SQLite intacto); todo
    se deriva de datos persistidos existentes.
11. **Cambios en prompts o agentes**: no se tocó ningún agente; las tareas
    profundas P0 de OX Alpha ya existían (iteración 015) y solo se prueban.
12. **Cambios en scoring y reglas de decisión**: se AÑADIÓ `super_tournament_score`
    (prioridad etiquetada `is_not_evidence=true`); el Venture Quality Score,
    bandas y bloqueadores existentes no se modifican; evidencia sigue en 0.
13. **Cambios en seguridad o gestión presupuestaria**: el centro de mando no
    expone claves (solo booleano `configured` por proveedor); presupuesto 0 €;
    PRE_CYCLE detenido; `AUTONOMOUS_PRODUCTION` bloqueado por capacidad;
    `READY_TO_LAUNCH` imposible sin autorización única (determinista, probado).
14. **Pruebas ejecutadas**: `python3 -m pytest` (suite completa),
    `node --check frontend/app.js frontend/ops17.js frontend/ops18.js`,
    flujo offline: campaña → super-torneo → plan portable → benchmark.
15. **Comandos exactos utilizados**:
    - `python3 -m pytest tests/test_ox_alpha_sprint_018.py -q`
    - `python3 -m pytest`
    - `node --check frontend/app.js && node --check frontend/ops17.js && node --check frontend/ops18.js`
    - `python3 scripts/run_super_tournament.py`
    - `python3 scripts/benchmark_ox_alpha.py`
16. **Número de pruebas superadas**: 367 (337 previas + 30 nuevas).
17. **Número de pruebas fallidas**: 0 (fallos iniciales de los tests nuevos
    corregidos, ver 18).
18. **Errores encontrados y correcciones aplicadas**:
    - Import circular `command_center` ↔ `container`: resuelto con
      `TYPE_CHECKING` (la anotación es solo de tipos).
    - El super-torneo real mostró que el MISMO título ganaba 3 veces
      (duplicados en la campaña local): se añadió deduplicación determinista
      por título normalizado conservando el estado más avanzado.
    - `cycle.evaluate()` devuelve `status` (no `state`): alineados servicio
      y tests con el contrato real.
    - `proven_demand` vive dentro de `venture` en el detalle del concepto:
      el test de no-mutación compara la ruta correcta.
    - Los tests de la puerta OX Alpha requerían `omniroute_enabled=True`
      para aislar el estado `SLUG_UNVERIFIED` (no `GATEWAY_DISABLED`).
    - El test de etiquetas prohibidas comparaba contra el JSON completo que
      las lista (diseño): ahora verifica que no se ATRIBUYEN a salidas.
19. **Comprobaciones manuales realizadas**: reproducción completa offline
    (campaña real → `RESEARCH_PENDING` → super-torneo con 9 entradas → 3
    ganadoras → plan portable con 6 misiones Fase 1 por candidata);
    endpoint `GET /api/command-center` con y sin campaña (66 conceptos,
    contadores por estado, bloqueador `PRODUCTION_BLOCKED`, servicios
    `NO CONECTADO`); benchmark OX Alpha (`OX_ALPHA_UNVERIFIED`); sintaxis JS.
20. **Funcionalidades no verificadas**: el benchmark real de OX Alpha contra
    el gateway (identidad no verificada; gateway desactivado; falta disco para
    arrancarlo); la aplicación del plan portable en la base del propietario
    (requiere su instalación y `apply_reformulation_plan.py --preview`);
    la importación de la investigación provisional (exige `mission_id` locales).
21. **Elementos simulados o mock**: nada nuevo; los briefs y candidatas son
    HIPÓTESIS etiquetadas; la investigación inicial se marca PROVISIONAL y no
    eleva ninguna puntuación; la economía sigue simulada (`simulated=true`).
22. **Dependencias de servicios externos**: ninguna obligatoria; todo corre
    offline. OX Alpha/OmniRoute/OpenRouter/Gemini son opcionales y su ausencia
    es neutral.
23. **Limitaciones conocidas**: `collect_entries` del torneo usa la campaña
    activa local (los challengers sin brief se rechazan en la puerta con
    motivo); la deduplicación es por título normalizado (títulos renombrados
    a mano podrían pasar como duplicados); el plan portable sigue el formato
    de la iteración 017 (Fase 1, 6 misiones por candidata).
24. **Riesgos abiertos**: sin investigación importada verificada no hay
    finalistas (0 válido); las 3 candidatas tienen `evidence_backed_venture_score=0`
    y `proven_demand=0` hasta evidencias con URL+fecha+fragmento; el slug
    "OX Alpha" debe verificarse contra el catálogo real del gateway antes de
    declararse (regla de la iteración 008).
25. **Deuda técnica**: ejecutar el benchmark OX Alpha real cuando haya espacio
    en disco y slug verificado; conector opcional de escucha de foros
    (BENCHMARK_FIRST); persistir el resultado del super-torneo en una tabla
    propia (hoy vive en `decision_log` + JSON de salida).
26. **Elementos concretos para el revisor externo**: (a) el resultado del
    super-torneo (¿las 3 ganadoras merecen investigación o 0 era más honesto?);
    (b) la investigación inicial PROVISIONAL (¿las fuentes y fragmentos son
    correctos y útiles?); (c) el centro de mando (¿distingue bien naturaleza
    de datos?); (d) el contrato Autonomous Launch (¿faltan puertas de
    seguridad?); (e) la política económica 50 €/100 €.
27. **Instrucciones de instalación y ejecución**: descomprimir el paquete,
    `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`,
    `uvicorn app.main:app --host 0.0.0.0 --port 8000`; en la pestaña
    **Centro de mando** se ve el snapshot; `python3 scripts/run_super_tournament.py`
    regenera el torneo; en la instalación del propietario:
    `python3 scripts/apply_reformulation_plan.py --file plan_investigacion_portable_018.json --preview`.
28. **Próximo paso recomendado**: en la instalación real, aplicar el plan
    portable (preview → aplicar), copiar las 6 misiones Fase 1 por candidata,
    investigar con las consultas ES/EN del paquete e importar resultados con
    URL+fecha+fragmento; las fuentes PROVISIONALES del paquete pueden usarse
    como punto de partida de las misiones de demanda/competencia.
