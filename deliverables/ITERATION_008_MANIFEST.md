# Manifiesto ITERACIÓN 008 — Evaluación e integración aislada de OmniRoute

- **Identificador**: 008
- **Fecha y hora**: 2026-08-23 (UTC)
- **Objetivo**: integrar **OmniRoute** (gateway local OpenAI-compatible, MIT)
  como proveedor **opcional, aislado y desactivado por defecto**, con
  allowlist de conexiones, routing por tarea, perfil Docker separado,
  benchmark A/B con datos sintéticos y documentación honesta de riesgos.
  **No** sustituye a OpenRouter, **no** se activa Discovery general, **no**
  se activa producción y **no** se mueve dinero.
- **Estado**: Implementado + probado automáticamente + verificado por API.
  Arranque real del gateway **pendiente** (ENOSPC en el sandbox).

## Resumen de cambios

- Proveedor `OmniRouteProvider` (OpenAI-compatible, `x-omniroute-cli-token`,
  `auto` passthrough, retries acotados, timeout, topes de tokens, costes
  honestos, sin fabricación).
- Routing por tarea (`app/core/routing_policies.py`): políticas por tarea
  con proveedor principal, fallbacks, requisitos JSON, modelo fijo vs. libre.
- Allowlist de conexiones (`app/core/omniroute_allowlist.py`): UNKNOWN ⇒
  bloqueado para producción; solo el gateway local está en TEST_ONLY.
- `ReviewService.auto_review_omniroute`: 2º revisor opcional del comité con
  los mismos guardas que OpenRouter; si está desactivado o falla → **ausencia
  neutral** (nunca revisión mock presentada como real).
- Columnas nuevas en `llm_call_log` (migración idempotente):
  `actual_provider`, `routing_strategy`, `fallback_reason`,
  `response_is_external`, `response_is_synthetic`, `quota_state`.
- Perfil Docker aislado `infra/omniroute/docker-compose.omniroute.yml`
  (solo `127.0.0.1:20128`, sin privilegios, health check, restart, límites).
- Endpoints: `GET /api/providers/omniroute/status`,
  `GET /api/routing/policies`, `POST .../auto-review-omniroute`.
- Benchmark A/B: `scripts/benchmark_ab.py` (10 problemas sintéticos, no
  MQL5; arm A offline ejecutado; brazos B/C/D pendientes de gateway real).
- Frontend: tarjeta de estado OmniRoute en el panel (sin claves).

## Archivos nuevos

- `app/providers/omniroute.py`
- `app/core/routing_policies.py`
- `app/core/omniroute_allowlist.py`
- `app/models/llm_call.py` (ampliado, ver modificados)
- `infra/omniroute/docker-compose.omniroute.yml`
- `scripts/benchmark_ab.py`
- `tests/test_omniroute.py` (23 tests)
- `docs/OMNIROUTE_RESEARCH.md`
- `docs/OMNIROUTE_SECURITY.md`
- `docs/OMNIROUTE_DEPLOYMENT.md`
- `docs/OMNIROUTE_PROVIDER_POLICY.md`
- `docs/OMNIROUTE_MODEL_SELECTION.md`
- `docs/OMNIROUTE_TERMS_RISK.md`
- `deliverables/ITERATION_008_MANIFEST.md` (este archivo)

## Archivos modificados

- `app/core/config.py` (config OMNIROUTE_*)
- `app/repositories/db.py` (columnas nuevas idempotentes)
- `app/repositories/llm_calls.py` (nuevos campos)
- `app/models/llm_call.py` (nuevos campos)
- `app/providers/manager.py` (proveedor aislado, fuera de auto-resolución)
- `app/services/reviews.py` (`auto_review_omniroute`)
- `app/api/routes.py` (3 endpoints nuevos)
- `frontend/app.js` (tarjeta OmniRoute)
- `env.example` (variables documentadas, sin valores)
- `.gitignore` (`data/benchmark/`)
- `README.md`, `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`,
  `docs/ROADMAP.md`

## Archivos eliminados

- Ninguno.

## Cambios arquitectónicos

- OmniRoute corre como **servicio externo** (nunca dentro de WAWA; sin fork,
  sin copia del repo, sin dependencias Node en el backend).
