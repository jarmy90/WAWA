# Síntesis de revisiones externas

> Estado: **implementado** (iteración 005) · Determinista, sin LLM.

## Parsing de una respuesta importada

`ReviewService.parse_review_response(text)` es tolerante y usa una
**allowlist** de claves (`PARSED_FIELDS`):

| Clave | Validación |
|---|---|
| `recommendation` | Obligatoria; normalizada a `REJECT | MORE_RESEARCH | SMALL_EXPERIMENT | PRIORITY_EXPERIMENT` |
| `confidence` | Numérico 0-100 (redondeado a 1 decimal) |
| `strongest_evidence`, `weakest_assumption`, `missing_evidence`, `primary_risk`, `suggested_improvement`, `cheaper_experiment`, `kill_condition`, `final_reasoning_summary` | Texto sanitizado (sin caracteres de control) y acotado |

Formatos aceptados (por orden):

1. Bloque JSON (```json ... ```) u objeto JSON con `recommendation`.
2. Líneas `clave: valor`, `**clave**: valor` o `- clave: valor`.

El JSON gana; las líneas rellenan huecos sin sobrescribir.

**Estados** de una revisión:

- `valid`: recomendación + confianza parseadas.
- `partial`: recomendación presente, confianza ausente o inválida.
- `needs_validation`: sin recomendación (requiere validación humana).
- `invalid`: marcada manualmente como inválida.
- `rejected`: (reservado) rechazada por el sistema.

Los `parse_errors` se conservan y se muestran al importar. El **texto
original (`raw_response`) se conserva siempre**, junto con su SHA-256.

## Síntesis (`synthesize(opportunity_id)`)

Agrega solo revisiones `valid` o `partial`:

- `recommendation_distribution`: conteo por recomendación (siempre incluye las
  cuatro con ceros).
- `average_confidence`: media de confianzas (null si no hay).
- `repeated_risks` / `unique_risks`: riesgos primarios que aparecen en ≥2
  revisiones o en una sola.
- `missing_evidence`: evidencias ausentes señaladas (deduplicadas).
- `consensus_level`:
  - `NONE` — sin revisiones válidas.
  - `LOW` — sin mayoría (ratio < 0.4).
  - `MEDIUM` — mayoría parcial (0.4 ≤ ratio < 0.6).
  - `HIGH` — mayoría ≥ 0.6 **y** ≥60% de las revisiones citan URL/evidencia.
  - `OPINION_CONSENSUS` — mayoría ≥ 0.6 pero sin referencias a evidencia:
    **falso consenso**. Varios modelos que coinciden en opinión no crean
    evidencia.
- `recommended_next_action` (determinista):
  `REJECT` (≥50% rechazo) → `MORE_RESEARCH` (≥50%) →
  `PRIORITY_EXPERIMENT` (≥50%) → `SMALL_EXPERIMENT` (prioritario+pequeño ≥60%)
  → `MORE_REVIEW` (sin consenso).

## Reglas de honestidad

- La puntuación interna **no cambia** por opiniones de modelos
  (`internal_score_after = internal_score_before`), y `score_change_reason` lo
  explica: la evidencia de demanda solo puede venir de fuentes verificadas
  (URL + fecha + fragmento).
- Repetir una afirmación en 4 revisiones **no** añade evidencias a la
  oportunidad ni sube el Opportunity Score.
- Los datos desconocidos siguen siendo desconocidos; la síntesis puede
  *señalar* la evidencia ausente, no inventarla.
