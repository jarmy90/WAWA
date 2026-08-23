# Formato del expediente de revisión (`review_packet.md`)

> Estado: **implementado** (iteración 005).

Para cada oportunidad finalista se genera un expediente **idéntico para todos
los revisores** en:

```
data/external_reviews/opportunity_{id}/review_packet.md
```

La regeneración es **idempotente** (mismo contenido, mismo SHA-256): la fecha
del expediente es la fecha de creación de la oportunidad, no la hora de
generación. No se adapta el texto para persuadir a ningún modelo concreto.

## Secciones

1. **Identificador** (id + título + fecha determinista).
2. **Problema observado**.
3. **Cliente objetivo** (o `DESCONOCIDO`).
4. **Solución propuesta**.
5. **Contexto y evidencias guardadas** (tipo, fuente, URL, fiabilidad,
   verificación, método). Si no hay evidencias: "desconocido", nunca cero.
6. **Competidores, precios observados y alternativas actuales** (precio
   `desconocido` si no hay dato).
7. **Soluciones consideradas** (alternativas reales del cliente).
8. **Diferenciación y canal de adquisición** (estimaciones).
9. **Coste, modelo de ingresos y margen** (siempre etiquetados como
   ESTIMACIONES; `desconocido` si falta el dato).
10. **Datos desconocidos y suposiciones no verificadas**.
11. **Riesgos (Compliance) y crítica interna (Skeptic)**.
12. **Experimento propuesto** (hipótesis, presupuesto máximo, métrica, umbral
    de éxito, umbral de abandono, duración).
13. **Preguntas concretas para el revisor** (supuesto que destruiría la idea,
    evidencia crítica ausente, quién pagaría y de qué presupuesto, alternativa
    actual, sustitución por IA generalista, primeros 20 usuarios, experimento
    más barato, condición objetiva de abandono).
14. **Prompt de revisión normalizado** (verbatim, ver más abajo).

## Prompt normalizado (verbatim, al final del expediente)

```text
Actúa como revisor empresarial independiente y adversarial.

Tu trabajo no es apoyar la propuesta, sino determinar si merece más investigación o una prueba limitada.

Utiliza exclusivamente el expediente proporcionado.

No inventes demanda, cifras, competidores, precios ni capacidades.

Separa hechos, inferencias y supuestos.

Evalúa:

1. Claridad y gravedad del problema.
2. Cliente objetivo.
3. Evidencia de demanda.
4. Disposición a pagar.
5. Acceso al cliente.
6. Competencia.
7. Diferenciación.
8. Modelo de ingresos.
9. Margen.
10. Automatización.
11. Coste y velocidad de construcción.
12. Dependencia de terceros.
13. Riesgo legal y operativo.
14. Calidad del experimento.
15. Supuesto más débil.
16. Evidencia crítica que falta.
17. Alternativa mejor.
18. Motivo principal para continuar.
19. Motivo principal para rechazar.

Devuelve:

- recommendation:
  REJECT
  MORE_RESEARCH
  SMALL_EXPERIMENT
  PRIORITY_EXPERIMENT

- confidence: 0-100
- strongest_evidence
- weakest_assumption
- missing_evidence
- primary_risk
- suggested_improvement
- cheaper_experiment
- kill_condition
- final_reasoning_summary

No confundas una idea original con una oportunidad comercial.
```

## Respuesta esperada del revisor

La respuesta puede venir como texto plano (`clave: valor`), Markdown
(`**clave**: valor`) o bloque JSON. El parser acepta las tres y normaliza
(`REJECT | MORE_RESEARCH | SMALL_EXPERIMENT | PRIORITY_EXPERIMENT`,
`confidence` numérico 0-100). Ver `docs/REVIEW_SYNTHESIS.md` para el parsing
y `docs/REVIEW_SECURITY.md` para la protección contra inyección.
