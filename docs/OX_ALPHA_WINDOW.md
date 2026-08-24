# Ventana prioritaria "OX Alpha" (iteración 015)

El propietario dispone de acceso gratuito **TEMPORAL** (hasta el
**2026-08-27 inclusive**) a un modelo que denomina **"OX Alpha"**, accesible a
través del gateway local OmniRoute. Este documento define cómo WAWA lo usa sin
violar ninguna regla inmutable de `AGENTS.md`.

## 1. Reglas inmutables

1. **No se inventa el slug.** El slug exacto SOLO se acepta si el propietario
   lo fija en `OX_ALPHA_SLUG` tras verificarlo contra el catálogo real del
   gateway (`GET /v1/models`). Mientras esté vacío, la identidad es
   `OX_ALPHA_UNVERIFIED` y **nunca** se declara que se ha usado OX Alpha.
   `auto` NO corresponde por defecto a OX Alpha.
2. **La ventana expira sola.** Tras `OX_ALPHA_EXPIRES_AT` (2026-08-27) la
   puerta determinista se cierra: ningún flujo depende obligatoriamente de OX
   Alpha y OmniRoute vuelve a su routing coordinado habitual.
3. **La salida del modelo NUNCA es evidencia.** Toda respuesta se etiqueta
   `MODEL_REASONING` / `MODEL_HYPOTHESIS` / `MODEL_CRITIQUE` /
   `MODEL_REFORMULATION`. Jamás sube `proven_demand`, no crea grupos de
   evidencia independientes, no aprueba finalistas, no inicia PRE_CYCLE ni
   autoriza gasto o producción.
4. **Fallo ⇒ ausencia NEUTRAL.** Si OX Alpha falla, no hay clave o el gateway
   está caído: se registra el fallo en `decision_log` + `llm_call_log`, NO se
   sustituye silenciosamente por mock y NO se presenta salida sintética como
   salida de OX Alpha.
5. **Costes honestos.** Cada llamada registra `requested_model`,
   `actual_model`, `actual_provider`, `routing_strategy`, `fallback_used`,
   `fallback_reason`, latencia, tokens, `reported_cost` / `estimated_cost`,
   `cost_source`, `billing_verified=false`, `response_is_external`,
   `response_is_synthetic`.
6. **OmniRoute sigue aislado** (`OMNIROUTE_ENABLED=false` por defecto,
   allowlist upstream, solo 127.0.0.1) según `docs/RUNTIME_STRATEGY.md`.

## 2. Puerta determinista (`app/core/ox_alpha.py`)

`ox_alpha_status(settings)` devuelve identidad, ventana, límites y si puede
usarse hoy. `deep_task_gate(settings, task)` comprueba, en orden:

1. tarea admitida (`reformulation`, `coherence`, `red_team`, `variation_comparison`);
2. slug verificado (si no: `SLUG_UNVERIFIED`);
3. ventana vigente (si no: `WINDOW_EXPIRED`);
4. límite diario de tareas (`DAILY_LIMIT_REACHED`);
5. tamaño máximo del expediente (`ox_alpha_max_input_chars`).

## 3. Tareas reservadas (`app/services/deep_reasoning.py`)

| Tarea | Objetivo |
|---|---|
| `reformulation` | Convertir territorio+lente+arquetipo en Opportunity Briefs concretos (comprador, problema observable, alternativa actual, entregable, precio hipotético, canal, prueba 48 h, limitación IA generalista, activo acumulativo, riesgos, supuestos). 3–5 variantes REALMENTE diferentes. |
| `coherence` | Detectar combinaciones artificiales sin relación causal/comercial ("Capa de confianza para soledad… adaptado a Logística local"). |
| `red_team` | Intentar destruir cada propuesta (¿solo una frase?, ¿una función?, ¿la resuelve una IA generalista?, ¿hay comprador urgente?, ¿prueba <10 USD?, ¿qué dato la descartaría?). |
| `variation_comparison` | Comparar reformulaciones por pares; puede recomendar **0** candidatas. |

Pipeline recomendado: filtros deterministas baratos primero → OX Alpha solo
para las mejores 10–15 direcciones estructurales → validación determinista del
brief → torneo → máx. 3 `RESEARCH_CANDIDATE` → investigación web real.

## 4. API

- `GET /api/oxalpha/status` — estado honesto de la puerta.
- `POST /api/oxalpha/catalog-check` — consulta el catálogo real del gateway;
  si no puede verificar el slug, responde `verified=false` y NO fija nada.
- `POST /api/oxalpha/task` — ejecuta una tarea profunda; ante puerta cerrada
  devuelve `status` ∈ {GATEWAY_DISABLED, SLUG_UNVERIFIED, WINDOW_EXPIRED,
  DAILY_LIMIT_REACHED} con `result: null`.

## 5. Variables de entorno

Ver `env.example`: `OX_ALPHA_SLUG` (vacío hasta verificación),
`OX_ALPHA_EXPIRES_AT=2026-08-27`, `OX_ALPHA_DAILY_TASK_LIMIT=40`,
`OX_ALPHA_MAX_INPUT_CHARS=24000`.

## 6. Benchmark obligatorio antes de preferir OX Alpha

Brazo A (determinista+mock) vs B (OmniRoute auto) vs C (OX Alpha slug fijo)
vs D (otro modelo fuerte), mismos conceptos y expediente. Criterios:
especificidad del comprador, concreción, coherencia causal, calidad del
entregable, prueba 48 h, resistencia a IA generalista, detección de
incoherencias, diversidad real, ausencia de invenciones, formato, latencia,
coste y estabilidad. Se selecciona por resultados, no por brillantez textual.

## 7. Interfaz

Toda salida mostrada lleva: Generada por / Modelo solicitado / Modelo real /
Proveedor real / Estrategia de routing / Coste / Coste verificado /
**Es evidencia: NO** / Revisión determinista / Estado. Etiquetas permitidas:
REFORMULACIÓN DE MODELO · CRÍTICA DE MODELO · HIPÓTESIS SIN VERIFICAR.
Prohibido mostrar: VALIDADA POR OX ALPHA · DEMANDA CONFIRMADA POR OX ALPHA ·
APROBADA POR OMNIROUTE.
