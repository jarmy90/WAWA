# Producto: Benchmark de Tarifas de Ortodoncia (ganadora iteración 021)

Estado: `READY_TO_CONNECT_SERVICES` (falta conectar servicios y autorización
del propietario). Nada de este directorio está conectado ni publicado.

## Oportunidad ganadora (decisión determinista)

- **Concepto**: Benchmark anónimo de tarifas para clínicas dentales que
  deciden su precio de ortodoncia (`3867e04e…`).
- **Oportunidad**: `c1dfd7d5…` · **Plan de experimento**: `4e7647f4…`.
- **Evidencia**: 11 evidencias verificadas (URL + fecha 2026-08-26 + fragmento),
  7 grupos independientes, `max_evidence_score=100`.
- **Score con evidencia**: `evidence_backed_venture_score = 59.14` (sube de 0).
- **Torneo 018**: 77.5 (única con `low_launch_cost=2/2` y `concierge_delivery=2/2`).
- **Decisión**: `approved` (candidata a experimento SMALL de 30 días).

## Problema (hipótesis)

Las clínicas dentales pequeñas (2-5 dentistas) fijan el precio de ortodoncia
sin un comparativo de tarifas de su zona y pierden margen o pacientes. La
evidencia documenta dispersión real (2.900-8.100 € según fuentes públicas) y
que la fijación de precios es un problema de gestión conocido del sector.

## Oferta y precio

- **Oferta**: Informe de benchmark anónimo de tarifas de ortodoncia por
  provincia (rangos y percentiles) + revisión por videollamada.
- **Precio hipótesis**: 30-90 EUR (midpoint 60 EUR) — HIPÓTESIS, sin
  comprador real todavía.
- **Entrega**: concierge (PDF + revisión), plantillable y automatizable.

## Qué hay aquí (preparado, NO conectado)

| Archivo | Contenido |
|---|---|
| `landing.html` | Landing responsive del producto (estática, sin backend) |
| `checkout_prep.md` | Contrato de checkout Stripe (requiere `STRIPE_SECRET_KEY`) |
| `email_templates.md` | Plantillas de email transaccional (requiere `EMAIL_API_KEY`) |
| `analytics_events.md` | Contrato de eventos: visits, leads, checkouts, payments |
| `terms_privacy.md` | Términos y privacidad adaptables |
| `launch_checklist.md` | Lista mínima de credenciales y acciones humanas |

## Condiciones del experimento (30 días)

- **Éxito**: 1 pago real confirmado (30-90 EUR) por un comprador real.
- **Pivot**: interés sin pago tras 14 días → aseguradoras/software dental,
  ampliar especialidades, suscripción trimestral.
- **Cierre**: sin señal de pago en 30 días y sin pivote viable.
- **Presupuesto real**: 0 EUR (producción bloqueada; sin gasto real).

## Garantías

- Producción sigue bloqueada (`production_capability_available=false`).
- Sin datos de pacientes: el informe es anónimo y agregado.
- Sin spam: captación manual autorizada (20 clínicas vía colegios/directorios).
- Sin secretos en Git: las claves van en el gestor de credenciales.
