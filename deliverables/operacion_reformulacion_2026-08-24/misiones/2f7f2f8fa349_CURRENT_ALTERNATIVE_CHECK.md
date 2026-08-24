# Misión de investigación — CURRENT_ALTERNATIVE_CHECK

- **Mission ID**: `2f7f2f8fa349424990013b09e960a351`
- **Tipo**: CURRENT_ALTERNATIVE_CHECK
- **Objetivo**: Documentar la alternativa real del cliente hoy (incluida 'no hacer nada').

## Preguntas
1. ¿Qué usa hoy el cliente para resolver el problema?
2. ¿Cuál es el coste (tiempo, dinero, riesgo) de la alternativa?
3. ¿Por qué la alternativa no basta?
4. ¿Cuál es el coste de NO resolverlo?

## Consultas sugeridas
- `"{problema}" instead of`
- `"{alternativa}" limitations complaints`
- `"{problema}" "we do it manually"`

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
  "alternatives": [
    {
      "name": "str",
      "url": "str|null",
      "observed_cost": "str|null",
      "weakness": "str",
      "source_url": "str",
      "consulted_at": "iso-date"
    }
  ]
}
```