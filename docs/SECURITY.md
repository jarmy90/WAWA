# Seguridad — modelo de amenazas y mitigaciones

## Alcance

Aplicación local (MVP) con API FastAPI y dashboard servido por la misma app.
Sin autenticación de usuarios en esta versión (entorno local/desarrollo).

## Modelo de amenazas inicial

| # | Amenaza | Riesgo | Mitigación |
|---|---|---|---|
| 1 | Ejecución de código generado (por IA o por importaciones) | **Alto** | El sistema **nunca ejecuta código** generado ni importado. No existe ruta de ejecución de código arbitrario (sin `eval`/`exec`, sin subprocesos de usuario). |
| 2 | Inyección SQL | Medio | 100% SQL parametrizada a través de repositorios. Sin interpolación de cadenas. |
| 3 | Command injection | Medio | No se ejecutan comandos del sistema con entrada de usuario. |
| 4 | Path traversal | Medio | IDs validados como UUID hex (32 chars); rutas de archivo internas fijas (`data/`, `frontend/`); extensiones de importación en lista blanca (`.json`). |
| 5 | Payloads abusivamente grandes | Medio | `MAX_UPLOAD_BYTES` (por defecto 1 MB) comprobado por `Content-Length`; límites de longitud en todos los campos Pydantic. |
| 6 | Fuga de secretos | Medio | `.env` en `.gitignore`; `env.example` sin valores; logging con `redact()` para claves/tokens; errores internos no exponen trazas (handler 500 genérico). |
| 7 | Datos inventados como "evidencia" | Medio (integridad) | Toda evidencia lleva `method`, `reliability_score`, `verified` y `verification_notes`; el scoring penaliza lo no verificado; el Judge marca bases `evidence/estimate/unknown`. |
| 8 | Fraude financiero / asesoramiento no regulado | Medio | Sin operaciones financieras; Compliance bloquea promesas de rentabilidad; la interfaz avisa de que el análisis es de software, no asesoramiento. |
| 9 | Exfiltración de datos externos | Bajo | Sin scraping automático; solo se guardan URL, fecha, fragmento breve, resumen y fiabilidad. |
| 10 | Envenenamiento de prompts a Gemini | Bajo-Medio | La salida de Gemini nunca se trata como evidencia verificada (solo hipótesis). El sistema no ejecuta sus instrucciones. |
| 11 | CSRF/XSS en el dashboard | Bajo (local) | Escape HTML en el frontend (`esc()`); sin cookies de sesión; CORS por defecto `*` solo en desarrollo. Revisar antes de exponer. |
| 12 | Abuso de costes de API | Medio | BudgetGuard: presupuesto diario/por oportunidad, tope de evaluaciones profundas/día, modos gratuito/simulación, bloqueo manual, registro por acción. |
| 13 | Manipulación del ledger (saldo falso) | **Alto** | Ledger append-only: los asientos confirmados no se editan ni se borran; el saldo se deriva siempre de los movimientos (nunca se persiste un saldo editable); `idempotency_key` UNIQUE; reversiones vinculadas con doble reversión bloqueada; reconciliación que reconstruye saldos desde cero y entra en `SAFE_PAUSE` ante inconsistencias graves. |
| 14 | Confundir simulación con dinero real | **Alto** | Toda respuesta económica incluye `simulated: true` y `real_money_moved: false`; el dashboard muestra "SIMULACIÓN — NO REPRESENTA DINERO REAL"; no existe integración bancaria, Stripe, wallet ni cripto; AUTONOMOUS_PRODUCTION bloqueado por capacidad. |
| 15 | Activación de producción no autorizada | **Alto** | Una variable de entorno puede, como máximo, alcanzar `PRODUCTION_ARMED` (con precondiciones económicas); la activación final exige `production_capability_available=true` + `ENGINE_ACTIVATION_KEY`; arranque con configuraciones inconsistentes ⇒ `SAFE_PAUSE` auditado. |
| 16 | Envenenamiento de metadata contable | Bajo | `metadata` de asientos limitada a 4 KB y validada; importes en Decimal con redondeo fijo; moneda distinta de la base rechazada; importes negativos rechazados. |

## Prácticas obligatorias

- **Nunca** ejecutar código generado por el sistema o por agentes sin sandbox.
- **Nunca** almacenar secretos en Git.
- **Validar todas las entradas** (Pydantic + utilidades de `core/security.py`).
- **No** realizar operaciones financieras reales, trading, envíos masivos ni
  publicaciones automáticas. La economía es 100% simulada y etiquetada como
  tal.
- **No** permitir que un prompt altere el ledger directamente: solo los
  servicios contables (deterministas) crean asientos.
- **No** almacenar más contenido externo del necesario (URL, fecha, fragmento,
  resumen, fiabilidad).

## Comité de contraste: respuestas importadas como datos no confiables

Desde la iteración 005, las respuestas de modelos externos (TXT/Markdown/JSON)
se tratan como **datos no confiables** (ver `docs/REVIEW_SECURITY.md`):

