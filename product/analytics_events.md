# Analytics (contrato de eventos — NO conectado)

Requisito: proveedor de analytics autorizado (variable `ANALYTICS_*`).
Estado `MISSING`. Los eventos se registran solo cuando existen datos reales;
sin datos, la métrica se muestra `NO CONECTADO` / `SIN DATOS`, nunca 0.

## Embudo del experimento (30 días)

| Evento | Definición | Métrica |
|---|---|---|
| `page_view` | visita a la landing | visits |
| `lead_created` | solicitud de información / pedido iniciado con contacto | leads |
| `checkout_started` | clic en "Pagar" | checkouts iniciados |
| `checkout_completed` | pago confirmado (Stripe webhook) | payments |
| `report_delivered` | envío del PDF + videollamada agendada | entregas |

## Derivados

- `conversion = payments / leads`
- `margin = price − coste_delivery` (coste de entrega = horas de revisión;
  se documenta como estimación etiquetada, nunca como coste real).

## Guardas

- `simulated=true` hasta pago real confirmado; `real_money_moved=false`.
- Sin PII: no se registran nombres, emails ni datos de pacientes en eventos.
- Si el proveedor no está conectado: `NO CONECTADO`, nunca `0`.
