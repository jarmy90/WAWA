# REASONING BUDGET

> **Estado: IMPLEMENTADO** (iteración 006). Niveles de profundidad con
> registro auditable de qué nivel se usó y por qué.

## Niveles

| Nivel | Uso | Ejemplos |
|---|---|---|
| `LEVEL_0_DETERMINISTIC` | Reglas puras, sin razonamiento | dedup, fingerprints, filtros, ordenación, validación, métricas, persistencia |
| `LEVEL_1_FAST_REVIEW` | Clasificación inicial barata | títulos, resúmenes, etiquetado, eliminación obvia |
| `LEVEL_2_DEEP_REASONING` | Solo candidatas de la shortlist | recombinación, moat, distribución, comprador, red-team |
| `LEVEL_3_COMMITTEE_READY` | Máximo 10 candidatas | expedientes completos, comparación por pares, preparación del comité |
| `LEVEL_4_EXPERIMENT_READY` | Máximo 3 finalistas | tesis completa, experimento específico, investigación profunda |

## Reglas

- No usar razonamiento profundo para 100 conceptos: la fase 1 es brevisima
  (2-3 frases por concepto) y barata.
- El paso a niveles superiores está acotado por el embudo
  (`maximum_deep_research_candidates=10`, `maximum_finalists=3`).
- Cada uso de nivel se registra en `ff_reasoning_log` (campaña, nivel, acción,
  motivo, sesión) vía `POST /api/campaigns/{id}/reasoning` o el servicio.
- La aplicación registra el nivel y el motivo; no se delega en un LLM la
  decisión de profundidad.

## API budget

`api_budget_usd=0` durante el descubrimiento: las APIs de producción se
reservan para fases posteriores (ver `docs/API_READINESS_GATE.md`). Cualquier
`SESSION_OUTPUT` que declare llamadas o coste > 0 es rechazado por la política
permanente.
