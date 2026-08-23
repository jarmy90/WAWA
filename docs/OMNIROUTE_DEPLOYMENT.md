# Despliegue aislado de OmniRoute (iteración 008)

OmniRoute es un servicio **externo** al backend Python de WAWA. Nunca se
copia dentro del repositorio, no se hace fork y sus dependencias Node no se
mezclan con el backend.

```
WAWA FastAPI
    |
    | OpenAI-compatible HTTP (solo localhost)
    v
OmniRoute 127.0.0.1:20128
    |
    +-- proveedores autorizados
    +-- modelos gratuitos disponibles
    +-- routing y fallbacks
```

## Opciones evaluadas

| Opción | Uso recomendado | Motivo |
|--------|-----------------|--------|
| A. Docker Compose | **Pruebas y producción** | Aislamiento, versión fijada, límites, health check, restart |
| B. Node/npm oficial | Desarrollo rápido local | Menor sobrecarga, pero menos garantías de aislamiento |

Preferencia inicial: **A. Docker Compose** (aislamiento). Versión fijada
(`release/v3.8.50`), nunca `latest`.

## Perfil opcional (NO arranca con el proyecto)

`infra/omniroute/docker-compose.omniroute.yml` — se activa explícitamente:

```bash
docker compose -f infra/omniroute/docker-compose.omniroute.yml up -d
```

Medidas aplicadas en el perfil:

- Contenedor sin privilegios, filesystem de solo lectura donde es posible.
- Volúmenes mínimos (persistencia del catálogo/config, sin exponer secretos).
- Puerto enlazado **únicamente a `127.0.0.1:20128`**.
- Health check.
- `restart: unless-stopped`.
- Límites de CPU y memoria.
- Logs rotativos.
- **Sin** Docker socket, **sin** acceso innecesario a red interna.
- Secretos fuera del repositorio (`.env.omniroute` ignorado por Git).

## Despliegue 24/7 futuro (documentado, NO activado)

Criterios mínimos antes de declarar cualquier disponibilidad continua:

1. 72 horas continuas en shadow mode.
2. Reinicios recuperados automáticamente.
3. Cuotas respetadas (nunca se excede `OMNIROUTE_DAILY_REQUEST_LIMIT`).
4. Ninguna clave en logs.
5. Ninguna revisión fabricada (ausencia neutral verificada).
6. Catálogo y modelo real registrados.
7. Términos de proveedores autorizados (allowlist completa).
8. Costes reconciliados.
9. Sin fallos críticos.

WAWA y OmniRoute correrían como servicios separados, con restart automático,
backups y logs separados, health checks, watchdog, versiones fijadas y
rollback. **Ninguna de estas garantías está activa hoy**: una única llamada
funcionando no convierte el sistema en 24/7.

## Estado actual de la integración

- **Implementado**: proveedor aislado, routing por tarea, allowlist, perfil
  Docker, tests offline (23), benchmark A/B (arm A offline ejecutado).
- **No probado en esta iteración**: arranque real de OmniRoute (`npm install`
  falló con `ENOSPC` en el sandbox), catálogo real, llamadas reales (las 5
  máximas quedan reservadas a un entorno con disco suficiente).
