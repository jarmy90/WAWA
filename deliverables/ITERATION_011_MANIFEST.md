# MANIFIESTO ITERACIÓN 011 — CORRECCIÓN DE ENTREGA: FRONTEND OBSOLETO EN EL NAVEGADOR DEL PROPIETARIO

- **Iteración**: 011
- **Fecha**: 2026-08-23
- **Estado**: COMPLETADA
- **Objetivo**: corregir la causa raíz por la que el propietario veía la
  interfaz de la iteración 009 (sin pestañas Campaña real/Ideas, sin
  INICIAR CAMPAÑA REAL, sin PRE_CYCLE) a pesar de que el paquete 010
  contenía el frontend nuevo, y hacer que la entrega sea verificable por
  construcción (prueba de aceptación en carpeta limpia).

## Causa raíz exacta (investigada, no asumida)

Reproducción de la prueba válida con el paquete 010 en carpeta limpia:

1. `unzip` del paquete 010 en `/tmp/wawa-clean` → `frontend/index.html`
   CONTIENE `tab-orchestrator` (idéntico al del repo).
2. `uvicorn app.main:app` desde esa carpeta → `GET /` devuelve el HTML
   nuevo (17662 bytes, con las 6 pestañas e "INICIAR CAMPAÑA REAL").
3. `sh start_wawa.sh` (el script del propietario) desde esa carpeta →
   `GET /` devuelve el HTML nuevo (17662 bytes, pestañas presentes).

Conclusión: **el artefacto entregado sirve la interfaz nueva**. La pantalla
que describe el propietario (Cargar demo, Nueva oportunidad, Motor, Economía
simulada, Actividad en vivo, Proveedor mock) es **idéntica en las
iteraciones 009 y 010** — son el topbar y el sidebar, que no cambiaron. Lo
único que distingue la 010 son las pestañas nuevas; su ausencia en la
pantalla del propietario significa que su navegador estaba mostrando el
**HTML de la iteración 009** (u otro antiguo). Vectores verificados:

- **V1 — Caché heurística del navegador/proxy**: el frontend se servía SIN
  cabeceras `Cache-Control` y con URLs sin versión (`/app.js`, `/styles.css`,
  `/`). El navegador puede reutilizar la página antigua aunque se reinicie el
  servidor y se re-descarque el paquete: reproduce EXACTAMENTE el síntoma
  ("mismo resultado visual siempre", descartado como "caché simple" porque
  rehacer el proceso no cambia nada).
- **V2 — Canal de entrega roto**: `raw.githubusercontent.com/jarmy90/WAWA/...`
  devuelve **404** porque el repositorio es **PRIVADO** (verificado con
  `gh api repos/jarmy90/WAWA` → `private`). Los enlaces "RAW descargable"
  publicados desde la iteración 007 nunca fueron accesibles públicamente; el
  propietario/supervisor no recibió el artefacto verificado por el canal
  publicado (o recibió una descarga antigua).
- **V3 — Sin marcador de versión visible**: con una página obsoleta en
  pantalla no había forma de distinguir qué build se estaba sirviendo, lo que
  impidió diagnosticar y alargó el ciclo.

## Correcciones aplicadas

1. **Sin caché en el frontend** (`app/main.py`): nuevo `NoCacheStaticFiles`
   que añade `Cache-Control: no-store` a todas las respuestas estáticas.
   El navegador ya no puede reutilizar HTML/JS/CSS antiguos.
2. **Assets con versión** (`frontend/index.html`): `/styles.css?v=011` y
   `/app.js?v=011` — aunque una copia antigua del HTML quedara en caché, las
   URLs de JS/CSS cambian y fuerzan la descarga nueva.
