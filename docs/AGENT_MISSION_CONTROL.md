# WAWA Agent Mission Control Premium — estudio de referencias y arquitectura (iteración 020)

## 1. Referencias estudiadas

| Repositorio | Commit analizado | Licencia | Uso |
| --- | --- | --- | --- |
| https://github.com/Audazia/solar-system-agents | `fa63ba27ce27e2c3229fa4b3362346127487bd6b` (2026-04-01) | Sin fichero LICENSE → solo patrones, **cero código reutilizado** | Prioridad 1: sistema solar de agentes (roster + planetas) |
| https://github.com/DanWahlin/agent-mission-control | `75adb45308e111cbfd4d162610f4e6b60fe9ea63` (2026-08-11) | MIT | Solo patrones: mapa de misión, sectores, replay, inspectores, telemetría de actividad |
| https://github.com/glglak/agent-mission-control | `39e2e3bd7ffa88e1296360e8833b099435f4c6a8` (2026-03-28) | Sin fichero LICENSE → solo patrones | Zonas funcionales, agente bloqueado, jerarquía padre/subagente, feed en tiempo real |
| https://github.com/209512/atc | `6577c75ffe6f5664cce52f64cef9508a4ce834ab` (2026-03-03) | Apache-2.0 | Radar táctico, estados de prioridad, haces/pulsos, cola operativa |

Los clones viven SOLO en `tmp/references/` (excluido de Git y del paquete de
revisión; `scripts/_review_common.py` no lo incluye).

### Archivos y patrones analizados

- `solar-system-agents/index.html`, `mission-control.html`, `config.js`:
  - Roster de agentes con tarjeta + mapeo a planeta (`config.js` línea 28).
  - Parámetros por agente: `planet`, `color`, `size`, `orbit`, `speed`,
    `moons`, `rings` (líneas 35-85).
  - Estados por agente (incluido `error`), ticker animado, scanlines,
    sección orbital (`roster-section`, `orbital-item`).
  - Partículas vía tsParticles CDN: **patrón estudiado, no adoptado** (WAWA
    exige Canvas 2D sin CDN obligatoria y operación offline).
- `DanWahlin/agent-mission-control` (MIT): inspector lateral, telemetría de
  actividad por agente, foco en una misión. Tauri/React: **no adoptado**.
- `glglak/agent-mission-control`: feed en tiempo real, anomalías, agente
  bloqueado con motivo. **Patrones adaptados**: detalle de `blocked_reason`.
- `209512/atc` (Apache-2.0): radar táctico y estados de prioridad. **Patrón
  adaptado**: cola operativa visible y prioridad por agente.

## 2. Decisiones de licencia y originalidad

- No se copió ni se adaptó literalmente ninguna interfaz, marca, texto o
  composición de las referencias.
- `solar-system-agents` y `glglak/agent-mission-control` **no tienen fichero
  de licencia**: se trataron como fuentes de patrones, no de código.
  Implementación 100 % desde cero (Canvas 2D, sin tsParticles, sin CDN).
- DanWahlin es MIT y `atc` Apache-2.0: se reutilizaron únicamente principios
  de experiencia (inspector, estados, cola), no código ni activos.

## 3. Elementos originales de WAWA

- **Sol central = CampaignOrchestrator** con núcleo radiante propio.
- **Semántica de estados ligada a datos reales**: velocidad orbital = actividad
  reciente, brillo = actividad actual, color = estado, órbitas congeladas para
  WAITING/IDLE, planeta rojo intermitente para BLOCKED/ERROR.
- **Lunas = herramientas** del agente (no datos inventados).
- **Anillos = tareas programadas reales** (`scheduled_tasks` del endpoint).
- **Asteroides = cola de misiones real** (`mission_queue`).
- **Cometas = bloqueadores/incidentes reales** (`blockers`).
- **Líneas de energía = relaciones padre→hijo reales** (`agent_relationships`).
- **Contrato `/api/agent-telemetry`** con `data_nature` por agente y estados
  permitidos; nunca se deduce `ACTIVE` por la mera existencia de un agente.
- **Modo demo separado** (`?demo=1` o botón) etiquetado
  `DEMO DATA · NOT REAL ACTIVITY`, nunca mezclado con datos reales.
- Accesibilidad: `prefers-reduced-motion`, fallback textual del Canvas,
  navegación por teclado (flechas ← →, Escape), ARIA, contraste suficiente.

## 4. Arquitectura elegida

- HTML + CSS + JavaScript vanilla + Canvas 2D. Sin proceso de build, sin CDN
  obligatoria, operación offline. Sin Tauri/React/Three.js/Phaser (regla de la
  macrointervención: solo si se demuestra necesidad; no se demostró).
- Rutas limpias (funcionan directas y tras refrescar):
  - `/mission-control` → `frontend/mission-control.html`
  - `/agents-viz` → `frontend/agents-viz.html`
- Archivos nuevos:
  - `frontend/mission-control.html` / `mission-control.css` / `mission-control.js`
  - `frontend/agents-viz.html` / `agents-viz.js`
  - `frontend/viz-core.js` (núcleo compartido: fetch con timeout, escape XSS,
    estados/colores, demo etiquetada, reduced motion, formateo)
- Endpoint: `GET /api/agent-telemetry` (contrato en `app/services/command_center.py`
  → `agent_telemetry()`).

## 5. Correspondencia visual agente → estado

| Estado | Color | Representación |
| --- | --- | --- |
| ACTIVE / WORKING | cian | planeta con glow pulsante, órbita rápida, pulso de evento |
| WAITING | ámbar | órbita congelada, brillo bajo |
| BLOCKED | rojo | planeta rojo intermitente + `blocked_reason` |
| IDLE | verde | órbita congelada, brillo bajo |
| ERROR | rosa | intermitente + cometa si hay incidente |
| OFFLINE | gris | sin glow |
| NO_DATA | gris oscuro | sin glow, sin acción |

## 6. Verificación

- Suite completa: 386 passed (367 + 19 nuevos).
- `node --check` sobre `viz-core.js`, `mission-control.js`, `agents-viz.js`,
  `app.js`, `ops17.js`, `ops18.js`.
- Verificación visual con preview real (rutas cargadas, Canvas visible, sin
  errores de consola, desktop/móvil, fullscreen, tooltips, drawer, filtros,
  animación, reduced motion, error de API, modo demo, datos reales).
