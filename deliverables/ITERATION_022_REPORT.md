# Informe de iteración 022 — One-Click Owner Activation (v0.21.0)

1. **Número de iteración**: 022.
2. **Objetivo**: One-Click Owner Activation — corregir el demo persistente de
   Mission Control y eliminar TODA operación manual del propietario
   (PowerShell, scripts, copias de bases, elección de JSON, IDs internos):
   que Javier descargue, extraiga, doble clic en `START_WAWA.bat` y WAWA
   detecte instalación nueva/incompleta/FAILED, aplique idempotentemente el
   bootstrap comercial 021 y deje las 3 candidatas investigadas, la ganadora
   determinista y `READY_TO_CONNECT_SERVICES`, con comité, asistente de
   servicios y autorización del ciclo de 30 días accesibles desde el panel.
3. **Resumen del trabajo realizado**: (a) reproducido y corregido el demo
   persistente — el estado demo vive SOLO en memoria, `?demo=1` se elimina de
   la URL en la misma carga con `history.replaceState`, al salir se limpian
   claves demo de localStorage/sessionStorage, el botón indica
   `ACTIVAR DEMO` / `SALIR DE DEMO` según el estado real, refrescar y
   reiniciar WAWA nunca reactivan demo, y `data_nature=DEMO` nunca se mezcla
   con `REAL`; (b) diagnosticada la causa del error PowerShell (el propietario
   ejecutó el script fuera de la carpeta de WAWA) y eliminada la causa raíz:
   `START_WAWA.bat` hace `cd /d "%~dp0"`, crea/reutiliza `.venv` con rutas
   entre comillas y es el único punto de entrada (7 pasos `[1/7]…[7/7]` →
   bootstrap → navegador); (c) `CommercialBootstrapService` interno,
   idempotente y transaccional con checkpoints append-only que convierte la
   lógica de `activate/readiness_021`; (d) activos integrados en
   `resources/bootstrap/commercial_021/` (manifiesto inmutable con checksum,
   investigación portable, tarjetas de candidatas); (e) panel: `/candidates`,
   comité directo con wizard de 3 pasos, botón `REPARAR Y CONTINUAR
   AUTOMÁTICAMENTE`, asistente `CONECTAR SERVICIOS`; (f) arranque automático
   (`scripts/startup_bootstrap.py`); (g) verificación visual real con
   Chromium (9 capturas); (h) suite 423 passed; (i) paquete verificado y
   publicado.
4. **Archivos nuevos**: `app/services/commercial_bootstrap.py`,
   `app/services/connect_services.py`, `frontend/candidates.html/css/js`,
   `scripts/startup_bootstrap.py`, `scripts/demo_state_smoke.js`,
   `scripts/smoke_bootstrap_022.py`, `scripts/debug_phase1_022.py`,
   `scripts/build_candidatas_asset_022.py`,
   `scripts/capture_screenshots_022.py`,
   `tests/test_activation_commercial_022.py` (30 tests),
   `resources/bootstrap/commercial_021/` (manifest.json,
   investigacion_fase1_021.json, candidatas.json),
   `deliverables/ITERATION_022_MANIFEST.md`,
   `deliverables/ITERATION_022_REPORT.md`,
   `deliverables/iteracion_022_capturas/` (9 PNG).
5. **Archivos modificados**: `START_WAWA.bat`, `COMO_ABRIR_WAWA.md`,
   `app/main.py`, `app/api/routes.py`, `app/core/config.py` (v0.21.0),
   `app/core/container.py`, `app/repositories/db.py` (tablas
   `commercial_bootstrap_state`, `bootstrap_checkpoints`),
   `app/services/command_center.py`, `frontend/index.html`,
   `frontend/mission-control.html/js/css`, `frontend/agents-viz.html/js`,
   `frontend/viz-core.js`, `tests/test_mission_control_020.py`,
   `tests/test_ox_alpha_sprint_018.py`, `docs/ITERATION_HISTORY.md`.
