# MANIFIESTO ITERACIÓN 012 — CORRECCIÓN EXCLUSIVA DE LA INTERFAZ ENTREGADA (v0.11.1)

- **Iteración**: 012 (el workflow exige no reutilizar números; es una
  corrección exclusiva del frontend entregado en la 011)
- **Versión**: 0.11.1 (patch)
- **Fecha**: 2026-08-23
- **Estado**: COMPLETADA
- **Objetivo**: corregir la causa raíz por la que el propietario veía solo el
  panel lateral sin navegación, y rediseñar la pantalla inicial para que la
  navegación, PRE_CYCLE y el botón INICIAR CAMPAÑA REAL sean visibles sin
  JavaScript y sin desplazamiento.

## CAUSA RAÍZ exacta (confirmada con navegador real, no por grep)

La prueba real del propietario se reprodujo con **Chromium headless
(puppeteer)** contra el paquete 011 servido desde una carpeta limpia:

- El HTML, app.js y styles.css servidos eran los correctos (versión 0.11.0).
- A **1440×900** las pestañas sí eran visibles; a **1024×768 y 390×844** la
  medición geométrica real (`getBoundingClientRect`) mostró
  `tab_campaign=false, tab_ideas=false, status_strip=false` y
  `document.documentElement.scrollHeight` (1634/2029 px) muy superior a la
  altura de ventana.

**La causa raíz es un fallo de layout**: en `frontend/styles.css`,
`.layout { display: grid; grid-template-columns: 260px 1fr 1.25fr }` con
`@media (max-width: 1100px) { .layout { grid-template-columns: 1fr } }`. El
DOM colocaba el `<aside class="sidebar">` (filtros + leyenda + motor +
economía + actividad + proveedor, ~1000 px de alto) ANTES de
`<section class="content">`. En ventanas de ≤1100 px la cuadrícula pasa a una
sola columna y **todo el contenido principal (pestañas, franja de estado,
INICIAR CAMPAÑA REAL) queda debajo del sidebar, fuera del pliegue**. El
propietario veía exactamente eso: solo topbar + sidebar. JavaScript sí se
ejecutaba (los chips "investigando", "Presupuesto", "mock" los rellena
app.js); simplemente el contenido estaba fuera de la ventana.

## Correcciones aplicadas (rediseño mínimo, sin nueva arquitectura)

1. **Nueva portada** (`frontend/index.html`): hero visible sin
   desplazamiento con "WAWA", "Descubrimiento y validación de
   oportunidades", chip de versión, **PRE_CYCLE · reloj detenido · 30 días**,
   **PRIMERA CAMPAÑA REAL 001**, botón **INICIAR CAMPAÑA REAL** y la frase
   "Genera ideas, aplica filtros, prepara investigación y conserva todos los
   motivos de descarte sin inventar evidencia."
2. **Navegación estática en HTML** (no depende de JS): Inicio, Campaña real,
   Ideas, Investigación, Comité, Experimento, Economía, Actividad,
   Configuración — arriba, sin filtros/motor/economía delante.
3. **Panel antiguo movido a sub-vistas**: filtros, nueva oportunidad, importar
   JSON, leyenda, motor, economía simulada, actividad y proveedor viven ahora
   en Configuración / Economía / Actividad. Eliminados todos los textos
   heredados (Cargar demo, demostración, MQL5, MetaTrader, Expert Advisor:
   0 coincidencias en frontend/).
4. **Fallback sin JavaScript**: bloque `<noscript>` con aviso y enlace
   `/api/health`; la navegación y el botón existen directamente en index.html
   (los enlaces `#ancla` funcionan sin JS).
5. **Diagnóstico visible** (`#diag`): Backend, Frontend, Iteración,
   JavaScript (cargado) y Paquete. Si app.js no completa el init, una franja
   roja CSS pura muestra "LA INTERFAZ NO HA TERMINADO DE CARGAR."
   (`body:not([data-js="ok"]) .js-fail { display:block }`).
6. **Correcciones de app.js** (bugs reales encontrados con el navegador):
   - `switchView` reescrito para las 9 vistas nuevas.
   - `renderEngine` y badges con guards (el "huevo" `#egg` ya no existe).
   - Vistas Investigación (misiones + pegar) y Experimento (plan) nuevas.
7. **Versión**: 0.11.1 en `app/core/config.py`, `app/__init__.py`, `/api/health`,
   chip visible y `data-wawa-version`; assets con `?v=0111`.

## Prueba de aceptación (navegador real, la que exigía el propietario)

Ejecutada con puppeteer/Chromium sobre la página HTTP servida (no el archivo
en disco):

1. **1440×900 inicial**: nav, botón INICIAR y chip PRE_CYCLE visibles;
   `scrollHeight == innerHeight` (sin desplazamiento). ✅
2. **390×844 inicial**: nav, botón INICIAR y chip PRE_CYCLE visibles. ✅
3. Vista "Campaña real" antes de iniciar (captura). ✅
4. **Clic real** en INICIAR CAMPAÑA REAL → POST /api/orchestrator/start →
   estado **RESEARCH_PENDING** con 66 conceptos (captura). ✅
5. Vista Ideas: 66 tarjetas renderizadas (captura). ✅
6. **Descargas reales desde el navegador**: CSV (85351 B), Markdown (91531 B)
   y paquete de investigación .zip (28838 B). ✅
7. Portada tras la campaña: **PRE_CYCLE · reloj detenido · 30 días**. ✅
8. **document.body.innerText** (`deliverables/browser_body_text.txt`):
   contiene "Campaña real", "Ideas", "INICIAR CAMPAÑA REAL", "PRE_CYCLE" y
   "PRIMERA CAMPAÑA REAL 001"; NO contiene "Cargar demo", "MQL5",
   "MetaTrader" ni "Expert Advisor". ✅
9. **0 errores de consola** (incluido favicon, silenciado con data-URI). ✅

Capturas reales en `deliverables/screenshots-012/` (01-home-1440,
02-home-390, 03-campaign-before, 04-campaign-research-pending, 05-ideas,
06-home-precycle).

## Archivos modificados

- `frontend/index.html` (reescrito: portada + 9 vistas + modales con ids
  originales + noscript + diag)
- `frontend/app.js` (switchView 9 vistas, guards, vistas Investigación/
  Experimento, diag, init)
- `frontend/styles.css` (portada, navegación, franja JS-fail, compactación
  móvil)
- `app/core/config.py` y `app/__init__.py` (versión 0.11.1)
- `tests/test_api.py` y `tests/test_economy.py` (marcadores del nuevo HTML)
- `deliverables/browser_body_text.txt`, `deliverables/screenshots-012/*.png`
- `README.md`, `COMO_ABRIR_WAWA.md`, `docs/ITERATION_HISTORY.md`

## Validación

- **283 tests** pasan (`python3 -m pytest tests/`).
- `node --check frontend/app.js` OK.
- Aceptación de navegador real (8 puntos) superada sobre el workspace y se
  repetirá sobre el paquete definitivo en carpeta limpia antes de entregar.

- **Nombre del paquete**: autonomous-business-lab_iteracion-012_2026-08-23.zip.txt

- **Tamaño del paquete**: 1077638 bytes

- **SHA-256 del paquete**: d08aecf7990094a71351ec25158cb1b30243af12e4329d782d679e8281e04852
