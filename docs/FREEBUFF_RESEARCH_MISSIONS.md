# FREEBUFF RESEARCH MISSIONS

> **Estado: IMPLEMENTADO** (iteración 006). Misiones de investigación
> exportables/importables para que Freebuff investigue durante la sesión.

## Tipos de misión (10)

| Tipo | Pregunta central |
|---|---|
| `DEMAND_REALITY_CHECK` | ¿Existe demanda real y verificable, o solo hipótesis? |
| `BUYER_BUDGET_CHECK` | ¿Quién paga y de qué presupuesto sale el dinero? |
| `CURRENT_ALTERNATIVE_CHECK` | ¿Qué usa hoy el cliente para resolver el problema? |
| `GENERAL_AI_SUBSTITUTION_CHECK` | ¿Una IA generalista lo resuelve sin workflow ni integración? |
| `COMPETITOR_EQUIVALENT_SEARCH` | ¿Existen equivalentes cercanos? |
| `DISTRIBUTION_ACCESS_CHECK` | ¿Cómo se llega a los primeros 20 usuarios? |
| `MOAT_REALITY_CHECK` | ¿Existe un activo acumulativo real o solo deseado? |
| `DATA_AVAILABILITY_CHECK` | ¿Están disponibles los datos necesarios? |
| `TOS_AND_LEGAL_CHECK` | ¿La actividad es legal y compatible con el canal? |
| `EXPERIMENT_FEASIBILITY_CHECK` | ¿Puede probarse barato, ético y medible? |

## Contenido de cada misión

- Preguntas exactas.
- Consultas sugeridas.
- Fuentes prioritarias y fuentes débiles/prohibidas.
- Criterio de evidencia.
- Formato JSON de respuesta.
- Unknowns obligatorios.
- Fecha de consulta.
- Distinción fuente primaria/secundaria.
- Fragmentos breves y URLs concretas.
- Nivel de confianza y contradicciones.

## Reglas de verificación (no invención)

- Una conclusión de Freebuff **no** se convierte en demanda verificada sin
  referencias concretas: URL + fecha + fragmento (regla aplicada en
  `app/services/campaign.py::_build_evidence`).
- `verified=true` exige URL + fecha + fragmento; si falta alguno, la evidencia
  queda `verified=false` con nota explicativa.
- Fuentes primarias > secundarias; se registra la distinción.
- El consenso de modelos no es evidencia de mercado (ver
  `docs/MODEL_CONSENSUS_LIMITATIONS.md`).

## Flujo

1. `POST /api/discovery/missions` con `kind` y `concept_id`/`campaign_id`.
2. Exportar la misión (Markdown/JSON) para que Freebuff la investigue.
3. Importar resultados con `POST /api/discovery/missions/{id}/import` o desde
   `SESSION_OUTPUT.json` (`mission_results`).
