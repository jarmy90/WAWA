# Informe de iteración 021 — Activación comercial (v0.20.0)

1. **Número de iteración**: 021.
2. **Objetivo**: macrooperación de activación comercial: dejar una única
   oportunidad ganadora en `READY_TO_CONNECT_SERVICES` (y, sin credenciales
   humanas, en `READY_TO_CONNECT_SERVICES` con la lista mínima de
   credenciales), completando la investigación con evidencia real y
   preparando el lanzamiento sin gasto ni acciones irreversibles.
3. **Resumen del trabajo realizado**: (a) recuperación del estado real
   (iteraciones 018-020, DB `data/abl.db`, torneo, misiones, evidencias,
   revisiones, planes); (b) investigación web autorizada para las 3
   candidatas reales con 31 evidencias verificadas (URL + fecha + fragmento)
   importadas en 18 misiones de Fase 1; (c) reevaluación con evidencia
   (`evidence_backed_venture_score` 0 → 59.14, 7 grupos independientes);
   (d) decisión determinista de ganadora (torneo 018 + evidencia);
   (e) paquete de lanzamiento preparado en `product/` (landing, checkout,
   email, analytics, términos, checklist); (f) panel conectado (ganadora,
   CONECTAR SERVICIOS, AUTORIZAR CICLO AUTÓNOMO); (g) `READY_TO_CONNECT_SERVICES`
   verificado en servidor real; (h) suite 393 passed; (i) paquete verificado
   y publicado.
4. **Archivos nuevos**: `scripts/activate_commercial_021.py`,
   `scripts/readiness_launch_021.py`, `tests/test_activation_commercial_021.py`,
   `product/` (7 archivos), `deliverables/operacion_activacion_comercial_2026-08-26/investigacion_fase1_021.json`,
   `deliverables/ITERATION_021_MANIFEST.md`, `deliverables/ITERATION_021_REPORT.md`.
5. **Archivos modificados**: `app/repositories/opportunities.py`
   (`get_by_concept`), `app/repositories/discovery.py` (`update_mission_target`),
   `app/services/command_center.py` (telemetría de lanzamiento),
   `app/core/config.py` (v0.20.0), `frontend/index.html`,
   `frontend/mission-control.html`, `frontend/mission-control.js`,
   `tests/test_ox_alpha_sprint_018.py`, `tests/test_mission_control_020.py`,
   `docs/ITERATION_HISTORY.md`.
6. **Archivos eliminados**: ninguno.
7. **Decisiones técnicas**: (a) la investigación se importa como datos
   (misión local + evidencia con URL/fecha/fragmento), nunca como
   razonamiento de modelo; (b) `get_by_concept` resuelve concepto→oportunidad
   por título normalizado + campaña (sin IDs foráneos); (c) el readiness se
   fija con evaluación derivada (Venture Quality Score con evidencia, sin
   LLM) + plan de experimento completo; (d) el panel solo muestra nombres de
   variable y estados de credenciales, nunca valores.
8. **Estado del embudo**: 75 conceptos (67 NEEDS_REFORMULATION, 5
   RECOMBINATION_INCOHERENT, 3 RESEARCH_PENDING) → 3 candidatas investigadas
   → 1 ganadora determinista (ortodoncia) → READY_TO_CONNECT_SERVICES.
9. **Evidencia por candidata**: ortodoncia 11 verificadas / 7 grupos;
   gestorías 10 / 7; placas solares 10 / 7. Todas con `verified=true` solo
   con URL + fecha + fragmento; 0 evidencias rechazadas o duplicadas.
10. **Revisiones de modelos**: 0 (ausencia neutral; el comité sigue
    disponible). Las opiniones de modelos nunca son evidencia.
11. **Ganadora**: Benchmark anónimo de tarifas de ortodoncia. Razones:
    mayor prioridad del torneo 018 (77.5), única con `low_launch_cost=2/2` y
    `concierge_delivery=2/2`, 7 grupos de evidencia verificada, datos
    obtenibles (tarifarios públicos), canal accesible (colegios y
    directorios), entrega concierge posible, sin bloqueadores.
