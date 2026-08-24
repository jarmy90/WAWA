# Misión de investigación — DISTRIBUTION_ACCESS_CHECK

- **Mission ID**: `29b5efe094664aa2b4a873cff5f9dc34`
- **Tipo**: DISTRIBUTION_ACCESS_CHECK
- **Objetivo**: Verificar un canal concreto para llegar a los primeros 20 usuarios sin spam.

## Preguntas
1. ¿Dónde están exactamente los primeros 20 usuarios (comunidad, foro, gremio, evento)?
2. ¿Qué comportamiento existente se puede aprovechar (buscan, preguntan, compran algo)?
3. ¿Cómo descubren soluciones hoy?
4. ¿Es legal y compatible con las condiciones del canal?

## Consultas sugeridas
- `"{sector}" community OR association OR group`
- `"{sector}" directory where they list services`
- `"{sector}" forum active "problema"`

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
  "channels": [
    {
      "name": "str",
      "url": "str",
      "activity_evidence": "str",
      "tos_compatible": "bool|null",
      "estimated_reach": "str"
    }
  ]
}
```