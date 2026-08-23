# Investigación de OmniRoute (iteración 008)

Fecha de consulta: 2026-08-23. Fuente primaria: código fuente del repositorio
`https://github.com/diegosouzapw/OmniRoute` (rama `release/v3.8.50`, MIT).
Consulta realizada clonando el repositorio en `/tmp` (nunca dentro de WAWA).

## Conclusión ejecutiva

- **OmniRoute es real**: gateway local open-source (licencia **MIT**) compatible
  con la API de OpenAI, que enruta peticiones a múltiples proveedores.
- **~342 proveedores** y **90+ tiers gratuitos** documentados en su código.
- **19 estrategias de routing** documentadas.
- El modo `auto` existe y está documentado (`auto/coding`, `auto/cheap`,
  `auto/free:reliable`, etc.).
- **"Alpha 0" NO existe como modelo en el catálogo analizado.** La única
  aparición de "Alpha" es el endpoint `/alpha/generate` de un proveedor
  (Command Code). **No se inventa el slug.** `auto` queda como predeterminado
  provisional hasta disponer de un catálogo real del servicio en ejecución.
- **Limitación del entorno**: `npm install` de OmniRoute falló con `ENOSPC`
  (disco del sandbox agotado, Next.js es muy pesado). No se pudo arrancar el
  servicio aquí; las pruebas reales controladas (máx. 5 llamadas) quedan
  **pendientes** y documentadas en `docs/OMNIROUTE_DEPLOYMENT.md`.

## Estado por punto obligatorio

| # | Punto | Estado | Evidencia / nota |
|---|-------|--------|------------------|
| 1 | README oficial | Documentado | Gateway local, MIT, compatible OpenAI |
| 2 | Licencia | Verificado | MIT (archivo LICENSE en el repo) |
| 3 | SECURITY.md | Documentado | Existe; no se audita en profundidad en esta iteración |
| 4 | Instalación | Documentado | Node >=22.22.2 <23; `npm install`; fallo local por ENOSPC |
| 5 | Docker | Documentado | Dockerfile presente; perfil aislado en `infra/omniroute/` |
| 6 | Proveedores gratuitos | Documentado | 90+ tiers free; lista dinámica vía catálogo |
| 7 | Routing y combos | Documentado | 19 estrategias; `auto` documentado (`auto/free:reliable` etc.) |
| 8 | Endpoint compatible OpenAI | Documentado | `/v1/chat/completions`; handlers en `src/app/api/v1/` |
| 9 | Autenticación local | Documentado | Token CLI `x-omniroute-cli-token`; clave del gateway en secretos |
| 10 | Almacenamiento de credenciales | Parcial | Config local del gateway; no se almacena en WAWA |
| 11 | Telemetría y privacidad | No probado | No verificado en esta iteración; marcar UNKNOWN en allowlist |
| 12 | Mecanismos de actualización | Documentado | Versión fijada recomendada; `release/v3.8.50` |
| 13 | Health checks | Documentado | Endpoint de health; usado en el perfil Docker |
| 14 | Circuit breakers | Documentado | Estrategias de fallback del gateway |
| 15 | Límites y cuotas | Documentado | Límites diarios por proveedor gestionados por el gateway |
| 16 | Structured outputs | No probado | Soporte `response_format` en handlers; pendiente de verificación real |
| 17 | Catálogo de modelos | Pendiente | No ejecutable aquí (ENOSPC); endpoint de modelos al desplegar |
| 18 | Modelo realmente utilizado | Documentado | El gateway expone el modelo servido; WAWA registra `actual_model` |
| 19 | Restricciones de uso comercial | Pendiente | Depende del proveedor upstream; ver `OMNIROUTE_TERMS_RISK.md` |
| 20 | Riesgo de cuentas web/OAuth/sesiones | Parcial | Algunos proveedores requieren sesión web; bloquearlos por defecto |

## Hechos verificados en el código

- `PORT` es configurable por entorno (default 3000); el perfil aislado de WAWA
  usa `127.0.0.1:20128` (punto 3 de arquitectura de la iteración).
- `auto` resuelve modelos dinámicamente por llamada → WAWA registra
  `requested_model` y `actual_model` por llamada (nunca asume igualdad).
- Los endpoints `/v1/*` son compatibles con OpenAI (payload `chat/completions`).

## Lo que NO se verificó (honestidad)

- No se arrancó el servicio (ENOSPC en el sandbox).
- No se consultó el catálogo real de modelos.
- No se verificó structured outputs real.
- No se verificó telemetría real del gateway en ejecución.
- No se confirmó ningún modelo gratuito estable.

Todo lo anterior es **pendiente** y no debe presentarse como verificado.
