# CAMPAIGN RUNNER

> **Estado: IMPLEMENTADO** (iteración 006). Máquina de estados persistente,
> sin LLM para validar transiciones; embudo con límites configurables e
> inmutables durante la campaña.

## Estados de campaña

```
CREATED → TERRITORY_SELECTION → SIGNAL_COLLECTION → WIDE_IDEATION →
COMMODITY_FILTER → RECOMBINATION → STRUCTURAL_ANALYSIS → SHORTLIST →
INTERNAL_TOURNAMENT → FINALISTS → RESEARCH_MISSIONS → EXTERNAL_REVIEW_READY →
EXTERNAL_REVIEW_PENDING → SYNTHESIS → EXPERIMENT_DESIGN → OWNER_REVIEW → COMPLETED
```

Estados adicionales: `PAUSED`, `BLOCKED`, `FAILED`, `CANCELLED`.

Cada transición registra: campaign_id, from_stage, to_stage, timestamp, actor,
reason, inputs/outputs, conceptos considerados/rechazados, costes, unknowns,
errores y siguiente acción recomendada (tabla `ff_transitions`).

## Embudo estándar (configurable, nunca aumenta en silencio)

```
100 conceptos → ≤40 (dedup) → ≤20 (Commodity Detector) → ≤10 (análisis
estructural) → ≤5 (torneo) → ≤3 finalistas → comité → síntesis → ≤1 experimento
```

Límites por defecto (`DEFAULT_FUNNEL_LIMITS`, guardados en `funnel_limits`):

| Límite | Valor |
|---|---|
| `max_concepts` | 100 |
| `max_after_dedup` | 40 |
| `max_after_commodity` | 20 |
| `max_structural` | 10 |
| `max_tournament` | 5 |
| `maximum_finalists` | 3 (0-5, configurable por campaña) |

## Work Budget

- `time_budget_hours`: 2-6 por sesión (alcance, no garantía).
- `api_budget_usd`: **0** por defecto y durante todo el descubrimiento.
- `experiment_budget_usd`: 0 en campañas de descubrimiento.
- `external_review_slots`: 3.
- `maximum_deep_research_candidates`: 10.

## Si ninguna idea alcanza la calidad mínima

- No se fuerzan finalistas (`maximum_finalists` puede ser 0).
- Se guarda el motivo del fracaso como patrón de aprendizaje
  (`learning_records`, `kind=campaign_outcome`).
- Se puede iniciar una nueva campaña con territorios/lentes distintos.
- Las ideas mediocres **no** se envían al comité externo.

## Entregables obligatorios por etapa

`finalize_session` y las transiciones validan entregables antes de avanzar:
por ejemplo, no se pasa a `FINALISTS` sin shortlist, ni a `SYNTHESIS` sin
expedientes del comité. Si faltan entregables, la transición se bloquea con
una lista explícita de lo pendiente (`_missing_deliverables`).