3. **Marcador de versión visible y autochequeo** (`frontend/index.html` +
   `frontend/app.js`): `data-wawa-version="0.11.0"` en `<html>`, chip
   `#wawa-version` en el topbar (v0.11), y `loadHealth()` compara la versión
   del HTML con `GET /api/health` (ahora `0.11.0`); si divergen, aparece un
   banner rojo "Frontend desactualizado — Ctrl+F5".
4. **Eliminado el botón MQL5** (`#btn-demo` "Cargar demo"): fuera del
   frontend (HTML + handler JS). El endpoint `/api/demo/load` se conserva
   (lo usan los tests) pero la interfaz operativa ya no promueve la demo
   MQL5.
5. **Franja de estado siempre visible** (`#status-strip`): muestra PRE_CYCLE
   (o ciclo activo con días restantes), estado de la campaña real y próxima
   acción en la parte superior del contenido, con botones "Ir a Campaña
   real" y "Descargar CSV". Se refresca cada 15 s con el resto del panel.
6. **Pestañas a prueba de viewport** (`frontend/styles.css`):
   `.view-tabs { flex-wrap: wrap }` — ninguna pestaña puede quedar cortada
   en ventanas estrechas.
7. **Versión del servidor** actualizada a `0.11.0` (`app/core/config.py` y
   `app/__init__.py`).

## Prueba de aceptación (la que exige el propietario)

Ejecutada sobre el paquete 011 final en carpeta completamente limpia
(`/tmp/wawa-accept-011`):

1. Extraído el paquete 011 en carpeta limpia. ✅
2. Inicializado como lo hace el propietario (`sh start_wawa.sh`). ✅
3. Abierta la web (`http://127.0.0.1:8770/`). ✅
4. Capturado `GET /` real: HTML nuevo con las 6 pestañas. ✅
5. `tab-orchestrator` y `tab-ideas` presentes en la página servida. ✅
6. `POST /api/orchestrator/start` (INICIAR CAMPAÑA REAL) responde 200 y
   crea la campaña (estado RESEARCH_PENDING, 60+ conceptos). ✅
7. `GET /api/orchestrator/runs/{id}/exports/csv` y `/exports/md` devuelven
   200 con contenido real. ✅
8. "Cargar demo" y "MQL5" NO aparecen en el HTML servido. ✅
   (grep del HTML servido: 0 coincidencias)
9. Cabecera `Cache-Control: no-store` presente en `/`, `/app.js`,
   `/styles.css`. ✅

## Archivos modificados

- `app/main.py` (NoCacheStaticFiles)
- `app/core/config.py` (version 0.11.0)
- `app/__init__.py` (__version__ 0.11.0)
- `frontend/index.html` (versión, assets versionados, sin botón demo,
  banner de versión, franja de estado)
- `frontend/app.js` (autochequeo de versión, loadStatus, sin handler demo)
- `frontend/styles.css` (flex-wrap de pestañas, estilos de franja/banner)
- `README.md`, `COMO_ABRIR_WAWA.md`, `docs/ITERATION_HISTORY.md`
- `deliverables/ITERATION_011_MANIFEST.md`

## Validación

- **283 tests** pasan (`python3 -m pytest tests/`).
- `node --check frontend/app.js` OK.
- Prueba de aceptación completa (8 pasos) en carpeta limpia sobre el
  artefacto final.

## Nota sobre el canal de entrega

El repositorio `jarmy90/WAWA` es **privado**: los enlaces RAW de GitHub
devuelven 404. Los paquetes deben descargarse desde la UI de GitHub (con la
cuenta propietaria), desde el workspace de Freebuff, o distribuirse por otro
canal con acceso. Si se desea un enlace RAW público, el repositorio debe
hacerse público o usarse un release con adjuntos.

- **Nombre del paquete**: autonomous-business-lab_iteracion-011_2026-08-23.zip.txt

- **Tamaño del paquete**: 459020 bytes

- **SHA-256 del paquete**: 517c84b0af2501fe78c7cf6e831c21f0408cc00ef2a8ebb98a0ec34cd1b8e01d