- El proveedor **no** entra en la resolución automática del `ProviderManager`;
  solo se invoca explícitamente desde el comité (2º revisor opcional).

## Cambios en agentes/scoring/reglas

- Sin cambios en scoring. Nueva regla AGENTS.md nº 10 (OmniRoute aislado,
  sin inventar slugs, sin sustituir el modelo fijo del comité).

## Cambios en seguridad

- Allowlist de conexiones con UNKNOWN ⇒ bloqueado en producción.
- Errores saneados; clave del gateway solo en el gestor de secretos.
- No fabricación: fallo ⇒ ausencia neutral.
- No envía datos sensibles a proveedores upstream.

## Dependencias añadidas/retiradas

- **Ninguna**. `urllib` stdlib; perfil Docker opcional para el gateway
  (no se instala por defecto).

## Comandos

- Instalar: `pip install -e .` (sin dependencias nuevas).
- Ejecutar: `uvicorn app.main:app` (OmniRoute desactivado por defecto).
- Probar: `python3 -m pytest tests/`.
- Benchmark: `python3 scripts/benchmark_ab.py --arm A`.
- Gateway (opcional): `docker compose -f infra/omniroute/docker-compose.omniroute.yml up -d`.

## Resultado exacto de las pruebas

- `python3 -m pytest tests/` → **248 passed** (225 previos + 23 nuevos), 1
  warning, 10.42 s.
- `node --check frontend/app.js` → OK.
- `py_compile` de módulos nuevos → OK.
- **17/17 comprobaciones en vivo por HTTP** (TestClient): estado OmniRoute
  desactivado, sin claves en respuestas, routing sin OmniRoute cuando está
  desactivado, `auto-review-omniroute` → `skipped`/`omniroute_disabled` sin
  fabricar revisión, economía simulada, producción bloqueada.
- Benchmark arm A (offline): 10/10 OK, avg score 33.4, avg latencia 6 ms
  (etiquetado SINTÉTICO, no evidencia de mercado).

## Problemas conocidos / limitaciones

- **No se pudo arrancar OmniRoute en el sandbox** (`npm install` → ENOSPC,
  disco insuficiente). Las pruebas reales controladas (máx. 5 llamadas de la
  iteración) y la consulta del catálogo quedan **pendientes** para un entorno
  con disco suficiente.
- **"Alpha 0" no existe** en el catálogo analizado (código fuente
  `release/v3.8.50`): no se inventa el slug; `auto` es el predeterminado
  provisional.
- Telemetría del gateway, structured outputs reales y estabilidad de modelos
  gratuitos: **no verificados** (marcados en la documentación).

## Riesgos abiertos

- Dependencia de tiers gratuitos upstream (frágil por naturaleza).
- Algunos proveedores requieren OAuth/sesiones web (bloqueados por defecto).
- Sin auditoría real de telemetría del gateway.

## Deuda técnica

- `data/benchmark/` es salida de tests (ignorada por Git).
- El benchmark brazos B/C/D requieren el gateway desplegado.

## Componentes para revisión del supervisor

- `app/providers/omniroute.py` (aislamiento, saneamiento de errores,
  costes honestos, `actual_model`).
- `app/core/omniroute_allowlist.py` (regla UNKNOWN ⇒ bloqueado).
- `app/core/routing_policies.py` (no sustitución silenciosa del comité).
- `app/services/reviews.py` `auto_review_omniroute` (no fabricación).
- `infra/omniroute/docker-compose.omniroute.yml` (aislamiento Docker).
- `docs/OMNIROUTE_*.md` (honestidad de lo verificado vs. pendiente).

## Próxima acción recomendada

Desplegar OmniRoute en un entorno con disco suficiente, ejecutar las 5
llamadas reales, consultar el catálogo (buscar "Alpha 0" con evidencia),
cerrar el benchmark A/B (brazos B/C/D vs. A) y **solo entonces** evaluar si
OmniRoute aporta valor para Discovery. Mientras tanto, seguir con el comité
OpenRouter (Opción A) sobre finalistas reales.

- **Nombre del paquete**: autonomous-business-lab_iteracion-008_2026-08-23.zip.txt

- **Tamaño del paquete**: 391267 bytes

- **SHA-256 del paquete**: 39db98c953a556bfd5c119f8f095d42760206b955707ea8fb7bf65b74839316e
