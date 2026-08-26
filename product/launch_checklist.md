# Lista mínima de credenciales y acciones humanas (única acción de Javier)

Estado actual: **READY_TO_CONNECT_SERVICES** (todas las precondiciones locales
demostradas). Producción sigue bloqueada. Para llegar a **READY_TO_LAUNCH** el
propietario debe completar esto:

## A. Conectar servicios (una sola pantalla: CONECTAR SERVICIOS)

| Servicio | Variable | Estado | Para qué |
|---|---|---|---|
| Stripe | `STRIPE_SECRET_KEY` | MISSING | Cobro real (checkout 60 EUR hipótesis) |
| Email transaccional | `EMAIL_API_KEY` | MISSING | Confirmación y entrega del informe |
| Hosting | `HOSTING_*` | MISSING | Desplegar landing + checkout |
| Dominio / subdominio | `DOMAIN` | MISSING | URL pública |
| Analytics | `ANALYTICS_*` | MISSING | Eventos visits/leads/checkouts/payments |
| GitHub | — | CONNECTED | Repositorio actual WAWA (artefactos en `product/`) |

Las credenciales se guardan fuera de Git, nunca en logs ni en paquetes, y se
verifican sin revelar su contenido (estado CONNECTED / INVALID / MISSING /
EXPIRED).

## B. Autorizar ciclo autónomo (pantalla única: AUTORIZAR CICLO AUTÓNOMO)

- Oportunidad: Benchmark anónimo de tarifas de ortodoncia
- Oferta: informe por provincia + revisión · Precio hipótesis: 30-90 EUR
- Duración: 30 días · Presupuesto máximo: 0 EUR reales
- Canales permitidos: contacto directo a 20 clínicas (sin spam), colegios y
  directorios, LinkedIn
- Acciones automáticas: seguimiento, generación del informe, informes diarios,
  analytics
- Acciones bloqueadas: gasto real, publicaciones automáticas, mensajería
  masiva, creación de cuentas, trading, acciones irreversibles
- Éxito: 1 pago real (30-90 EUR) · Pivot: interés sin pago a los 14 días ·
  Cierre: sin señal de pago en 30 días

## C. Única acción necesaria de Javier ahora

1. Aportar las credenciales de la tabla A (botón "CONECTAR SERVICIOS").
2. Tras verificar, pulsar "AUTORIZAR CICLO AUTÓNOMO" para el mandato de 30 días.

Sin esas dos acciones el sistema permanece en `READY_TO_CONNECT_SERVICES` con
producción bloqueada — por diseño.
