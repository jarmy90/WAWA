# Venture Quality Score y General AI Substitution Test

El **Opportunity Validation Score** (iteración 001, `app/scoring/engine.py`)
sigue intacto y decide aprobar/rechazar con evidencias. Esta capa nueva,
**Venture Quality Score** (`app/scoring/venture.py`), valora la **calidad
empresarial y estratégica** de un concepto ANTES de que haya evidencia de
mercado. Es puro, determinista y sin LLM: los números salen de respuestas
estructuradas y de perfiles estructurales.

## General AI Substitution Test

### Preguntas (0-100)

1. ¿Puede el cliente resolver el 80% pegando su información en una IA generalista? (`generic_ai_can_solve`)
2. ¿La salida principal es solo texto/código/imágenes/recomendaciones genéricas? (`output_is_generic`)
3. ¿Existe workflow operativo adicional? (`has_operational_workflow`)
4. ¿Existe integración con datos o herramientas? (`has_data_integration`)
5. ¿Existe memoria histórica acumulativa? (`has_accumulative_memory`)
6. ¿Existe resultado verificable? (`has_verifiable_outcome`)
7. ¿Existe acción posterior automatizada? (`has_followup_action`)
8. ¿Existe coste de cambio? (`has_switching_cost`)
9. ¿Mejora el producto con cada uso? (`improves_with_use`)
10. ¿Sobrevive a la mejora de los modelos base? (`survives_model_improvement`)
11. ¿Efecto red? (`network_effect`)
12. ¿Bucle de distribución? (`distribution_loop`)
13. ¿Ventaja de datos? (`data_advantage`)

### Fórmulas (deterministas)

```
vulnerability = 0.5·generic_ai_can_solve + 0.5·output_is_generic
defense       = 0.25·has_operational_workflow + 0.2·has_data_integration
              + 0.2·has_accumulative_memory + 0.15·has_verifiable_outcome
              + 0.1·has_followup_action + 0.1·has_switching_cost
compounding   = 0.5·improves_with_use + 0.5·survives_model_improvement
bonus         = max(0.15·network_effect, 0.12·distribution_loop, 0.12·data_advantage)
resistance    = 0.6·(100 − vulnerability) + 0.4·defense + bonus   (0-100)
```

### Clasificación (orden de comprobación)

1. `generic_ai_can_solve ≥ 70` y `output_is_generic ≥ 60` y
   workflow/integración/memoria < 45 → **COMMODITY_WRAPPER** (verdict=blocked)
2. `data_advantage ≥ 70` → DATA_ADVANTAGE
3. `network_effect ≥ 70` → NETWORK_ADVANTAGE
4. `distribution_loop ≥ 70` → DISTRIBUTION_ADVANTAGE
5. `improves_with_use ≥ 60` o `memory ≥ 60`, y `survives ≥ 50` → COMPOUNDING_SYSTEM
6. workflow ≥ 55 y resultado verificable ≥ 50 → DEFENSIBLE_WORKFLOW
7. resistance ≥ 55 → DEFENSIBLE_WORKFLOW
8. resto → WEAK_DIFFERENTIATION

**Regla dura**: `COMMODITY_WRAPPER` no puede aprobarse. Se propaga como
bloqueador duro al Venture Quality Score.

## Venture Quality Score

### Pesos

| Criterio | Peso |
|---|---|
| economic_pain | 12 |
| proven_demand | 10 |
| general_ai_resistance | 15 |
| defensibility | 15 |
| distribution | 12 |
| originality | 10 |
| validation_speed | 8 |
| gross_margin | 6 |
| recurrence | 5 |
| demonstrability | 4 |
| operational_simplicity | 3 |
| **Total** | **100** |

`final_score = Σ(peso·criterio) / 100`, redondeado a 2 decimales.

### Bloqueadores duros

Si hay cualquiera (prefijo), `final_score` se **topea a 39** (nunca parece
aprobable):

- `COMMODITY_WRAPPER`
- Sin comprador identificable
- Sin camino creíble a los primeros 20 usuarios
- Sin resultado medible
- Sin vía de validación barata
- Riesgo legal o de plataforma grave
- Requiere capital elevado antes de aprender
- Marketplace sin cuña de liquidez
- Depende de spam no solicitado
- Sin ventaja defendible y sin camino creíble para construirla
- Es solo una feature de una plataforma general
- Requeriría evidencia inventada para parecer viable

### Originalidad con utilidad

```
novelty  = distancia de fingerprint al concepto más parecido de la campaña (0-100)
utility  = 0.45·economic_pain + 0.30·claridad_de_resultado + 0.25·comprador_definido
originality = utility · (0.4 + 0.6·novelty/100)
```

La utilidad **topea** la originalidad: novedoso pero inútil → baja. Útil pero
copiado → baja en novedad.

### Etiquetas

`NOVEL_BUT_WEAK` (originalidad ≥ 75 y dolor < 50) · `BORING_BUT_STRONG` (dolor
≥ 70 y resistencia a IA < 40) · `VIRAL_BUT_FRAGILE` (demostrabilidad ≥ 75 y
defensa < 45) · `COMMODITY` · `EXPERIMENT_READY` (validación ≥ 70 sin
bloqueadores) · `CAPITAL_INTENSIVE` · `DISTRIBUTION_FIRST` (distribución ≥ 70) ·
`DATA_COMPOUNDING` / `NETWORK_POTENTIAL` (defensa ≥ 70) · `HIGH_TRUST_REQUIRED` ·
`SERVICE_FIRST` · `PRODUCT_POTENTIAL` (margen ≥ 75) ·
`CATEGORY_CREATION_CANDIDATE`.

## Estimación estructural offline

Sin API, las respuestas del test se derivan de:
- **Perfil de sustitución por arquetipo** (`ARCHETYPE_SUBSTITUTION_PROFILES`).
- **Ajustes por texto**: palabras como "chat"/"contenido"/"informe" suben la
  vulnerabilidad y bajan las defensas; "integración"/"api" suben integración;
  "memoria"/"historial" suben memoria; etc.

Los 11 criterios se estiman con:
- Perfil económico por arquetipo (validación, margen, recurrencia,
  distribución, simplicidad).
- Perfil de dolor por territorio.
- Resultado del substitution test.

Todo se etiqueta como **estimación estructural (sin evidencia de mercado)** y
`proven_demand` permanece en 0 en offline. Las misiones de investigación
aportan los datos reales.