12. **Oferta y precio**: informe de benchmark por provincia + revisión
    concierge; 60 EUR (hipótesis 30-90 EUR). HIPÓTESIS sin comprador real.
13. **Plan de experimento**: 30 días, presupuesto 0 EUR reales, éxito = 1
    pago real (30-90 EUR), pivot a los 14 días sin pago, cierre a los 30
    días sin señal de pago.
14. **Misiones obligatorias**: 6 de Fase 1 de la ganadora importadas
    (status=imported), con `opportunity_id` en target; las 18 de las 3
    candidatas importadas.
15. **Readiness**: `READY_TO_CONNECT_SERVICES` (met=true, missing=[], 
    blockers=[]); condiciones: producción bloqueada, servicios no conectados,
    propietario no autorizado. `READY_TO_LAUNCH` bloqueado por diseño.
16. **Paquete de lanzamiento**: `product/` (landing responsive, checkout
    prep, email, analytics, términos/privacidad, checklist). Nada conectado.
17. **Servicios pendientes (lista mínima)**: Stripe (`STRIPE_SECRET_KEY`),
    email (`EMAIL_API_KEY`), hosting (`HOSTING_*`), dominio (`DOMAIN`),
    analytics (`ANALYTICS_*`) — todos MISSING; GitHub CONNECTED (repo actual).
18. **Mandato de 30 días**: pantalla AUTORIZAR CICLO AUTÓNOMO en el panel,
    `PENDING_OWNER_AUTHORIZATION`, con canales permitidos, acciones
    automáticas, acciones bloqueadas, rangos de precio y condiciones.
19. **Mission Control conectado**: secciones ganadora / servicios / mandato;
    telemetría real derivada de datos persistidos (sin actividad inventada).
20. **Presupuesto**: 0 EUR reales consumidos; `max_cost_usd=0.0`; costes LLM
    reported/estimated/unknown/zero separados (0 llamadas).
21. **Economía**: simulada; ledger append-only sin inconsistencias; sin
    deuda; sin SAFE_PAUSE.
22. **Seguridad**: sin secretos en Git ni en el paquete; panel XSS-safe;
    `tmp/` excluido; credenciales fuera de logs.
23. **Pruebas**: 393 passed (387 + 6 nuevos: get_by_concept,
    update_mission_target, verificación estricta al importar, contrato de
    telemetría de lanzamiento, readiness con todas las precondiciones,
    bloqueo sin precio hipótesis). `node --check` OK. Servidor real: rutas
    `/`, `/mission-control`, `/agents-viz`, `/api/command-center`,
    `/api/agent-telemetry` → 200 y readiness confirmado.
24. **Verificación visual**: sin navegador en este entorno; verificación por
    servidor real + smoke headless de render (deuda: capturas en la
    instalación del propietario).
25. **Limitaciones reales**: la demanda sigue siendo HIPÓTESIS (0 pagos
    reales); el precio no está confirmado con compradores; no hay navegador
    para capturas; el flujo legacy del orquestador (advance) reevalúa las
    oportunidades promovidas antiguas — esta iteración fija el estado de
    lanzamiento directamente con trazabilidad en `decision_log`.
26. **Siguiente macroobjetivo**: que el propietario complete CONECTAR
    SERVICIOS + AUTORIZAR CICLO AUTÓNOMO para pasar a `READY_TO_LAUNCH` y
    ejecutar el ciclo de 30 días con pagos reales.
27. **Automatización**: todo lo ejecutable se automatizó (investigación,
    importación, reevaluación, decisión, plan, readiness, panel, paquete,
    pruebas, commit, push). Solo quedan las dos acciones humanas del punto 17.
28. **Honestidad**: ningún indicador transmite una conclusión más optimista
    de lo que permiten los datos: `proven_demand=0` sin pagos, precio como
    hipótesis, costes desconocidos ≠ 0, producción bloqueada, opiniones de
    modelos separadas de evidencia.
