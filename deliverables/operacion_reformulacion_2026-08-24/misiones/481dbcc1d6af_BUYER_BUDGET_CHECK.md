# Misión de investigación — BUYER_BUDGET_CHECK

- **Mission ID**: `481dbcc1d6af405aa0e4e336e3292bfa`
- **Tipo**: BUYER_BUDGET_CHECK
- **Objetivo**: Confirmar quién paga y de qué presupuesto saldría el dinero.

## Preguntas
1. ¿Quién es el comprador (no solo el usuario)?
2. ¿De qué línea presupuestaria saldría el pago (discrecional, operativa, proyecto)?
3. ¿Qué dispara la compra (evento, urgencia, hito)?
4. ¿Cuánto paga hoy por la alternativa actual?

## Consultas sugeridas
- `"{rol}" budget "{problema}"`
- `"{alternativa actual}" price per month`
- `"{sector}" spend "{categoría}"`

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
  "buyer": {
    "role": "str",
    "budget_source": "str",
    "trigger_event": "str"
  },
  "observed_price": {
    "value": "float|null",
    "currency": "str",
    "source_url": "str",
    "consulted_at": "iso-date"
  }
}
```