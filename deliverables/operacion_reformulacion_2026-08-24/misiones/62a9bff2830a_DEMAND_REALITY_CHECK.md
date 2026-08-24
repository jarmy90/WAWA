# Misión de investigación — DEMAND_REALITY_CHECK

- **Mission ID**: `62a9bff2830a48dfa1cab93ffddf82a8`
- **Tipo**: DEMAND_REALITY_CHECK
- **Objetivo**: Comprobar si existe demanda REAL y observable del problema, no solo hipótesis.

## Preguntas
1. ¿Dónde expresa la gente este problema hoy (foros, reviews, tickets, comunidades)?
2. ¿Con qué frecuencia y con qué intensidad emocional/económica lo expresan?
3. ¿Qué hacen hoy para resolverlo (o lo ignoran)?
4. ¿Cuántas personas/organizaciones distintas lo manifiestan de forma independiente?

## Consultas sugeridas
- `"{problema}" forum OR reddit OR "help"`
- `"{frase del dolor" how to fix`
- `"{sector}" problem "{síntoma}"`

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
  "evidences": [
    {
      "source_url": "str",
      "consulted_at": "iso-date",
      "fragment": "str",
      "primary_or_secondary": "str",
      "confidence": "0-100",
      "contradictions": "list[str]"
    }
  ]
}
```