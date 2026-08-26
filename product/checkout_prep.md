# Checkout preparado (NO conectado)

Contrato mínimo de cobro para la ganadora. Nada está conectado ni se ha
gastado dinero. Se activa cuando el propietario aporte `STRIPE_SECRET_KEY`
en el gestor de credenciales (nunca en Git).

## Requisito

- Proveedor de pago: Stripe (por defecto) u otro medio real autorizado.
- Variable: `STRIPE_SECRET_KEY` → estado `CONNECTED` solo tras verificación
  (pago de prueba de 0,00 € sin capturar, o `GET /v1/balance`).
- El precio hipótesis es **60 EUR** (rango autorizado 30-90 EUR).

## Eventos de checkout (analytics)

| Evento | Trigger | Datos (sin PII) |
|---|---|---|
| `checkout_started` | clic en "Pagar" | product, price_usd, province |
| `checkout_completed` | confirmación de pago | payment_intent_id, amount |
| `checkout_failed` | error/cancelación | product, reason_code |

## Flujo

1. El cliente solicita el informe de su provincia en la landing.
2. Se crea una Payment Intent (Stripe) de `price_usd` EUR (moneda única EUR).
3. Confirmación de pago → se dispara el email transaccional de confirmación.
4. Entrega: PDF del informe + enlace a la videollamada (concierge).
5. Todo el flujo registra eventos en analytics y en `decision_log`
   (append-only, `simulated=false` SOLO cuando haya pago real confirmado;
   mientras tanto `simulated=true`, `real_money_moved=false`).

## Guardas

- **Sin gasto real**: el sistema nunca mueve dinero sin autorización del
  propietario (mandato de 30 días).
- **Idempotencia**: cada pedido con `idempotency_key` única.
- **Reembolso**: reversible manualmente por el propietario (sin reembolsos
  automáticos).
- **Privacidad**: nunca registrar el número de tarjeta ni datos de paciente.
