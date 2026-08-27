# INFORME DE ITERACIÓN 025 — Autonomous 24/7 OmniRoute Runtime

**Fecha:** 2026-08-27
**Versión:** v0.24.0
**Iteración:** 025
**Objetivo:** Transformar WAWA desde FREEBUFF_SESSION_ONLY a un sistema autónomo real, persistente y ejecutable 24/7 con OmniRoute como runtime LLM principal.

---

## 1. RESUMEN EJECUTIVO

WAWA ahora dispone de un runtime autónomo completo con:

- **Job Queue persistente** en SQLite con leases, prioridades, claims atómicos, reintentos con backoff e idempotencia
- **LLM Runtime Router** con allowlist, circuit breaker, rate limiting por minuto/día, cost tracking y audit trail completo
- **Scheduler** real que arranca con FastAPI lifespan y programa tareas periódicas
- **Worker** real que claim y ejecuta jobs del cola con protección de lease
- **Flujos autónomos** conectados: discovery, arena, research, critique, campaigns, maintenance
- **SAFE_PAUSE** funcional con scope GLOBAL/PROVIDER/CAMPAIGN/JOB_TYPE
- **Approval Queue** para aprobaciones del propietario
- **Preflight checks** que validan readiness antes de activar 24/7
- **Docker Compose** para despliegue con API + OmniRoute
- **Mission Control** actualizado con datos reales del runtime

## 2. CAUSA RAÍZ DEL BLOQUEO ANTERIOR

El sistema anterior dependía de Freebuff como runtime. No existía:
- Scheduler ni worker persistentes
- Cola de jobs sobreviviente a reinicios
- Límites de LLM configurables y auditados
- SAFE_PAUSE funcional
- Mecanismo de aprobación del propietario

## 3. ARCHIVOS NUEVOS

| Archivo | Descripción |
|---------|-------------|
| `app/models/job.py` | Modelo de Job con estados, prioridades, tipos |
| `app/repositories/jobs.py` | Repository SQLite con schema, CRUD, leases, approvals |
| `app/providers/llm_router.py` | LLM Runtime Router con circuit breaker, limits, allowlist |
| `app/services/scheduler.py` | Autonomous Scheduler con polling periódico |
| `app/services/worker.py` | Autonomous Worker con claim y execute |
| `app/services/autonomous.py` | Autonomous Flow con handlers para cada job_type |
| `app/services/safe_pause.py` | SAFE_PAUSE con scope y recovery |
| `app/services/preflight.py` | Preflight checks para 24/7 readiness |
| `docker-compose.yml` | Docker Compose para API + OmniRoute |
| `Dockerfile` | Dockerfile para WAWA runtime |
| `tests/test_autonomous_025.py` | 65 tests del runtime autónomo |

## 4. ARCHIVOS MODIFICADOS