6. **Archivos eliminados**: ninguno.
7. **Decisiones técnicas**: (a) el estado demo vive solo en memoria y la URL
   se limpia en la misma carga (refrescar/reiniciar no reactivan demo); no
   persiste ninguna preferencia de demo; (b) el bootstrap es un servicio
   interno transaccional con checkpoints append-only, reanudable tras corte y
   sin duplicar misiones/evidencias; (c) las candidatas se materializan en la
   campaña LOCAL por mapeo estable de título normalizado — nunca se insertan
   IDs foráneos de otra base; (d) `START_WAWA.bat` es el único punto de
   entrada: cd al directorio real, `.venv` gestionado, rutas entre comillas;
   (e) secretos fuera de Git, nunca devueltos por API, logs ni paquetes — el
   asistente de servicios solo muestra estado + últimos 4 caracteres;
   (f) el arranque aplica el bootstrap si falta y, si falla, el panel ofrece
   `REPARAR Y CONTINUAR AUTOMÁTICAMENTE` con `VER DIAGNÓSTICO` sin stack
   traces.
8. **Dependencias añadidas o retiradas**: ninguna dependencia de runtime
   añadida. Verificación visual con Playwright/Chromium temporal, fuera del
   paquete y del repositorio (no es dependencia del producto).
9. **Cambios en arquitectura**: dos servicios nuevos
   (`commercial_bootstrap.py`, `connect_services.py`) dentro de la
   arquitectura modular existente; el bootstrap ejecuta la lógica que antes
   vivía en scripts operativos (`activate/readiness_021`), ahora como
   servicio interno idempotente; el arranque de la aplicación lo invoca
   automáticamente.
10. **Cambios en modelos de datos**: dos tablas nuevas en SQLite
    (`commercial_bootstrap_state`, `bootstrap_checkpoints`) creadas con
    `CREATE TABLE IF NOT EXISTS` (migración idempotente, compatible con bases
    anteriores); todo append-only, sin ediciones.
11. **Cambios en prompts o agentes**: ninguno. El bootstrap materializa
    resultados ya decididos (candidatas, misiones, evidencias, ganadora) como
    datos con trazabilidad; no invoca modelos ni inventa razonamiento.
12. **Cambios en scoring y reglas de decisión**: ninguno. La ganadora sigue
    siendo la decisión determinista de la iteración 021 (torneo + evidencia);
    `evidence_backed_venture_score` y `proven_demand` no se alteran.
13. **Cambios en seguridad o gestión presupuestaria**: refuerzo: los secretos
    de servicios nunca salen por API/logs/paquetes; el diagnóstico no muestra
    stack traces; PRE_CYCLE detenido, gasto real 0, producción bloqueada por
    diseño (el bootstrap nunca la activa).
14. **Pruebas ejecutadas**: `python3 -m pytest` (suite completa),
    `node --check` sobre todos los JS, smoke headless de demo
    (`scripts/demo_state_smoke.js`, 6 casos), smoke de bootstrap en
    instalación limpia y sobre la base real 021 (recuperación idempotente),
    servidor real con TestClient y navegador real (Chromium) para capturas.
15. **Comandos exactos utilizados**: `python3 -m pytest -q`,
    `python3 -m pytest` (423 passed), `node --check frontend/viz-core.js
    frontend/mission-control.js frontend/agents-viz.js frontend/candidates.js
    scripts/demo_state_smoke.js`, `node scripts/demo_state_smoke.js`,
    `python3 scripts/smoke_bootstrap_022.py`,
    `python3 scripts/capture_screenshots_022.py`,
    `python3 scripts/package_for_review.py --iteration 022`,
    `python3 scripts/verify_review_package.py --iteration 022`,
    `git add …`, `git commit`, `git push origin main`.
16. **Número de pruebas superadas**: 423 passed (393 anteriores + 30 nuevas
    de `test_activation_commercial_022.py`).
