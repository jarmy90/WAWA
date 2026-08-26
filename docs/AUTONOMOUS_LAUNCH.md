# Autonomous Launch — contrato operativo (iteración 018)

Diseño del contrato que permitirá lanzar la candidata ganadora **sin** conectar
aún credenciales reales ni mover dinero. Este documento NO autoriza gasto,
publicación ni producción: solo define el estado final verificable y las
condiciones que deben cumplirse antes de cada transición.

## 0. Reglas que este contrato no puede romper

1. `AUTONOMOUS_PRODUCTION` sigue bloqueado por capacidad
   (`production_capability_available=false`); ninguna variable de entorno lo
   activa (máximo `PRODUCTION_ARMED` con precondiciones económicas).
2. Nada de dinero real: `simulated=true`, `real_money_moved=false` en toda
   respuesta económica hasta autorización única del propietario.
3. Ninguna salida de modelo es evidencia; ninguna puntuación de modelo abre
   la puerta de gasto.
4. El ledger es append-only; el control presupuestario es un guard (nunca un
   post-check editable).
5. SAFE_PAUSE ante cualquier configuración inconsistente; el sistema nunca se
   auto-recupera activando producción.

## 1. Estados finales verificables

| Estado | Significado | Condiciones para alcanzarlo |
|---|---|---|
| `READY_TO_CONNECT_SERVICES` | El contrato está completo, la ganadora elegida y los assets preparados; falta SOLO conectar servicios con credenciales reales. | 1) Super-torneo con ganadora(s); 2) misiones Fase 1 completadas con evidencia verificada o kill conditions ejecutadas; 3) brief de producto final; 4) landing/asset mock aprobado; 5) presupuesto aprobado por el propietario (por defecto 0 €); 6) ninguna deuda crítica abierta. |
| `READY_TO_LAUNCH` | Servicios conectados y verificados en modo simulación; falta únicamente el disparo manual del propietario. | Todo lo anterior + servicios conectados (hosting, Stripe, email, analytics) con `billing_verified` donde aplique + prueba end-to-end en sandbox + autorización ÚNICA del propietario registrada en `decision_log`. |

El sistema expone ambos estados como datos deterministas (endpoint de
readiness), nunca como afirmación textual suelta.

## 2. Componentes del contrato

| Componente | Decisión | Estado inicial | Notas |
|---|---|---|---|
| Repositorio de producto | Nuevo repo (o carpeta `product/` en WAWA) | SIN CREAR | Sin decidir hasta ganadora |
| Landing | Estática (Vite/HTML) servida por hosting | BORRADOR | Sin dominio |
| Generación de activos | Scripts locales + plantillas | LOCAL | Sin servicios |
| Hosting | Pendiente de selección | NO CONECTADO | Sin coste |
| Dominio/subdominio | Pendiente | NO CONECTADO | Sin compra |
| Stripe | Checkout/Payment Links | NO CONECTADO | Solo tras READY_TO_CONNECT_SERVICES |
| Webhook | Endpoint FastAPI + firma verificada | NO CONECTADO | Requiere hosting |
| Email operativo | Proveedor transaccional | NO CONECTADO | Sin envíos |
| Entrega | Email + descarga (asset digital) | DISEÑADO | Sin ejecución |
| Analytics | Respetuosa con privacidad (eventos propios) | NO CONECTADO | Sin cookies de terceros |
| Adquisición | Canal definido en brief (orgánico) | HIPÓTESIS | Sin publicidad pagada sin autorización |
| Scheduler | `cron`/proceso único (no workers extra) | DISEÑADO | Sin despliegue |
| Runtime 24/7 | Servidor único + reinicio automático | DISEÑADO | Documentado en RUNTIME_STRATEGY |
| Backup | Copia SQLite cifrada programada | DISEÑADO | Sin secretos en backups |
| Rollback | `git` + restauración de DB | DISEÑADO | Sin automatización destructiva |
| Control presupuestario | BudgetGuard + límites | ACTIVO | 0 € por defecto |
| Log de acciones | `decision_log` + `llm_call_log` | ACTIVO | Append-only |
| Informes diarios | Script de resumen | DISEÑADO | Sin envío automático hasta autorización |
| SAFE_PAUSE | Guard global | ACTIVO | Ver AGENTS.md |

## 3. Límites económicos del ciclo inicial

- Presupuesto base previsto: **hasta 50 €**; ampliación a **100 €** solo con
  autorización explícita del propietario (auditable en `decision_log`).
- Ciclo: 30 días / 50 USD según revisión externa; prórroga única de 14 días.
- Ningún gasto automático fuera del mandato aprobado.

## 4. Investigación asíncrona (no bloquear)

1. Generar expediente automáticamente al finalizar el super-torneo.
2. Lanzar revisiones disponibles (panel manual GPT/Grok/Gemini).
3. Continuar tareas independientes y reversibles mientras las revisiones
   están pendientes.
4. Importar revisiones cuando lleguen (import sin voto: ajuste ±5 máx.
   prioridad/confianza).
5. Timeout: la ausencia es NEUTRAL; nunca bloquea investigación ni
   construcción preliminar.
6. Bloqueo únicamente de: gasto, publicación, acción irreversible y riesgo
   crítico demostrado.

## 5. Puertas de seguridad obligatorias

- Stripe en modo test siempre primero; cargo real solo tras `READY_TO_LAUNCH`
  y autorización única.
- Webhooks con firma verificada y validación de eventos.
- Emails solo a direcciones obtenidas con consentimiento; sin envío masivo.
- Ningún secreto en el repo; claves en gestor de secretos de la plataforma.

## 6. Comprobación de readiness (determinista)

`GET /api/command-center` expone `autonomous_launch.state` con el estado
real: `NOT_STARTED | READY_TO_CONNECT_SERVICES | READY_TO_LAUNCH | BLOCKED`,
derivado de condiciones verificables (no de opiniones de modelo).