| Archivo | Cambios |
|---------|---------|
| `app/core/config.py` | v0.24.0, +30 variables de autonomous runtime |
| `app/repositories/db.py` | +3 tablas (job_queue, runtime_state, owner_approvals) |
| `app/repositories/__init__.py` | +JobRepository, ApprovalRepository |
| `app/core/container.py` | +scheduler, worker, autonomous_flow, safe_pause, llm_router |
| `app/api/routes.py` | +13 endpoints de runtime (/runtime/*) |
| `app/main.py` | +FastAPI lifespan para scheduler/worker |
| `env.example` | +30 variables de autonomous runtime |
| `frontend/*.html` | v0.24.0, iteración 025 |

## 5. TABLAS NUEVAS

| Tabla | Propósito |
|-------|-----------|
| `job_queue` | Cola persistente de jobs con leases, priorities, retries |
| `runtime_state` | Estado singleton del runtime (scheduler, worker, circuit breaker) |
| `owner_approvals` | Cola de aprobaciones del propietario (append-only) |

## 6. ENDPOINTS NUEVOS

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/runtime/status` | Estado completo del runtime |
| GET | `/api/runtime/preflight` | Preflight checks |
| GET | `/api/runtime/jobs` | Lista de jobs con filtros |
| POST | `/api/runtime/jobs` | Crear job manual |
| POST | `/api/runtime/jobs/{id}/cancel` | Cancelar job |
| POST | `/api/runtime/jobs/{id}/retry` | Reintentar job failed |
| POST | `/api/runtime/pause` | Activar SAFE_PAUSE |
| POST | `/api/runtime/resume` | Desactivar SAFE_PAUSE |
| GET | `/api/runtime/approvals` | Aprobaciones pendientes |
| POST | `/api/runtime/approvals/{id}/decide` | Decidir aprobación |
| GET | `/api/runtime/usage` | Consumo LLM |
| GET | `/api/runtime/provider-health` | Salud OmniRoute |
| GET | `/api/runtime/audit` | Eventos de auditoría |
| POST | `/api/runtime/backup` | Backup de DB |
| GET | `/api/runtime/daily-summary` | Resumen diario |

## 7. FLUJOS AUTÓNOMOS CONECTADOS

| Flujo | Job Types | Estado |
|-------|-----------|--------|
| Discovery | discovery_generate → dedup → classify → scoring → tournament | Conectado a cola |
| Arena | arena_generate → filter → tournament | Conectado a cola |
| Research | research_mission | Conectado, requiere external_reads=true |
| Critique | critique_review | Conectado, usa LLM router auxiliar |
| Campaigns | campaign_advance | Conectado a cola |
| Synthesis | synthesize_and_decide | Conectado |
| Maintenance | healthcheck, lease_recovery, backup, daily_summary | Conectado, periódico |

## 8. GARANTÍAS DE SEGURIDAD

| Garantía | Estado |
|----------|--------|
| production_capability_available=false | ✅ |
| autonomous_allow_financial_actions=false | ✅ |
| autonomous_allow_publication=false | ✅ |
| autonomous_allow_production_deployment=false | ✅ |
| autonomous_allow_external_writes=false | ✅ |
| LLM cost daily limit = 0 (enforcement=true) | ✅ |
| Circuit breaker con threshold=5 | ✅ |
| SAFE_PAUSE funcional | ✅ |
| Approval queue para acciones irreversibles | ✅ |
| No secretos en Git | ✅ |
| Economy sigue SIMULATED | ✅ |
| Judge sigue determinista | ✅ |

## 9. PRUEBAS

- **Suite completa:** 540 passed, 0 failed, 1 warning
- **Tests nuevos de runtime:** 65 passed
- **node --check:** 8/8 JS files OK
- **Cobertura:** job queue, LLM router, circuit breaker, scheduler, worker, autonomous flows, SAFE_PAUSE, approvals, preflight, API endpoints, config defaults, persistence

## 10. MATRIZ DE ESTADO

| Componente | Estado |
|------------|--------|
| Job Queue SQLite | IMPLEMENTADO y PROBADO |
| LLM Runtime Router | IMPLEMENTADO y PROBADO |
| Circuit Breaker | IMPLEMENTADO y PROBADO |
| Scheduler (background thread) | IMPLEMENTADO y PROBADO |
| Worker (background thread) | IMPLEMENTADO y PROBADO |
| Autonomous Flows | IMPLEMENTADO y PROBADO |
| SAFE_PAUSE | IMPLEMENTADO y PROBADO |
| Approval Queue | IMPLEMENTADO y PROBADO |
| Preflight Checks | IMPLEMENTADO y PROBADO |
| FastAPI Lifespan | IMPLEMENTADO y PROBADO |
| Docker Compose | IMPLEMENTADO (no verificado en runtime real) |
| OmniRoute Connection | BLOQUEADO POR CREDENCIAL (sin API key configurada) |
| Real LLM Calls | BLOQUEADO POR CREDENCIAL |
| Production Deployment | BLOQUEADO (production_capability_available=false) |
| Real Financial Actions | BLOQUEADO por regla inmutable |
| Real Publication | BLOQUEADO por regla inmutable |

## 11. LIMITACIONES REALES

1. **OmniRoute no está conectado** en este sandbox (sin credenciales). Las llamadas LLM reales requieren que Javier configure OMNIROUTE_API_KEY o OMNIROUTE_CLI_TOKEN en el gestor de secretos.
2. **Docker Compose** no ha sido verificado en runtime real — el `docker-compose.yml` y `Dockerfile` están listos pero requieren `docker compose up` en un entorno con Docker.
3. **Scheduler/Worker son threads** dentro del proceso Uvicorn. Si se usan múltiples workers Uvicorn, duplicarían scheduler y worker. La solución es `--workers 1` o separar scheduler/worker en un proceso independiente.
4. **Sin auth pública**: los endpoints `/api/runtime/*` no tienen autenticación. En producción requieren red privada o middleware de auth.

## 12. PASOS PARA DESPLEGAR 24/7

### Opción A: Docker (recomendado)

```bash
# 1. Configurar credenciales en .env
cp env.example .env
# Editar .env: OMNIROUTE_API_KEY, OMNIROUTE_ENABLED=true, etc.

# 2. Desplegar
docker compose up -d

# 3. Verificar
curl http://localhost:8000/api/runtime/preflight
# Debe mostrar READY_FOR_AUTONOMOUS_24_7

# 4. Monitorear
curl http://localhost:8000/api/runtime/status
```

### Opción B: Directo (desarrollo)

```bash
# 1. Configurar .env
export AUTONOMOUS_RUNTIME_ENABLED=true
export AUTONOMOUS_SCHEDULER_ENABLED=true
export AUTONOMOUS_WORKER_ENABLED=true
export OMNIROUTE_ENABLED=true
export OMNIROUTE_API_KEY=tu-clave

# 2. Arrancar (single worker)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

### Credenciales pendientes de Javier

1. `OMNIROUTE_API_KEY` o `OMNIROUTE_CLI_TOKEN` — en Settings → Keys
2. Si usa OmniRoute gateway: ejecutar OmniRoute por separado en puerto 20128

---

**Commit:** pendiente de commit y push
**Paquete:** pendiente de generación
