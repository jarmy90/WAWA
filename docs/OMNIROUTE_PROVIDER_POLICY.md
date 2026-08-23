# Política de proveedores con OmniRoute (iteración 008)

## No usar un único proveedor para todo

`app/core/routing_policies.py` define políticas **por tarea**:

- classification
- clustering
- discovery
- evidence_extraction
- solution_generation
- skeptic_review
- external_committee
- summarization

Cada tarea define:

- proveedor principal y modelo principal
- proveedores fallback y modelos fallback
- coste máximo y latencia máxima
- requisitos de JSON / contexto
- si se permiten modelos gratuitos aleatorios
- si se exige un modelo fijo
- si está permitido continuar sin respuesta

## Política inicial (implementada)

| Tarea | Proveedor | Modelo | Notas |
|-------|-----------|--------|-------|
| Comité externo | OpenRouter | fijo (`OPENROUTER_REVIEW_MODEL`) | comparabilidad; fallback `openrouter/free` solo si se configura |
| Comité externo (2º revisor) | OmniRoute | `auto` (opcional) | solo si `OMNIROUTE_ENABLED`; mismo guarda que OpenRouter |
| Discovery general | Offline/mock | — | **OmniRoute desactivado para Discovery hasta A/B** |
| Mock | — | — | solo tests y desarrollo |
| Gemini | opcional | — | nunca evidencia por sí mismo |
| ManualImport | — | — | disponible siempre |

## Reglas

1. OmniRoute **no** sustituye silenciosamente el modelo fijo del comité:
   la revisión OpenRouter y la revisión OmniRoute son **revisiones
   independientes y etiquetadas**; el modelo fijo del comité nunca cambia
   sin decisión explícita.
2. `OMNIROUTE_ALLOW_FREE_ONLY=true` por defecto: sin esto no se permiten
   modelos de pago.
3. `OMNIROUTE_REQUIRE_MODEL_ID=true` por defecto: si el gateway no devuelve
   el modelo realmente usado, la llamada se registra como sospechosa y no se
   considera válida para el comité.
4. Coste honesto: `reported_cost` solo si el proveedor lo devuelve;
   `billing_verified=false` sin reconciliación real; un coste desconocido
   **nunca** se convierte en cero.
5. Ausencia = neutral: si OmniRoute falla, no hay revisión, no hay evidencia,
   no hay cambio de decisión.

## Estados de conexión (allowlist)

Ver `docs/OMNIROUTE_SECURITY.md`. Por defecto `UNKNOWN` = bloqueado para
producción. Solo `omniroute-gateway` local está en `TEST_ONLY`.
