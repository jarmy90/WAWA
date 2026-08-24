# MANIFIESTO ITERACIÓN 015 — VENTANA PRIORITARIA OX ALPHA (v0.14.0)

- **Iteración**: 015 (detectada automáticamente: max(manifiestos)=014 → siguiente=015)
- **Versión**: 0.14.0
- **Fecha**: 2026-08-23
- **Estado**: COMPLETADA — **314 tests pasan** (300 previos + 14 nuevos), 100% offline
- **Objetivo**: aprovechar la ventana gratuita TEMPORAL (hasta 2026-08-27) del modelo que el propietario denomina "OX Alpha" a través de OmniRoute, para tareas de razonamiento profundo, SIN inventar el slug, SIN convertir salidas de modelo en evidencia y CON ausencia neutral ante cualquier fallo.

## Identificación real del modelo

- Se intentó la consulta REAL del catálogo contra `http://127.0.0.1:20128/v1/models`:
  **conexión rechazada** (gateway no arrancado en este entorno; mismo estado documentado en la iteración 008).
- Por tanto, según regla inmutable: identidad = **OX_ALPHA_UNVERIFIED**, `ox_alpha_slug=""` por defecto.
- NO se inventa ningún slug; NO se declara haber usado OX Alpha hasta que el propietario verifique el slug real (`POST /api/oxalpha/catalog-check` con el gateway en marcha) y fije `OX_ALPHA_SLUG`.

## Cambios implementados

### 1. Puerta determinista — `app/core/ox_alpha.py` (NUEVO)
- `ox_alpha_status()`: identidad, ventana (expira sola tras 2026-08-27), límites.
- `deep_task_gate(task)`: tareas admitidas (`reformulation`, `coherence`, `red_team`, `variation_comparison`) → slug verificado → ventana vigente → límite diario → tamaño máx. de entrada.
- Prompts deterministas: `build_reformulation_prompt` (exige comprador, problema observable, alternativa actual, entregable, precio hipotético, canal, prueba 48 h, limitación IA generalista, activo acumulativo, riesgos, supuestos; entre 3 y 5 variantes realmente diferentes), `build_coherence_prompt`, `build_red_team_prompt`, `build_variation_comparison_prompt` (puede recomendar 0 candidatas).

### 2. Servicio de razonamiento profundo — `app/services/deep_reasoning.py` (NUEVO)
- Ejecuta tareas vía `OmniRouteProvider.generate(model=slug)` (parámetro `model` explícito añadido al proveedor; nunca sustituye al modelo fijo del comité OpenRouter).
- Registro honesto por llamada en `llm_call_log`: requested/actual model+provider, routing_strategy, fallback_used/reason, latencia, tokens, reported/estimated cost, cost_source, billing_verified=false, response_is_external/synthetic.
- **Ausencia neutral**: fallo ⇒ status registrado (GATEWAY_DISABLED / SLUG_UNVERIFIED / WINDOW_EXPIRED / DAILY_LIMIT_REACHED), decisión en `decision_log`, NUNCA mock silencioso ni salida sintética presentada como OX Alpha.
- **La salida del modelo jamás toca evidencia ni puntuaciones**: no crea grupos de evidencia, no sube proven_demand, no aprueba finalistas ni inicia PRE_CYCLE.

### 3. Configuración — `app/core/config.py`
- `ox_alpha_slug=""`, `ox_alpha_expires_at="2026-08-27"`, `ox_alpha_daily_task_limit=40`, `ox_alpha_max_input_chars=24000`; version → 0.14.0.

### 4. API — `app/api/routes.py`
- `GET /api/oxalpha/status`
- `POST /api/oxalpha/catalog-check` (verificación contra catálogo real; si no puede verificar ⇒ verified=false, no fija nada)
- `POST /api/oxalpha/task` (puerta cerrada ⇒ resultado null + motivo honesto)

### 5. Documentación
- `docs/OX_ALPHA_WINDOW.md` (NUEVO): reglas inmutables, puerta, tareas reservadas, pipeline recomendado (filtros baratos primero, OX Alpha solo para las mejores 10–15 direcciones), benchmark A/B/C/D obligatorio antes de preferirlo, etiquetas de interfaz permitidas/prohibidas.
- `env.example`: OX_ALPHA_SLUG (vacío hasta verificación), OX_ALPHA_EXPIRES_AT, OX_ALPHA_DAILY_TASK_LIMIT, OX_ALPHA_MAX_INPUT_CHARS.

### 6. Frontend
- Versión sincronizada v0.14.0 · iteración 015 · build `015-ox-alpha-window`.

## Pruebas nuevas (tests/test_ox_alpha_015.py — 14 tests, offline)
1. Estado por defecto = OX_ALPHA_UNVERIFIED, is_evidence=False.
2. Puerta cierra sin slug (SLUG_UNVERIFIED) incluso con gateway activo.
3. Puerta cierra tras la fecha de expiración (WINDOW_EXPIRED) — sin flujos dependientes.
4. Tareas no admitidas rechazadas.
5. Límite diario configurable (0 bloquea inmediatamente).
6. Fallo del proveedor ⇒ ausencia neutral: sin salida sintética, sin mock que suplante, fallo registrado.
7. Registro honesto en llm_call_log (requested vs actual, cost_source, billing_verified=false).
8. La salida del modelo NO añade evidencia, NO sube demanda y NO aprueba finalistas.
9. Prompt de reformulación exige campos concretos del brief (comprador, problema observable, prueba 48 h, canal; 3–5 variantes).
10–14. Endpoints API: status, task (GATEWAY_DISABLED/SLUG_UNVERIFIED/WINDOW_EXPIRED), catalog-check verified=false, tarea inválida can_use=false.

## Resultado de pruebas
- `python3 -m pytest tests/` → **314 passed**, 1 warning. `node --check frontend/app.js` → OK.

## No se hizo (por seguridad, según AGENTS.md)
- NO se activó AUTONOMOUS_PRODUCTION; PRE_CYCLE permanece detenido.
- NO se consumió ninguna API de pago ni se enviaron datos reales (gateway apagado).
- NO se inventó slug, demanda, precio ni evidencia; las opiniones de modelos siguen sin ser evidencia.
- OmniRoute sigue aislado, desactivado por defecto y fuera del comité OpenRouter.

- **Nombre del paquete**: pendiente de generar (`scripts/package_for_review.py`)
