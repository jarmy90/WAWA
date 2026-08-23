# MANIFIESTO ITERACIÓN 007 — OPENROUTER PARA EL COMITÉ (OPCIÓN A)

- **Iteración**: 007
- **Fecha**: 2026-08-23
- **Estado**: COMPLETADA
- **Objetivo**: Usar OpenRouter **únicamente** para el comité de contraste de
  oportunidades finalistas (Opción A), con modelo fijo para comparabilidad,
  contabilidad de costes honesta por llamada, presupuesto de inferencia
  separado y reglas de no-fabricación. NO se activa OpenRouter para el flujo
  Discovery.

## Resumen de cambios

- **Implementado**:
  - `OpenRouterProvider` reescrito: modelo fijo `OPENROUTER_REVIEW_MODEL` +
    router gratuito `OPENROUTER_FALLBACK_MODEL=openrouter/free`; reintentos
    SOLO transitorios acotados a `OPENROUTER_MAX_RETRIES` (nunca infinitos);
    topes `OPENROUTER_MAX_INPUT_TOKENS` / `OPENROUTER_MAX_OUTPUT_TOKENS`;
    registro de `requested_model` vs `actual_model` (el router :free puede
    variar por llamada); tokens de uso; latencia; coste honesto
    (`reported_cost` solo si el proveedor lo devuelve, `cost_source` =
    PROVIDER_RESPONSE | LOCAL_ESTIMATE | FREE_TIER | UNKNOWN,
    `billing_verified=false`; un coste desconocido NUNCA se convierte en
    cero).
  - `llm_call_log` (tabla append-only + `LLMCallRecord` + repositorio) con
    todos los campos exigidos por llamada.
  - `ReviewService.auto_review()`: guardas deterministas en orden — máx. 1
    revisión automática por oportunidad (`OPENROUTER_MAX_REVIEWS_PER_OPPORTUNITY`),
    circuit breaker (`OPENROUTER_CIRCUIT_BREAKER_FAILURES` + cooldown),
    límite diario de peticiones, límite diario y mensual de coste.
    **Llama directamente a `openrouter.generate`** (nunca al manager, que
    podría resolver a mock y fabricar una revisión falsa). Sin clave o con
    fallo: NO se fabrica revisión; se registra en `llm_call_log` y la
    ausencia es neutral.
  - `auto_status()`: presupuesto de inferencia + circuit breaker (sin llamadas).
  - API: `POST /api/reviews/opportunities/{id}/auto-review`,
    `GET /api/reviews/auto-status`, `GET /api/llm-calls`.
  - Frontend: botón **Revisión automática** en el Laboratorio + línea de
    estado OpenRouter (modelo, uso diario, coste, circuit breaker).
  - Config completa: `openrouter_review_model`, `openrouter_fallback_model`,
    `openrouter_timeout_seconds`, `openrouter_max_retries`,
    `openrouter_max_input_tokens`, `openrouter_max_output_tokens`,
    `openrouter_daily_request_limit`, `openrouter_daily_cost_limit_usd`,
    `openrouter_monthly_cost_limit_usd`,
    `openrouter_max_reviews_per_opportunity`,
    `openrouter_circuit_breaker_failures`,
    `openrouter_circuit_breaker_cooldown_seconds`.
- **Probado automáticamente**: 225 tests (215 previos + 10 nuevos).
- **Verificado manualmente**: 17/17 en vivo con UNA llamada real a OpenRouter
  (coste reportado por el proveedor: 0.0003006 USD, `PROVIDER_RESPONSE`,
  `billing_verified=false`, 1179 tokens; el modelo devolvió REJECT para la
  finalista sintética; máx. 1 por oportunidad confirmado).
- **Simulado**: las pruebas offline (sin red). **Pendiente**: reconciliación
  real con facturación; decidir si el valor justifica el coste tras la semana
  gratuita.

## Archivos nuevos

- `app/models/llm_call.py` (LLMCallRecord + CostSource)
- `app/repositories/llm_calls.py`
- `tests/test_openrouter.py` (reescrito: 19 tests del proveedor + auto_review)
- `deliverables/ITERATION_007_MANIFEST.md`

## Archivos modificados

