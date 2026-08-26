# Manifiesto de iteración 020

- **Identificador de iteración**: 020
- **Fecha y hora**: 2026-08-26 (macrointervención visual Agent Mission Control Premium)
- **Objetivo**: crear una experiencia visual de supervisión de agentes de
  calidad profesional y lúdica (Sistema Solar + Mission Control cyberpunk)
  con telemetría conectada a datos REALES de WAWA, modo demo separado,
  rendimiento fluido e identidad visual propia, SIN sustituir la corrección
  semántica del Centro de mando (iteración 019) y sin inventar actividad.
- **Estado**: `entregado`

## Resumen de cambios

Implementado y probado automáticamente (suite 387 passed; 20 tests nuevos):
endpoint `GET /api/agent-telemetry` con contrato tipado (agentes reales con
`data_nature`, estados permitidos ACTIVE/WORKING/WAITING/BLOCKED/IDLE/ERROR/
OFFLINE/NO_DATA; nunca se deduce ACTIVE por la mera existencia de un agente);
rutas limpias `/mission-control` y `/agents-viz` (funcionan directas y tras
refrescar) con HTML/CSS/JS vanilla + Canvas 2D, sin CDN, sin build; modo demo
etiquetado `DEMO DATA · NOT REAL ACTIVITY` (`?demo=1` o botón), nunca mezclado
con datos reales; `prefers-reduced-motion`, fallback textual del Canvas,
navegación por teclado, ARIA; `node --check` OK en los 6 JS; smoke test
headless de render (`scripts/viz_smoke.js`). Estudio de 4 repositorios de
referencia (commits y licencias documentados en
`docs/AGENT_MISSION_CONTROL.md`); clones SOLO en `tmp/references/` (excluido de
Git y del paquete). Versión v0.19.0 / build 020-agent-mission-control.

## Archivos

- **Nuevos**:
  - `frontend/mission-control.html`, `frontend/mission-control.css`, `frontend/mission-control.js`
  - `frontend/agents-viz.html`, `frontend/agents-viz.js`
  - `frontend/viz-core.js`
  - `scripts/viz_smoke.js`
  - `tests/test_mission_control_020.py`
  - `docs/AGENT_MISSION_CONTROL.md`
  - `deliverables/ITERATION_020_MANIFEST.md`, `deliverables/ITERATION_020_REPORT.md`
- **Modificados**:
  - `app/services/command_center.py` (`agent_telemetry()`)
  - `app/api/routes.py` (`GET /api/agent-telemetry`)
  - `app/main.py` (rutas directas /mission-control y /agents-viz)
  - `app/core/config.py` (v0.19.0)
  - `frontend/index.html` (v0.19.0 / 020 + enlaces a las vistas)
  - `scripts/_review_common.py` (excluye `tmp/` del paquete)
  - `.gitignore` (excluye `tmp/`)
  - `tests/test_ox_alpha_sprint_018.py` (sincronización de versión)
- **Eliminados**: ninguno

## Cambios

- **Arquitectura**: vistas premium estáticas (sin build) servidas por
  rutas explícitas + StaticFiles; telemetría derivada de datos persistidos.
- **Agentes/prompts**: ninguno (los 8 agentes lógicos + proveedores se
  representan, no se modifican).
- **Scoring y reglas de decisión**: ninguno.
- **Seguridad**: render siempre escapado (XSS-safe); `data_nature` por agente;
  modo demo separado; sin CDN; `tmp/` excluido del paquete.
- **Presupuesto**: sin cambios; gasto real 0 €; producción bloqueada.
- **Modelos de datos**: sin cambio de esquema.
- **Dependencias**: ninguna.

## Comandos

- **Instalar**: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- **Ejecutar**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Probar**: `pytest`; `node --check frontend/*.js`; `node scripts/viz_smoke.js`

## Pruebas

- **Resultado exacto**: `387 passed, 1 warning in 28.40s`
- **Comandos usados**: `python3 -m pytest`; `node --check frontend/viz-core.js
  frontend/mission-control.js frontend/agents-viz.js frontend/app.js
  frontend/ops17.js frontend/ops18.js`; `node scripts/viz_smoke.js`
- **Comprobaciones manuales**: servidor real (uvicorn): `/` 200,
  `/mission-control` 200, `/agents-viz` 200, `/api/agent-telemetry` 200 con
  agentes y estados honestos (orchestrator WAITING, compliance BLOCKED,
  proveedores OFFLINE), assets JS/CSS 200; smoke headless de render sin
  excepciones (selección, hover, filtros, demo, escape XSS).

## Problemas conocidos / limitaciones / riesgos

- **Problemas conocidos**: ninguno en la suite (0 fallos).
- **Limitaciones**: sin navegador real en este entorno, la verificación visual
  se hizo con servidor real + smoke headless de render (no capturas PNG);
  las referencias sin licencia (solar-system-agents, glglak) se usaron solo
  como patrones, sin copiar código.
- **Riesgos abiertos**: los indicadores visuales dependen de la exactitud
  semántica de la iteración 019 (garantizada por sus tests); sin candidata
  seleccionada, el readiness visual permanece NOT_READY.
- **Deuda técnica**: capturas PNG deterministas cuando haya navegador
  disponible; degradación de calidad en móvil (vista simplificada ya
  implementada vía CSS).

## Revisión externa

- **Elementos que debe supervisar el revisor**: fidelidad de la telemetría
  (¿algún estado parece más optimista que los datos?), calidad visual de las
  dos vistas, separación estricta del modo demo, cumplimiento de licencias.
- **Próxima acción recomendada**: probar `/mission-control` y `/agents-viz` en
  navegador real (desktop y móvil), capturar pantallas y continuar el roadmap
  hacia Autonomous Launch.

## Paquete

- **Nombre del paquete**: autonomous-business-lab_iteracion-020_2026-08-26.zip.txt
- **Tamaño del paquete**: 6879637 bytes
- **SHA-256 del paquete**: 76dfb286bfb78c9d61571b2f609c8c39dfc1133d8ed56ed9d64649210db687f2

## Git

- **Commit actual**: pendiente de publicar
- **Estado del repositorio**: cambios locales de la iteración 020 listos
- **git diff --stat**: 8 modificados + 9 nuevos
- **Archivos cambiados**: ver sección Archivos
