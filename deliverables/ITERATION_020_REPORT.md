# Informe de iteración 020 — Agent Mission Control Premium (v0.19.0)

1. **Número de iteración**: 020.
2. **Objetivo**: crear una experiencia visual de supervisión de agentes de
   calidad profesional y lúdica (Sistema Solar + Mission Control cyberpunk)
   con telemetría conectada a datos REALES de WAWA, modo demo explícito y
   separado, rendimiento fluido e identidad visual propia (WAWA AUTONOMOUS
   BUSINESS COMMAND), sin sustituir ni retrasar la corrección semántica del
   Centro de mando (iteración 019, publicada antes) y sin inventar actividad.
3. **Resumen del trabajo realizado**: (a) estudio de 4 repositorios de
   referencia clonados en `tmp/references/` (Audazia/solar-system-agents
   `fa63ba27`, DanWahlin/agent-mission-control `75adb453` MIT, glglak/
   agent-mission-control `39e2e3bd`, 209512/atc `6577c75f` Apache-2.0) con
   análisis de patrones (roster+planetas, moones/anillos, ticker, scanlines,
   inspector, cola operativa, radar) y decisión de no copiar código de las
   referencias sin licencia; (b) endpoint `GET /api/agent-telemetry` que
   deriva estados SOLO de datos persistidos (run del orquestador, misiones,
   evidencias, comité, costes LLM, proveedores, decisiones y eventos) con
   contrato tipado por agente (`id`, `name`, `role`, `status`, `current_action`,
   `last_event_at`, `activity_level`, `priority`, `tools`, `missions`,
   `parent_agent_id`, `blocked_reason`, `event_count`, `error_count`, `cost`,
   `data_nature`) y estados permitidos; nunca deduce ACTIVE por la mera
   existencia de un agente (sin datos ⇒ NO_DATA/IDLE/OFFLINE); (c) vistas
   `/mission-control` (20 secciones: salud, producción, campaña, roster,
   acción actual, misiones, cola, bloqueadores, evidencias, comité, costes
   con desconocidos ≠ 0, presupuesto, timeline, métricas NO CONECTADO,
   drawer, fullscreen, refresco manual/automático, estado de conexión,
   timestamp) y `/agents-viz` (Canvas 2D con devicePixelRatio, ResizeObserver,
   requestAnimationFrame + delta time, pausa en pestaña oculta, límite de
   partículas, degradación automática, sol=CampaignOrchestrator, planetas=
   agentes, lunas=herramientas, anillos=tareas, asteroides=cola, cometas=
   bloqueadores, líneas=relaciones reales, órbita congelada=WAITING/IDLE,
   planeta rojo intermitente=BLOCKED/ERROR, tooltips, teclado, zoom limitado,
   focus mode, filtros por estado, indicador REAL/DEMO, pausa); (d) modo demo
   etiquetado `DEMO DATA · NOT REAL ACTIVITY` (`?demo=1` o botón), conjunto
   separado en `viz-core.js`, nunca mezclado con datos reales; (e)
   accesibilidad: `prefers-reduced-motion`, fallback textual del Canvas,
   ARIA, navegación por teclado, contraste; (f) 20 tests nuevos (rutas,
   recarga, contrato de telemetría, estados, base vacía sin ACTIVE inventado,
   costes sin ceros falsos, demo separada, XSS, reduced motion, smoke de
   render headless); (g) suite 387 passed; `node --check` OK; servidor real
   verificado (rutas 200); versión v0.19.0 / build 020-agent-mission-control.
4. **Archivos nuevos**: `frontend/mission-control.html`,
   `frontend/mission-control.css`, `frontend/mission-control.js`,
   `frontend/agents-viz.html`, `frontend/agents-viz.js`, `frontend/viz-core.js`,
   `scripts/viz_smoke.js`, `tests/test_mission_control_020.py`,
   `docs/AGENT_MISSION_CONTROL.md`, `deliverables/ITERATION_020_MANIFEST.md`,
   `deliverables/ITERATION_020_REPORT.md`.
5. **Archivos modificados**: `app/services/command_center.py`
   (`agent_telemetry()`), `app/api/routes.py` (`/api/agent-telemetry`),
   `app/main.py` (rutas directas), `app/core/config.py` (v0.19.0),
   `frontend/index.html` (v0.19.0/020 + enlaces), `scripts/_review_common.py`
   (excluye `tmp/`), `.gitignore` (`tmp/`), `tests/test_ox_alpha_sprint_018.py`
   (sincronización de versión).
6. **Archivos eliminados**: ninguno.
7. **Decisiones técnicas**: (a) telemetría derivada de datos persistidos, con
   `data_nature=REAL` por agente y nota que aclara que el demo es solo cliente;
   (b) estados por reglas deterministas (run state → orquestador; misiones →
   Researcher; revisiones → Skeptic; ciclo → Economist; plan → Builder;
   bloqueadores → Compliance; evidencias → Judge; llamadas recientes →
   proveedores WORKING/ACTIVE); (c) sin CDN ni frameworks: Canvas 2D vanilla
   (tsParticles de la referencia se estudió y se rechazó por la regla sin
   CDN/offline); (d) rutas explícitas en `app/main.py` porque StaticFiles con
   `html=True` no resuelve URLs sin extensión; (e) `tmp/` excluido de Git y
   del paquete para no filtrar las referencias clonadas; (f) smoke headless de
   render con mocks de DOM/Canvas en node.
