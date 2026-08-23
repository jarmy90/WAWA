# Limitaciones del consenso entre modelos

> Estado: **implementado** (iteración 005) · Prevención de falso consenso.

## El problema

Varios modelos pueden coincidir sin que eso signifique que tienen razón.
Comparten:

- Datos de entrenamiento (superposición enorme entre GPT, Gemini, Claude...).
- Sesgos y estilos de razonamiento.
- Información incorrecta o desactualizada.
- Suposiciones no verificadas.

Por eso **no se multiplica la confianza porque varios modelos coincidan**.

## Qué distingue la síntesis

- `HIGH` (consenso con base): mayoría ≥60% **y** ≥60% de las revisiones citan
  URL/evidencia concreta.
- `OPINION_CONSENSUS` (falso consenso): mayoría ≥60% **sin** referencias a
  evidencia. Es un aviso: los modelos coinciden en opinión, no en hechos.
- `MEDIUM` / `LOW` / `NONE`: acuerdo parcial, débil o inexistente.
- Riesgos **detectados independientemente** (aparecen en una sola revisión) se
  listan como `unique_risks`; los repetidos como `repeated_risks`. Un riesgo
  repetido no es evidencia externa, pero merece atención.
- Contradicciones entre modelos: se reflejan en la distribución de
  recomendaciones y en la falta de consenso.

## Reglas duras

1. Una afirmación repetida por 4 modelos **no** se convierte en evidencia
   externa (no añade filas a `evidence` ni sube puntuaciones).
2. Las opiniones **no** modifican la puntuación interna
   (`internal_score_after == internal_score_before`).
3. La síntesis puede recomendar `MORE_RESEARCH` o un experimento más barato,
   pero nunca inventa demanda, precios ni competidores.
4. El consenso se muestra con etiqueta clara en el panel (color/texto, no solo
   color): `NONE`, `LOW`, `MEDIUM`, `HIGH` u `OPINION_CONSENSUS`.

## Implicación operativa

Un `OPINION_CONSENSUS` de "experimento prioritario" **no** aprueba nada: la
decisión final sigue siendo del Judge determinista + evidencias verificadas +
reglas de decisión. Las revisiones solo ajustan prioridad, riesgo y diseño del
experimento.
