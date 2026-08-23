# API READINESS GATE

> **Estado: IMPLEMENTADO** (iteración 006). Puerta determinista por
> oportunidad que decide si **empezar a gastar tokens tiene sentido**. NO
> activa ninguna API y no configura claves.

## Estados

| Estado | Significado |
|---|---|
| `API_NOT_NEEDED` | El trabajo no requiere ejecución continua |
| `API_PREMATURE` | Faltan criterios (por defecto) |
| `API_USEFUL_FOR_EXPERIMENT` | Útil solo durante el experimento |
| `API_REQUIRED_FOR_DELIVERY` | Necesaria para entregar el servicio |
| `API_REQUIRED_FOR_24_7_OPERATION` | Necesaria para operación continua |
| `API_REJECTED_LOW_ROI` | Coste estimado > valor estimado |

Por defecto el gate devuelve `API_PREMATURE` o `API_NOT_NEEDED`.

## Criterios mínimos

- Oportunidad finalista (aprobada).
- No commodity (General AI Substitution Test superado).
- Comprador concreto.
- Canal viable.
- Resultado verificable.
- Experimento definido.
- Evidencia externa suficiente (URL + fecha + fragmento).
- Comité procesado (≥1 revisión válida).
- Incertidumbre principal identificada.
- Trabajo repetitivo que requiera ejecución continua.
- Coste por llamada estimable y relación coste/valor.
- Fallback posible y límite diario propuesto.

## Garantías

- No configura ni consume claves: solo produce una propuesta
  (`proposed_daily_limit_usd`, `estimated_cost_per_call_usd`).
- Es determinista y auditable (se persiste en `ff_readiness` y se registra un
  evento `api_readiness`).
- La activación real de APIs queda para una fase futura, documentada en
  `docs/ROADMAP.md`.

## Endpoint

```
POST /api/campaigns/{campaign_id}/readiness/{opportunity_id}
```