17. **Número de pruebas fallidas**: 0.
18. **Errores encontrados y correcciones aplicadas**: (a) demo persistente —
    la vista volvía a activar demo al recargar por una lectura temprana de
    `?demo=1`; corregido moviendo el estado a memoria y limpiando la URL en la
    misma carga; (b) error PowerShell del propietario — ejecutaba el script
    desde `C:\Users\j` fuera de la carpeta de WAWA; corregido haciendo que
    `START_WAWA.bat` cambie al directorio real y gestione el `.venv`;
    (c) instalación parcial 021 (RUN RESEARCH_IMPORTED sin marcador) — la
    recuperación probada sobre la base real aplicó el marcador sin duplicar
    misiones/evidencias y mantuvo `READY_TO_CONNECT_SERVICES`.
19. **Comprobaciones manuales realizadas**: verificación visual en navegador
    real: clic en SALIR DE DEMO → URL sin `?demo`; botón ACTIVAR DEMO / SALIR
    DE DEMO según estado; `DEMO DATA · NOT REAL ACTIVITY` desaparece al salir;
    9 capturas PNG (inicio tras bootstrap, candidatas, tarjeta ganadora,
    wizard, Mission Control sin/con/tras demo, CONECTAR SERVICIOS, móvil).
20. **Funcionalidades no verificadas**: ejecución de `START_WAWA.bat` real en
    Windows (el sandbox es Linux; el .bat sigue la sintaxis estándar de
    Windows con rutas entre comillas y `cd /d "%~dp0"`); conexión real de
    servicios de pago (requiere credenciales del propietario); ciclo de 30
    días (requiere autorización del propietario).
21. **Elementos simulados o mock**: `buyer_confirmed` como HIPÓTESIS (sin
    comprador real); la demanda sigue sin validar (`proven_demand=0`); las
    evidencias son URL + fecha + fragmento verificados, nunca opiniones de
    modelos; los servicios muestran estado MISSING hasta que el propietario
    aporte credenciales.
22. **Dependencias de servicios externos**: ninguna obligatoria. Gemini y
    OpenRouter opcionales con fallback a mock; sin claves, sin llamadas
    reales, gasto real 0 EUR.
23. **Limitaciones conocidas**: el paquete no incluye la base SQLite
    (`data/abl.db` se crea y activa sola en la instalación del propietario);
    la verificación visual se hizo con Chromium del sandbox (capturas
    incluidas como evidencia); el .bat no se ha ejecutado en Windows real.
24. **Riesgos abiertos**: si el entorno Windows del propietario no tiene
    Python instalado, `START_WAWA.bat` no puede crear el `.venv` (se informa
    claramente al final del flujo); la recuperación de bases muy antiguas o
    corruptas podría requerir el botón de reparación (automatizado, sin
    comandos manuales).
25. **Deuda técnica**: los scripts `activate/readiness_021` quedan como
    compatibilidad, pero el camino canónico es el servicio interno; el
    `debug_phase1_022.py` es herramienta de diagnóstico temporal.
26. **Elementos concretos que debe supervisar el revisor externo**: (a) el
    flujo doble clic → bootstrap → panel en una instalación limpia real de
    Windows; (b) que el demo nunca reaparezca tras refrescar/reiniciar;
    (c) que el asistente CONECTAR SERVICIOS no exponga secretos y mantenga
    GitHub CONNECTED; (d) que ninguna pantalla declare demanda validada ni
    producción activada.
27. **Instrucciones de instalación y ejecución**: descargar y extraer el
    paquete; doble clic en `START_WAWA.bat` (instala dependencias, crea
    `.venv`, ejecuta migraciones, aplica el bootstrap comercial si falta,
    arranca WAWA y abre el navegador). Nada más. El recorrido completo de 7
    pasos está en `COMO_ABRIR_WAWA.md`.
28. **Próximo paso recomendado**: que el propietario complete el comité
    (copiar/pegar expedientes GPT, Grok, Gemini — ausencia neutral), conecte
    servicios con el asistente gráfico y autorice el ciclo de 30 días para
    pasar de `READY_TO_CONNECT_SERVICES` a `READY_TO_LAUNCH`; en paralelo,
    validar el flujo de `START_WAWA.bat` en Windows real.