- Se conservan verbatim (`raw_response`) con su SHA-256; el parsing usa una
  **allowlist** de claves y nunca interpreta el contenido como instrucciones.
- Límites de tamaño (200 KB) y lista blanca de extensiones (`.txt`, `.md`,
  `.markdown`). Duplicados por hash → 409.
- Frases típicas de prompt injection se **señalan** en warnings, sin ejecutarse.
- Los servicios de revisión no tienen acceso a modo/budget/economía: una
  revisión no puede autorizar producción, mover dinero ni cambiar límites
  (verificado por tests).

## Zonas de confianza

```
[ Entrada (API) ] → validación → [ Lógica (agentes/scoring) ] → [ SQLite ]
                                       │
                    [ Proveedores LLM (mock/gemini/manual) ]  ← nunca se confía
                                       │
                    [ Salida (dashboard/export) ] ← escape HTML en frontend
```

## Campañas Freebuff-first (iteración 006)

- **Sin API runtime de Freebuff**: no se finge un endpoint que no existe; el
  trabajo se ejecuta por sesiones reanudables y cada sesión deja checkpoint.
- **Coste API 0**: `api_budget_usd=0` en descubrimiento; un `SESSION_OUTPUT`
  con llamadas o coste > 0 se rechaza (política permanente, probada).
- **Outputs como datos no confiables**: `SESSION_OUTPUT.json` se valida con
  Pydantic (`extra=forbid`, tamaños, no negativos); los conceptos se
  deduplican; las evidencias exigen URL+fecha+fragmento para `verified=true`.
- **API Readiness Gate**: nunca configura claves ni consume nada; solo
  produce una propuesta determinista y auditable.
- **No inventar capacidades**: ver `docs/FREEBUFF_WORKFLOW.md` (qué puede y
  qué no puede garantizar Freebuff fuera de la sesión).

## OpenRouter y costes de inferencia (iteración 007)

- **Opción A**: OpenRouter solo para el comité de contraste de finalistas, con
  guardas deterministas (máx. 1 revisión por oportunidad, límites diarios y
  mensuales de peticiones/coste, circuit breaker, reintentos acotados).
- **Coste honesto por llamada** en `llm_call_log` (append-only): `reported_cost`
  solo si el proveedor lo devuelve; si no, `None` + `cost_source` (FREE_TIER /
  UNKNOWN) y estimación etiquetada aparte. `billing_verified=false` hasta que
  exista reconciliación real con facturación. Un coste desconocido nunca se
  convierte en cero.
- **Sin fabricación**: si la llamada falla o no hay clave, no se genera ninguna
  revisión (el fallback a mock nunca se presenta como revisión real); la
  ausencia de revisión es neutral.
- **La clave vive en el gestor de secretos** (`.env.local`/Settings → Keys),
  nunca en Git ni en `env.example`.

## OmniRoute (iteración 008 — proveedor aislado)

- **Aislado y desactivado por defecto** (`OMNIROUTE_ENABLED=false`); el
  backend nunca depende de él para arrancar, testear o funcionar.
- Solo local: `127.0.0.1:20128`, perfil Docker opcional con contenedor sin
  privilegios, filesystem de solo lectura, health check, límites de
  CPU/memoria, logs rotativos y sin Docker socket.
- **Allowlist de conexiones** (`app/core/omniroute_allowlist.py`):
  `UNKNOWN` ⇒ bloqueado para producción. Solo el gateway local está en
  `TEST_ONLY`; ningún proveedor upstream está autorizado.
- **Sin fabricación**: fallo ⇒ ausencia neutral (no hay revisión mock
  presentada como real, no hay evidencia, no hay cambio de decisión).
- Costes honestos en `llm_call_log` con las columnas OmniRoute
  (`actual_provider`, `routing_strategy`, `fallback_reason`,
  `response_is_external/synthetic`, `quota_state`).
- Errores saneados (sin cabeceras de autenticación ni cuerpos con secretos);
  la clave del gateway solo vive en el gestor de secretos.
- No envía secretos, wallets, datos personales, credenciales ni información
  financiera sensible a proveedores upstream.
- No activa producción, no modifica presupuestos, no sustituye el modelo fijo
  del comité OpenRouter.

## Local por defecto (iteración 010)

- El panel escucha en **`127.0.0.1`** por defecto (`start_wawa.sh` /
  `START_WAWA.bat`); no se declara seguro exponerlo a Internet.
- **CORS restringido** a `http://127.0.0.1:8000` y `http://localhost:8000`
  (ya no `*`) — `settings.cors_origins`.
- Las respuestas importadas (datos no confiables) se escapan con `esc()`
  antes de entrar en `innerHTML`; hay test de escape XSS con contenido
  hostil (`tests/test_orchestrator_010.py`).

## Si esto se expone a internet (futuro)

- Añadir autenticación/authorization (Convex Auth u OIDC) y control de acceso.
- Revisar límites de tasa por IP.
- Mover claves a secretos gestionados; rotación.
- Auditoría de `decision_log` como dato inmutable (backup).
- TLS, gestión de sesiones y protección de endpoints administrativos.
