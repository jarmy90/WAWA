# Business Discovery Engine (iteración 004)

El motor de ideas: descubre, diseña, compara y selecciona conceptos de negocio
**sin depender de que el usuario le entregue un problema**. Prioridad central
del proyecto: encontrar oportunidades extraordinarias, originales, rentables,
baratas de validar y **difíciles de sustituir por una IA generalista**.

> **Estado**: implementado (offline determinista) · las bibliotecas son
> configurables · la demanda nunca se inventa.

## Dos rutas de descubrimiento

- **Ruta A — Problem-led**: el usuario aporta un problema y el Scout propone
  oportunidades (flujo de las iteraciones 001-003, intacto).
- **Ruta B — Open opportunity discovery** (nueva): campañas que generan
  espacios de búsqueda y candidatos sin propuesta previa.

## Ruta B: campañas en fases

Una campaña (`POST /api/discovery/campaigns`) recorre 7 fases. Cada fase es un
endpoint explícito y barato (coste registrado, fallback a mock):

1. **Fase 1 — Exploración amplia** (`POST .../phase1`): genera 20-200 conceptos
   breves combinando **territorio × lente × arquetipo**. Los conceptos son
   HIPÓTESIS, no ideas finales.
2. **Fase 2 — Filtro de comoditización** (`POST .../filter`): ejecuta el
   **General AI Substitution Test** y elimina prompt-wrappers, productos sin
   comprador, sin resultado medible y regulados sin camino viable. Cada
   rechazo crea un *learning record* con el patrón detectado.
3. **Fase 3 — Recombinación** (`POST .../recombine`): cruza los mecanismos de
   los conceptos que pasaron el filtro para crear conceptos superiores.
4. **Fase 4 — Shortlist** (`POST .../shortlist`): evalúa cada concepto con el
   **Venture Quality Score** y conserva 6-16 candidatos **con diversidad**
   (descarta clones conceptuales por fingerprint).
5. **Fase 5 — Torneo** (`POST .../tournament`): comparaciones por pares con 8
   criterios (dolor económico, resistencia a IA, velocidad de validación,
   distribución, activo acumulativo, explicabilidad, margen, merecimiento del
   siguiente euro/hora). Guarda cada enfrentamiento.
6. **Fase 6 — Finalistas**: máximo 3.
7. **Fase 7 — Tesis y experimento**: los finalistas se promueven a
   `Opportunity` (`POST /api/discovery/concepts/{id}/promote`) y entran en el
   pipeline de investigación normal.

## Bibliotecas configurables (`app/core/libraries.py`)

- **31 territorios** de búsqueda (nuevos comportamientos, trabajo invisible,
  descoordinación entre apps, información difícil de verificar, mercados
  fragmentados, economía de máquinas, problemas creados por la IA…). Son
  **espacios para explorar, no afirmaciones de demanda**.
- **30 lentes** de innovación (quitar intermediario, pagar por resultado,
  trust layer, proof-before-payment, agrupar demanda fragmentada…).
- **27 arquetipos** de negocio (SaaS vertical, marketplace, producto de datos,
  verificación, infraestructura para agentes, concierge validable…). El
  generador evita sesgos tipo "siempre SaaS/informes/dashboards".

Cada concepto registra: territorio, lentes, arquetipo, por qué la combinación
podría ser novedosa, problema concreto, quién pagaría, qué resultado compraría,
por qué ahora, por qué no bastaría una IA generalista y qué activo acumulativo
podría crear.

## General AI Substitution Test

Una idea **no es buena solo porque pueda construirse con IA**. El test
(`app/scoring/venture.py`) puntúa 13 respuestas estructuradas (0-100) y
clasifica:

| Clasificación | Significado |
|---|---|
| `COMMODITY_WRAPPER` | Una IA generalista resuelve el 70%+ con salida genérica y sin workflow/integración/memoria. **BLOQUEADA** (verdict=blocked). |
| `WEAK_DIFFERENTIATION` | Algo de defensa, insuficiente. |
| `DEFENSIBLE_WORKFLOW` | Workflow operativo + resultado verificable. |
| `DATA_ADVANTAGE` | Datos propios que mejoran el servicio. |
| `DISTRIBUTION_ADVANTAGE` | Canal/bucle de distribución propio. |
| `NETWORK_ADVANTAGE` | Efecto red. |
| `COMPOUNDING_SYSTEM` | Mejora con cada uso y sobrevive a la mejora de los modelos base. |

