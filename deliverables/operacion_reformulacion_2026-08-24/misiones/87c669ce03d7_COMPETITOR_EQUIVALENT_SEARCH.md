# Misión de investigación — COMPETITOR_EQUIVALENT_SEARCH

- **Mission ID**: `87c669ce03d74eeaba961e406f9a0e88`
- **Tipo**: COMPETITOR_EQUIVALENT_SEARCH
- **Objetivo**: Buscar equivalentes directos e indirectos del producto propuesto.

## Preguntas
1. ¿Quién ofrece ya exactamente lo mismo?
2. ¿Quién ofrece una parte (feature) suelta?
3. ¿Quién lo resuelve de forma manual (freelancers, agencias)?
4. ¿Qué precios publican?

## Consultas sugeridas
- `"{solución}" service OR tool OR software`
- `"{problema}" solution price`
- `"{sector}" "{solución}" freelance`

## Regla de no invención
NO inventar demanda, precios, competidores, clientes, estadísticas ni resultados. Si no hay dato, escribir null y marcar el dato como desconocido.

## Criterios de fiabilidad
- Fuente primaria > secundaria.
- URL concreta y fecha de consulta.
- Fragmento textual relevante.
- Notas de incertidumbre cuando aplique.

## Formato de salida (JSON para reimportar)
```json
{
  "competitors": [
    {
      "name": "str",
      "url": "str",
      "offer": "str",
      "observed_price": "float|null",
      "strengths": "list[str]",
      "weaknesses": "list[str]"
    }
  ]
}
```