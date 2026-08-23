# Seguridad de la integración OmniRoute (iteración 008)

## Principios

1. **Aislado por defecto**: `OMNIROUTE_ENABLED=false`. Nada de WAWA depende de
   OmniRoute para arrancar, testear o funcionar.
2. **Solo local**: el gateway se enlaza a `127.0.0.1:20128` (perfil Docker
   opcional). Nunca se expone públicamente sin autenticación.
3. **Sin fabricación**: si OmniRoute falla o no está configurado, **no** se
   genera una revisión mock como si fuese real, no se crea evidencia, no se
   cambia ninguna decisión. Se registra **ausencia neutral** + error.
4. **Sin secretos en Git**: la clave del gateway va solo al gestor de
   secretos del entorno (`OMNIROUTE_API_KEY`), nunca en el repositorio.
5. **Sin datos sensibles**: no se envían secretos, wallets, datos personales,
   datos de clientes, credenciales, código confidencial completo ni
   información financiera sensible a ningún proveedor upstream.

## Allowlist de conexiones

`app/core/omniroute_allowlist.py` define el estado de cada conexión:

- `ALLOWED` — puede usarse.
- `TEST_ONLY` — solo pruebas controladas.
- `BLOCKED` — prohibida.
- `UNKNOWN` — **bloqueada para producción por defecto** (regla: desconocido
  ⇒ bloqueado).

La única conexión registrada inicialmente es `omniroute-gateway`
(localhost, TEST_ONLY). **Ningún proveedor upstream está autorizado** hasta
registrar: proveedor, método de autenticación, ToS, permiso de automatización,
permiso de uso comercial, política de entrenamiento, retención, región, tipo
de datos permitido, fecha de revisión y estado.

## Registro por llamada

Cada llamada OmniRoute registra en `llm_call_log`:

- `provider_requested=omniroute`
- `requested_model` / `actual_model` (nunca se asume que coinciden)
- `actual_provider` (si el gateway lo expone)
- `routing_strategy`
- `fallback_used` / `fallback_reason`
- `response_is_external` / `response_is_synthetic`
- `prompt_tokens` / `completion_tokens`
- `reported_cost` / `estimated_cost` / `cost_source` (nunca un coste
  desconocido se convierte en cero)
- `latency_ms`, `status`, `quota_state`

## Protección de logs

- La clave nunca se imprime ni se loguea.
- Los errores del proveedor se **sanean** antes de persistirlos
  (se eliminan cabeceras de autenticación y cuerpos que puedan contener
  secretos).

## Bloqueos estructurales

- OmniRoute **no** puede activar AUTONOMOUS_PRODUCTION.
- OmniRoute **no** puede modificar presupuestos, modos ni límites.
- OmniRoute **no** sustituye silenciosamente el modelo fijo del comité
  OpenRouter (política por tarea en `app/core/routing_policies.py`).
- El fallback del comité OpenRouter sigue siendo **ausencia neutral**, nunca
  una revisión fabricada.