- `app/providers/openrouter.py` (reescrito) — `app/providers/base.py`
  (LLMResponse ampliado) — `app/providers/manager.py` — `app/core/config.py`
  — `app/repositories/db.py` (tabla llm_call_log) — `app/repositories/__init__.py`
  — `app/services/reviews.py` (auto_review + auto_status + _record_call +
  _circuit_breaker) — `app/core/container.py` — `app/api/routes.py` —
  `frontend/app.js` — `env.example` — `README.md` — `AGENTS.md` —
  `docs/{EXTERNAL_MODEL_REVIEW,ARCHITECTURE,SECURITY,ROADMAP,ITERATION_HISTORY}.md`
  — `tests/test_openrouter.py`

## Archivos eliminados

Ninguno.

## Decisiones técnicas

- `auto_review` llama DIRECTAMENTE a `openrouter.generate`: el manager podría
  resolver a mock según `LLM_PROVIDER` y fabricar una revisión falsa (bug
  detectado y corregido durante la iteración).
- El fallback sin coste "permitido" es **no generar revisión** (ausencia
  neutral), nunca sustituir el modelo real por el mock.
- `ExternalReview.cost` usa `reported_cost` si existe, si no la estimación
  etiquetada; la verdad completa vive en `llm_call_log`.
- `billing_verified` es siempre `false` hasta que exista reconciliación real
  con el panel de facturación.
- El modelo del comité es fijo por configuración (comparabilidad); el router
  gratuito es fallback y su modelo real se registra por llamada.

## Cambios en seguridad

- La clave vive en el gestor de secretos (`.env.local` / Settings → Keys),
  nunca en Git; `env.example` solo documenta nombres.
- Límites de inferencia separados del ledger (sin tocar la economía simulada).
- Sin fabricación de revisiones en ningún fallo; log append-only por llamada.

## Dependencias añadidas o retiradas

Ninguna (OpenRouter usa `urllib` de la stdlib).

## Comandos

```bash
pip install -e . && uvicorn app.main:app   # o scripts/run.sh
pytest                                     # 225 tests offline
# Revisión automática (Opción A):
#   POST /api/reviews/opportunities/{id}/auto-review
#   GET  /api/reviews/auto-status
#   GET  /api/llm-calls
```

## Resultado exacto de las pruebas

- `python3 -m pytest tests/` → **225 passed**.
- `node --check frontend/app.js` → OK.
- Validación en vivo → **17/17 PASS** (1 llamada real, coste 0.0003006 USD).

## Problemas conocidos

- `cost_since` del log suma `reported_cost` o `estimated_cost` (etiquetado en
  el campo `cost_source`); no hay reconciliación con facturación real.
- El modelo gratuito `openrouter/free` puede no estar disponible en todas las
  cuentas; si el modelo fijo funciona, no se usa.

## Limitaciones

- Opción A limitada a 1 revisión automática por oportunidad (fase actual).
- La semana gratuita no está garantizada por el sistema: se mide coste real
  cuando el proveedor lo reporta.
- Sin `API_AUTOMATIC` para otros proveedores (GPT/Grok/Gemini siguen vía
  manual `MANUAL_IMPORT`).

## Riesgos

- Agotar la cuota gratuita (mitigado: límites diarios/mensuales + circuit
  breaker + 1 revisión por oportunidad).
- El modelo devuelve contenido no parseable (mitigado: parser con allowlist,
  estado `partial`/`needs_validation`, sin auto-aprobación).

## Componentes que debe revisar el supervisor

1. `app/services/reviews.py::auto_review` (guardas y no-fabricación).
2. `app/providers/openrouter.py` (retries, topes, costes honestos).
3. `llm_call_log` (esquema + repo + cost_since honesto).
4. Tests nuevos (19) y el bug corregido del manager→mock.

## Próxima acción recomendada

Configurar `OPENROUTER_REVIEW_MODEL` con el modelo grande deseado, ejecutar la
Opción A sobre 2-3 finalistas reales durante la semana gratuita, comparar
objeciones frente al Judge solo y decidir tras la semana si el valor justifica
el coste real.

## Nombre del paquete

autonomous-business-lab_iteracion-007_2026-08-23.zip.txt

- **Tamaño del paquete**: 357465 bytes
- **SHA-256 del paquete**: 563cab6a8350d29ae268f3c90519d6bc3518b45551f68669973a84f28bc69979

- **Nombre del paquete**: autonomous-business-lab_iteracion-007_2026-08-23.zip.txt
