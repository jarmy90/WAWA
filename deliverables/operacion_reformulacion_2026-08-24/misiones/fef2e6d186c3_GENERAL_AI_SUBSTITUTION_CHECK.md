# Misión de investigación — GENERAL_AI_SUBSTITUTION_CHECK

- **Mission ID**: `fef2e6d186c346edb8d2e6c93267c305`
- **Tipo**: GENERAL_AI_SUBSTITUTION_CHECK
- **Objetivo**: Verificar si una IA generalista (ChatGPT/Gemini/Claude/DeepSeek) resuelve el 80% del problema con un prompt.

## Preguntas
1. ¿Qué pasos del workflow del cliente puede hacer una IA generalista hoy, sin integración?
2. ¿Qué partes requieren datos, integración, memoria o ejecución que una IA generalista no tiene?
3. ¿Existe algún prompt público que ya lo resuelva?
4. ¿Qué mejorará o empeorará con la próxima generación de modelos?

## Consultas sugeridas
- `"{problema}" chatgpt prompt`
- `"{problema}" "just ask AI" OR "AI can do this"`
- `site:reddit.com "{problema}" AI`

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
  "substitution_test": {
    "generic_prompt_solves_80pct": "bool",
    "evidence_url": "str",
    "tested_at": "iso-date",
    "workflow_steps_ai_cannot_do": "list[str]"
  }
}
```