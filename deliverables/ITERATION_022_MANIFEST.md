# Manifiesto de iteración 022

- **Identificador de iteración**: 022
- **Fecha y hora**: 2026-08-26
- **Objetivo**: One-Click Owner Activation — corregir el demo persistente,
  eliminar toda operación manual (PowerShell/scripts/IDs) y activar en la
  instalación del propietario el bootstrap comercial 021 con un solo doble
  clic en `START_WAWA.bat` (instalación limpia, FAILED o parcial).
- **Estado**: `entregado`

## Resumen de cambios

Implementado y probado automáticamente (suite **423 passed**; 30 tests
nuevos, `node --check` OK, verificación visual con navegador real):

1. **Modo demo corregido** (causa del demo persistente): el estado demo vive
   SOLO en memoria (`frontend/viz-core.js`); `?demo=1` se elimina de la URL
   en la misma carga con `history.replaceState` (refrescar/reiniciar WAWA
   nunca reactiva demo); al salir se limpian claves demo de
   localStorage/sessionStorage; el botón indica `ACTIVAR DEMO` / `SALIR DE
   DEMO` según el estado real; `data_nature=DEMO` nunca se mezcla con `REAL`.
   Verificado con `scripts/demo_state_smoke.js` (headless) y en navegador
   real (clic en SALIR DE DEMO → URL sin `?demo`).
2. **Causa del error PowerShell**: el propietario ejecutó
   `.venv\Scripts\python.exe scripts\activate_commercial_021.py` desde
   `C:\Users\j` (fuera de la carpeta de WAWA). `START_WAWA.bat` ahora hace
   `cd /d "%~dp0"`, gestiona el `.venv` (crea si falta, reutiliza si existe)
   con rutas entre comillas (soporta espacios), y es el único punto de
   entrada: doble clic → flujo `[1/7]…[7/7]` → bootstrap comercial →
   navegador. Sin comandos manuales.
3. **CommercialBootstrapService**
   (`app/services/commercial_bootstrap.py`): servicio interno idempotente y
   transaccional con checkpoints append-only que convierte la lógica de
   `scripts/activate_commercial_021.py` + `readiness_launch_021.py`. Detecta
   instalación nueva / incompleta / FAILED recuperable, materializa las 3
   candidatas del paquete portable en la campaña LOCAL (resolución por título
   normalizado; **nunca inserta IDs de otra base**), importa idempotentemente
   18 misiones y 31 evidencias verificadas, recalcula puntuaciones (7 grupos
   independientes), selecciona la ganadora determinista, crea/recupera el
   experimento, encola la ganadora en el comité y deja
   `READY_TO_CONNECT_SERVICES`. PRE_CYCLE detenido, gasto real 0, producción
   bloqueada; cada paso en `decision_log`; reanudable tras corte.
4. **Activos integrados** `resources/bootstrap/commercial_021/`: manifiesto
   inmutable por versión (checksum SHA-256), investigación portable y
   tarjetas de candidatas; sin secretos, sin SQLite, sin logs;
   `buyer_confirmed` como HIPÓTESIS; evidencia solo URL + fecha + fragmento.
5. **Panel y rutas**: `/candidates` (CANDIDATAS en el menú: 3 tarjetas con
   puntuación estructural/con evidencia, evidencias verificadas, grupos,
   comprador, problema, oferta, precio hipótesis, canal, alternativas,
   fuentes, contradicciones, riesgos, kill condition; la ganadora muestra
   `GANADORA DETERMINISTA PARA EXPERIMENTO`, nunca demanda validada);
   comité directo (COPIAR PARA GPT/GROK/GEMINI, DESCARGAR EXPEDIENTE .MD,
   PEGAR RESPUESTA, IMPORTAR ARCHIVO COMBINADO; wizard PASO 1·COPIAR /
   PASO 2·PEGAR / PASO 3·SÍNTESIS con estados pendiente/importado/válido;
   ausencia de revisión = neutral); botón `REPARAR Y CONTINUAR
   AUTOMÁTICAMENTE` con `VER DIAGNÓSTICO` (solo si FAILED / falta activación;
   sin stack traces); asistente `CONECTAR SERVICIOS`
   (`/api/services/status|save|check`: estado CONNECTED/PARTIAL/INVALID/
   MISSING + últimos 4 caracteres; secretos fuera de Git, nunca por API,
   logs ni paquetes; GitHub permanece CONNECTED).
6. **Arranque automático**: `scripts/startup_bootstrap.py` se ejecuta en el
   arranque (pasos [4/7]-[6/7]); si ya está aplicado imprime
   `BOOTSTRAP COMERCIAL YA APLICADO` y no cambia nada; si falla, el panel
   ofrece reparación con un clic.
7. **Verificación visual real**: Playwright + Chromium temporal (fuera del
   paquete) → 9 capturas PNG en `deliverables/iteracion_022_capturas/`
   (inicio tras bootstrap, candidatas, tarjeta ganadora, wizard, Mission
   Control sin demo / con demo / tras salir de demo, CONECTAR SERVICIOS,
   móvil). URL sin `?demo` tras salir de demo confirmada en navegador.
8. **Recuperación real probada**: sobre la base real 021 del sandbox
   (instalación parcial: run RESEARCH_IMPORTED sin marcador de bootstrap),
   `POST /api/bootstrap/commercial` aplicó el marcador sin duplicar
   misiones/evidencias y mantuvo `READY_TO_CONNECT_SERVICES`.

Versión v0.21.0 / build 022-one-click-activation. Sin gasto real (0 EUR),
PRE_CYCLE detenido, producción bloqueada por diseño. `data/abl.db` NO se
incluye en el paquete; la base se crea y se activa sola en la instalación
del propietario.

## Archivos clave

- `app/services/commercial_bootstrap.py` · `app/services/connect_services.py`
- `app/repositories/db.py` (tablas `commercial_bootstrap_state`,
  `bootstrap_checkpoints`) · `app/api/routes.py` · `app/main.py`
- `resources/bootstrap/commercial_021/` (manifiesto + investigación +
  candidatas)
- `START_WAWA.bat` · `scripts/startup_bootstrap.py` ·
  `scripts/demo_state_smoke.js` · `scripts/capture_screenshots_022.py`
- `frontend/candidates.html/css/js` · `frontend/viz-core.js` ·
  `frontend/mission-control.js/html` · `frontend/agents-viz.js/html`
- `COMO_ABRIR_WAWA.md` (recorrido normal de 7 pasos) ·
  `docs/ITERATION_HISTORY.md`
- `tests/test_activation_commercial_022.py` (30 tests)

## Verificación

- Suite completa: **423 passed** · `node --check` OK (viz-core,
  mission-control, agents-viz, candidates, demo_state_smoke, viz_smoke)
- Demo smoke headless: `DEMO_STATE_SMOKE_OK` (6 casos)
- Servidor real: `/candidates`, `/mission-control`, `/agents-viz` → 200;
  `/api/bootstrap/status`, `/api/candidates`, `/api/services/*`,
  `/api/agent-telemetry` → honestos (REAL, sin demo, sin secretos)
- Navegador real (Chromium): 9 capturas; salir de demo limpia la URL
- Paquete verificado 15/15 · hashes canónico y completo · commit · push ·
  enlaces RAW comprobados

- **Nombre del paquete**: autonomous-business-lab_iteracion-022_2026-08-26.zip.txt

- **Tamaño del paquete**: 9303052 bytes

- **SHA-256 del paquete**: 999fdd5c2f3c70d95d4728d19ddb8c65f31fb9df147afcfc6e98b978171f71b1