8. **Dependencias añadidas o retiradas**: ninguna.
9. **Cambios en arquitectura**: 2 rutas web + 1 endpoint de telemetría +
   6 archivos frontend estáticos; sin workers ni microservicios.
10. **Cambios en modelos de datos**: ninguno (esquema SQLite intacto).
11. **Cambios en prompts o agentes**: ninguno (solo representación visual de
    los agentes lógicos existentes).
12. **Cambios en scoring y reglas de decisión**: ninguno.
13. **Cambios en seguridad o gestión presupuestaria**: render escapado
    (XSS-safe); modo demo nunca mezclado; presupuesto intacto; gasto real 0 €;
    AUTONOMOUS_PRODUCTION bloqueado; producción mostrada como BLOCKED con
    motivo real.
14. **Pruebas ejecutadas**: `python3 -m pytest` (387), `node --check` sobre
    los 6 JS del frontend, `node scripts/viz_smoke.js` (render headless),
    servidor uvicorn real con curl.
15. **Comandos exactos utilizados**:
    - `python3 -m pytest -q`
    - `node --check frontend/viz-core.js frontend/mission-control.js frontend/agents-viz.js frontend/app.js frontend/ops17.js frontend/ops18.js`
    - `node scripts/viz_smoke.js`
    - `uvicorn app.main:app --host 127.0.0.1 --port 8931` + `curl` a `/`,
      `/mission-control`, `/agents-viz`, `/api/agent-telemetry` y assets
16. **Número de pruebas superadas**: 387 (367 previas + 20 nuevas).
17. **Número de pruebas fallidas**: 0.
18. **Errores encontrados y correcciones aplicadas**:
    - StaticFiles con `html=True` no sirve `/mission-control` sin extensión
      (404): rutas explícitas con FileResponse en `app/main.py`.
    - El smoke de render headless no terminaba (rAF mock mantenía el bucle):
      salida explícita con `process.exit(0)`.
    - `tmp/` no estaba excluido: añadido a `.gitignore` y a
      `EXCLUDED_DIRS` del empaquetado.
    - El test de `matchMedia` miraba en agents-viz.js: la detección vive en
      `viz-core.js` (núcleo compartido); test corregido.
    - Test `test_telemetry_does_not_invent_activity_on_empty_db` tenía una
      construcción residual: simplificada a base recién creada.
19. **Comprobaciones manuales realizadas**: servidor real levantado; `/` 200,
    `/mission-control` 200, `/agents-viz` 200, `/api/agent-telemetry` 200 con
    agentes reales y estados honestos (orchestrator WAITING, researcher
    WAITING con misiones pendientes, compliance BLOCKED por producción
    bloqueada, proveedores OFFLINE, mock IDLE); assets JS/CSS 200; smoke
    headless: render, selección por teclado, hover, filtro, modo demo y
    escape XSS sin excepciones.
20. **Funcionalidades no verificadas**: capturas PNG en navegador real (sin
    navegador en este entorno); la vista en móvil físico real (verificada por
    CSS responsive y código, no por dispositivo).
21. **Elementos simulados o mock**: solo el modo demo del cliente
    (etiquetado `DEMO DATA · NOT REAL ACTIVITY`); el resto es REAL derivado
    de datos persistidos; la economía sigue simulada (`simulated=true`).
22. **Dependencias de servicios externos**: ninguna obligatoria; sin CDN;
    todo corre offline.
23. **Limitaciones conocidas**: sin navegador real no hay capturas; las
    referencias sin licencia se usaron solo como patrones; el polling visual
    es de 10 s (ajustable) y se pausa en pestañas ocultas.
24. **Riesgos abiertos**: los estados visuales dependen de la exactitud
    semántica 019; con base vacía todo se muestra NO_DATA/OFFLINE (honesto,
    no decorativo).
25. **Deuda técnica**: capturas PNG deterministas con navegador; modo móvil
    simplificado adicional si la prueba en dispositivo lo exige; accesibilidad
    fina (foco visible en selectores) pendiente de revisión visual.
26. **Elementos concretos para el revisor externo**: (a) fidelidad de la
    telemetría (¿algún agente parece más activo de lo que permiten los
    datos?); (b) calidad visual y jerarquía de ambas vistas; (c) separación
    estricta del modo demo; (d) cumplimiento de licencias (nada copiado de
    repos sin licencia); (e) documentación `docs/AGENT_MISSION_CONTROL.md`.
27. **Instrucciones de instalación y ejecución**: descomprimir el paquete,
    `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`,
    `uvicorn app.main:app --host 0.0.0.0 --port 8000`; abrir
    `http://127.0.0.1:8000/mission-control` y `http://127.0.0.1:8000/agents-viz`;
    `?demo=1` activa el modo demo etiquetado.
28. **Próximo paso recomendado**: probar ambas vistas en navegador real
    (desktop/móvil/fullscreen), capturar pantallas de referencia y continuar
    el roadmap hacia Autonomous Launch (conectar y verificar servicios antes
    de cualquier READY_TO_LAUNCH).
