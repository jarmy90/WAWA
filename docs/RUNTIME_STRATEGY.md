# RUNTIME STRATEGY

> **Estado: DISEÑADO / DOCUMENTADO** (iteración 006). Ningún escenario está
> activado. La arquitectura objetivo recomendada es **HYBRID**.

## A. FREEBUFF_SESSION_ONLY (actual)

**Adecuado para**: investigación, diseño, desarrollo, campañas de
descubrimiento, revisión, construcción manual asistida, mantenimiento del
repositorio.

**No adecuado para**: atención 24/7, webhooks, jobs permanentes, respuestas
inmediatas de clientes, monitorización continua.

Freebuff se usa mediante las capacidades reales de la sesión (repositorio,
terminal, archivos, comandos). **No existe una API de Freebuff** y el sistema
no finge disponibilidad continua.

## B. CHEAP_SCHEDULED_RUNTIME

VPS o hosting Python económico para: scheduler, FastAPI, base de datos, jobs
periódicos, llamadas API puntuales, panel permanente. Requiere desplegar la
aplicación FastAPI existente (la misma que corre localmente).

## C. HYBRID (objetivo recomendado)

- Freebuff para pensar, investigar y construir (sesiones reanudables).
- Runtime económico para ejecutar (scheduler, API, panel, jobs).
- API solo cuando el valor económico de la llamada lo justifique
  (ver `docs/API_READINESS_GATE.md`).

## Decisiones

- No activar ningún runtime en esta iteración.
- No configurar claves ni consumo de API.
- El paso a producción real exige el mecanismo de modos de
  `docs/OPERATING_MODES.md` y AUTONOMOUS_PRODUCTION permanece bloqueado por
  capacidad (`production_capability_available=false`).