En modo offline las respuestas se derivan de perfiles estructurales por
arquetipo (etiquetados como estimaciones); las misiones de investigación
pueden sustituirlas por respuestas fundamentadas. La regla es dura: **una
COMMODITY_WRAPPER no puede aprobarse aunque tenga demanda aparente**.

## Venture Quality Score

Segunda capa de puntuación (no sustituye al Opportunity Validation Score):

| Criterio | Peso |
|---|---|
| Economic Pain | 12% |
| Proven Demand | 10% |
| General AI Resistance | 15% |
| Defensibility / Compounding Advantage | 15% |
| Distribution Advantage | 12% |
| Originality with Utility | 10% |
| Validation Speed | 8% |
| Gross Margin Potential | 6% |
| Recurrence / Expansion | 5% |
| Demonstrability / Story | 4% |
| Operational Simplicity | 3% |

Bloqueadores duros (score tope 39 aunque todo lo demás puntúe alto):
COMMODITY_WRAPPER, sin comprador identificable, sin camino a los primeros 20
usuarios, sin resultado medible, sin validación barata, riesgo legal grave,
capital elevado antes de aprender, marketplace sin cuña de liquidez, spam,
sin ventaja defendible, mera feature de una plataforma general, o evidencia
inventada. Etiquetas: `NOVEL_BUT_WEAK`, `BORING_BUT_STRONG`,
`VIRAL_BUT_FRAGILE`, `COMMODITY`, `EXPERIMENT_READY`, `CAPITAL_INTENSIVE`,
`DISTRIBUTION_FIRST`, `DATA_COMPOUNDING`, `NETWORK_POTENTIAL`,
`HIGH_TRUST_REQUIRED`, `SERVICE_FIRST`, `PRODUCT_POTENTIAL`,
`CATEGORY_CREATION_CANDIDATE`.

### Originalidad medible

Nadie se autopuntúa "muy original". Se separan `novelty_score` (distancia de
fingerprint al resto de la campaña) y `utility_score` (dolor económico +
claridad de resultado + comprador definido). La originalidad final se calcula
con **tope de utilidad**: una idea novedosa pero inútil puntúa bajo.

## Diversidad y clones

Fingerprint estructural (arquetipo, territorio, lentes, mecanismo, problema,
comprador, resultado). Un clon conceptual = mismo arquetipo + mecanismo casi
idéntico, o distancia estructural ≤ 0.22. "Cambiar de sector manteniendo el
mismo producto" NO es diversidad. La campaña expone `diversity` (distancia
media 0-1).

## Misiones de investigación Freebuff-first

`POST /api/discovery/missions` genera una misión exportable (Markdown + JSON)
con objetivo, preguntas, consultas sugeridas, formato de salida, **regla de no
invención**, criterios de fiabilidad y el esquema JSON exacto para reimportar
(`POST /api/discovery/missions/{id}/import`).

La verificación NO es automática: una evidencia solo se marca `verified=true`
si incluye URL concreta, fecha de consulta y fragmento/resumen. Freebuff (o
cualquier fuente) sin esos campos queda `verified=false`. Las evidencias
verificadas pueden adjuntarse a una Opportunity promovida
(`POST /api/discovery/opportunities/{id}/missions/{mission_id}/attach`).

## Memoria empresarial

Cada rechazo guarda motivo principal, patrón y si debe evitarse en campañas
posteriores (`GET /api/discovery/learning`). Cada éxito futuro podrá guardar
señal, lente, canal, comprador, propuesta y ventaja confirmada.

## Honestidad

- En offline, `proven_demand = 0` siempre: la demanda no se inventa.
- Los conceptos son hipótesis; el Buyer Oracle se concreta con misiones.
- El MockProvider genera controles de comoditización a propósito: el filtro
  demuestra que bloquea prompt-wrappers.
- El Judge de oportunidades (iteración 001) sigue siendo el único que decide
  aprobar/rechazar con evidencias reales.
