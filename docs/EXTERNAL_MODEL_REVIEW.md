# Comité de Contraste (revisiones externas de finalistas)

> Estado: **implementado** (iteración 005) · Simulado: los proveedores automáticos
> son interfaces opcionales; el modo probado es `MANUAL_IMPORT` + `MOCK`.

## Propósito

Antes de que una oportunidad finalista pase a investigación profunda o
experimento, el sistema puede someterla a **revisión de contraste por varios
modelos independientes** (GPT, Grok, Gemini, el modelo operativo, un
supervisor humano...).

El objetivo NO es sustituir la evidencia de mercado por opiniones de modelos.
Es:

- Detectar puntos ciegos y riesgos.
- Contrastar supuestos.
- Proponer experimentos mejores y más baratos.
- Reducir el sesgo del modelo principal.

**Principio fundamental**: las opiniones de modelos no son evidencia de
demanda. Nunca se registran como hechos una estimación de un modelo, una
predicción de ventas, una valoración de mercado sin fuente, un precio sugerido
o una puntuación subjetiva.

## Flujo

1. El Judge aprueba una oportunidad (puntuación ≥ umbral, sin blockers).
2. `PipelineService` llama a `reviews.auto_queue()`: la finalista entra en la
   cola (silenciosamente; si supera el máximo semanal, solo se registra).
3. El panel muestra la cola; se puede generar el expediente:
   `data/external_reviews/opportunity_{id}/review_packet.md`.
4. El expediente se descarga y se consulta manualmente en cada modelo
   (`MANUAL_IMPORT`), o un proveedor automático lo procesa (`API_AUTOMATIC`,
   futuro, cuando exista API estable + credencial + presupuesto).
5. Las respuestas (TXT/Markdown) se importan al panel. El texto original se
   conserva; el parser extrae campos estructurados con una allowlist.
6. `synthesize()` agrega las revisiones válidas: distribución de
   recomendaciones, consenso (con etiqueta de opinión vs evidencia), riesgos
   repetidos/únicos, evidencia ausente y acción recomendada.
7. Si la ventana (48 h por defecto) caduca sin revisiones, el sistema
   **continúa automáticamente** con su evaluación interna. La ausencia de
   revisión es NEUTRAL, no negativa.

## Configuración (Settings)

| Variable | Defecto | Significado |
|---|---|---|
| `review_min_internal_score` | 72 | Umbral interno para entrar en la cola |
| `review_max_finalists_per_week` | 3 | Máximo de finalistas por semana (ventana deslizante de 7 días) |
| `review_window_hours` | 48 | Ventana de espera antes de continuar sin revisión |
| `review_continue_without_review` | true | Si `false`, la cola espera (nunca bloquea indefinidamente: el propietario decide) |
| `review_required_for_sensitive_activities` | true | Finalistas con riesgo legal/ToS/plataforma marcan `review_required=1` |
| `review_max_file_bytes` | 200 000 | Límite de tamaño de una respuesta importada |
| `review_allowed_extensions` | `.txt, .md, .markdown` | Lista blanca de extensiones |

## Modos de ejecución

- `API_AUTOMATIC` (**implementado desde la iteración 007 para OpenRouter**):
  una revisión automática por finalista vía el proveedor OpenRouter, con
  guardas deterministas. Se activa solo con credencial y presupuesto
  (límites diarios/mensuales de peticiones y coste, circuit breaker). Si
  falla o no hay clave, **no se fabrica ninguna revisión**: la ausencia es
  neutral y se registra en `llm_call_log`. No se asume acceso programático de
  ninguna otra cuenta web.
- `MANUAL_IMPORT`: expediente → consulta manual → importación TXT/MD. Vía
  funcional principal para GPT/Grok/Gemini/Claude/humano.
- `INTERNAL` / `HUMAN`: revisión del modelo operativo o del supervisor humano.
- `MOCK`: revisiones de demostración claramente etiquetadas.

### Opción A — OpenRouter solo para el comité (iteración 007)

- Modelo fijo (`OPENROUTER_REVIEW_MODEL`) para comparabilidad; router gratuito
  (`OPENROUTER_FALLBACK_MODEL=openrouter/free`) como fallback. Se registra
  siempre `requested_model` y `actual_model` (el router gratuito puede
  devolver modelos distintos en cada llamada).
- Costes honestos por llamada en `llm_call_log`: `reported_cost` (solo si el
  proveedor lo devuelve), `estimated_cost` etiquetado, `cost_source`
  (`PROVIDER_RESPONSE | LOCAL_ESTIMATE | FREE_TIER | UNKNOWN |
  BILLING_RECONCILIATION`) y `billing_verified=false` (no hay reconciliación
  con facturación en esta fase). Un coste desconocido nunca se convierte en
  cero.
- Presupuesto de inferencia separado: máx. 3 finalistas/semana (regla
  existente), 1 revisión automática por oportunidad, límites diario/mensual
  de peticiones y coste, circuit breaker ante errores repetidos y bloqueo por
  cuota. Reintentos acotados (`OPENROUTER_MAX_RETRIES`), nunca infinitos.
- Fallback sin coste permitido = **no generar revisión** (el mock nunca se
  hace pasar por revisión real).

## Reglas de decisión

Las revisiones **pueden**: aumentar/reducir confianza, recomendar más
investigación, detectar riesgos, proponer un experimento más barato, cambiar
prioridad, recomendar rechazo, identificar contradicciones.

Las revisiones **no pueden**: activar `AUTONOMOUS_PRODUCTION`, autorizar dinero
real, cambiar límites económicos, saltarse riesgos críticos, convertir una
estimación en ingreso, aprobar una actividad bloqueada ni eliminar evidencias
contrarias. El Judge final sigue aplicando reglas deterministas.

## No molestar al propietario

- No hay notificación por cada idea; las finalistas aparecen en el panel.
- Se incluyen en el resumen semanal (nuevas finalistas, revisiones pendientes,
  decisiones, experimentos recomendados, ideas rechazadas).
- Si el propietario no interviene en la ventana: el sistema continúa, usa su
  evaluación interna, registra que no hubo revisión externa y mantiene los
  límites presupuestarios. La ausencia **no** se interpreta como aprobación.

## Endpoints

```
GET  /api/reviews/queue                       Cola con síntesis por finalista
POST /api/reviews/opportunities/{id}/queue    Colocar una finalista (umbral)
POST /api/reviews/opportunities/{id}/packet   Generar expediente (idempotente)
GET  /api/reviews/opportunities/{id}/packet   Descargar expediente (Markdown)
POST /api/reviews/opportunities/{id}/import   Importar revisión (TXT/MD/JSON)
GET  /api/reviews/opportunities/{id}          Revisiones + síntesis
GET  /api/reviews/{review_id}                 Revisión con raw original
POST /api/reviews/{review_id}/invalidate      Marcar inválida
POST /api/reviews/opportunities/{id}/synthesize  (Re)generar síntesis
POST /api/reviews/opportunities/{id}/continue Continuar sin revisión (neutral)
POST /api/reviews/opportunities/{id}/auto-review  Revisión automática OpenRouter (Opción A)
GET  /api/reviews/auto-status               Presupuesto de inferencia + circuit breaker
GET  /api/llm-calls                         Log append-only de llamadas LLM (coste honesto)
POST /api/reviews/opportunities/{id}/note     Nota humana en la cola
POST /api/reviews/demo                        Demostración SINTÉTICA del flujo
```

Toda respuesta incluye `model_opinion_not_evidence: true` y
`real_money_moved: false`.
