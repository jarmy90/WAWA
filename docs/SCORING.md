# Sistema de puntuación

## Criterios y pesos (configurables)

| Criterio | Peso | Base esperada |
|---|---|---|
| `pain` (dolor y urgencia) | 20% | evidence |
| `demand` (evidencia verificable de demanda) | 20% | evidence |
| `customer_reach` (facilidad para localizar clientes) | 15% | estimate |
| `automation` (capacidad de automatización) | 15% | estimate |
| `margin` (margen estimado) | 10% | estimate |
| `build_speed` (velocidad y coste de construcción) | 10% | estimate |
| `differentiation` (diferenciación frente a alternativas) | 5% | estimate |
| `safety` (seguridad legal y operativa) | 5% | estimate |

Los pesos por defecto suman 1.0 y se pueden sobreescribir con
`SCORING_WEIGHTS_JSON`. Las bandas de decisión con `DECISION_BANDS_JSON`.

Cada criterio lleva un **`basis`** que indica de dónde salió su puntuación:

- `evidence` → respaldado por evidencias guardadas (`evidence_ids`).
- `estimate` → estimación de un agente (Economist/Builder) o heurística.
- `unknown` → no hay datos; puntuación baja y confianza reducida.

## Fórmulas

### Puntuación final (0-100)

```
final = Σ(criterio_i * peso_i) / Σ(pesos)
```

### Evidence Quality Score (0-100)

```
sin evidencias reales           -> 0
avg_rel       = media(reliability_score)
verif_factor  = 0.5 + 0.5 * (verificadas / total)
indep_factor  = min(grupos_independientes, 3) / 3
raw           = avg_rel * verif_factor * (0.4 + 0.6 * indep_factor)
EQ            = min(100, raw * 100)
```

La **fiabilidad** (0-1) la asigna la fuente/método. La **verificación** solo
la concede un humano (import manual con `verified: true`) o una fuente
contrastable. La **independencia** premia que varias fuentes distintas
confirmen lo mismo (máximo 3 grupos).

### Confidence Score (0-100)

```
coverage = Σ(peso_i * factor(basis_i)) / Σ(pesos)
factor: evidence=1.0, estimate=0.5, unknown=0.0
confidence = 0.7 * coverage * 100 + 0.3 * EQ
```

## Bandas de decisión

| Puntuación | Decisión |
|---|---|
| 75 – 100 | `approved` (candidata a experimento) |
| 60 – 74 | `needs_more_research` |
| 40 – 59 | `deferred` (aplazada) |
| 0 – 39 | `rejected` |

## Bloqueadores (override)

Si existe **cualquier** bloqueador, la decisión es `blocked` aunque la
puntuación sea alta. Fuentes de bloqueadores:

- Sin evidencias reales guardadas.
- Sin cliente objetivo concreto.
- Sin forma razonable de llegar a compradores.
- Gasto inicial elevado.
- Riesgo grave detectado por Compliance (ej. promesa de rentabilidad).
- Dependencia de plataforma externa que prohíba la automatización.
- Actividad regulada que el sistema no pueda cumplir.

## Metadatos de cada evaluación

- `evidence_quality_score` (0-100)
- `confidence_score` (0-100)
- `independent_evidence_count` (grupos independientes, excluye `none`)
- `unverified_assumptions_count` (suposiciones sin verificar)
- `approval_reason` / `rejection_reason` (motivo principal)
- `blockers` (condiciones que harían cambiar la decisión)

## Ejemplo trabajado (caso real de la demo)

Auditoría automática de EAs MQL5 (4 evidencias de demo, no verificadas,
fiabilidad media ~0.64, 3 grupos independientes) — valores reales de la
demo ejecutada:

| Criterio | Score | Basis | Aporte |
|---|---|---|---|
| pain | 58.8 | evidence | 11.8 |
| demand (EQ ≈ 31.9) | 31.9 | evidence | 6.4 |
| customer_reach | 60.0 | estimate | 9.0 |
| automation | 80.0 | estimate | 12.0 |
| margin | 70.0 | estimate | 7.0 |
| build_speed | 75.0 | estimate | 7.5 |
| differentiation | 80.0 | estimate | 4.0 |
| safety | 70.0 | estimate | 3.5 |

**Final ≈ 61.1 → `needs_more_research`** (60-74). Sin evidencia verificada,
el sistema es honestamente escéptico: es exactamente el comportamiento
deseado. Para aprobar, hay que importar investigación verificada.

## Reproducibilidad

El Judge es 100% determinista: los tests comprueban que la misma entrada
produce exactamente la misma puntuación y decisión en ejecuciones repetidas.
