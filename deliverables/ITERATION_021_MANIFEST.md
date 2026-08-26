# Manifiesto de iteración 021

- **Identificador de iteración**: 021
- **Fecha y hora**: 2026-08-26
- **Objetivo**: macrooperación de activación comercial: recuperar el estado
  real de la campaña, completar la investigación Fase 1 con evidencia real
  (URL + fecha + fragmento), seleccionar una única ganadora por criterios
  deterministas, preparar el paquete de lanzamiento (landing, checkout,
  email, analytics, términos), conectar el flujo CONECTAR SERVICIOS y el
  mandato AUTORIZAR CICLO AUTÓNOMO en el panel, y dejar el sistema en
  READY_TO_CONNECT_SERVICES con la lista mínima de credenciales humanas.
- **Estado**: `entregado`

## Resumen de cambios

Implementado y probado automáticamente (suite 393 passed; 6 tests nuevos):

1. **Estado real recuperado**: la campaña PRIMERA CAMPAÑA REAL 001 tiene 75
   conceptos (67 NEEDS_REFORMULATION, 5 RECOMBINATION_INCOHERENT, 3
   RESEARCH_PENDING). Las 3 candidatas reales son las ganadoras del torneo
   018: Benchmark de tarifas de ortodoncia (77.5), Benchmark de honorarios de
   gestorías (72.5) y Benchmark de costes de placas solares (72.5). «Cuaderno
   de cuotas» y «modelo 232» NO existen en el universo; no se fabricaron.
2. **Investigación Fase 1 REAL**: 18 misiones importadas (6 por candidata)
   con 31 evidencias verificadas (`verified=true` solo con URL + fecha de
   consulta + fragmento original), fuentes primarias (Sanitas,
   Clínica Friedlander, Prodentis, Cronoshare, OkAsesores, Consejo de
   Gestores, Registro de Gestores, UNEF, Suntropy, ACCA…), competidores y
   `buyer_confirmed` como HIPÓTESIS. `evidence_backed_venture_score` sube de
   0 a 59.14 en las 3 candidatas con 7 grupos independientes.
3. **Ganadora determinista**: Benchmark anónimo de tarifas de ortodoncia
   (única con `low_launch_cost=2/2` y `concierge_delivery=2/2` en el torneo;
   11 evidencias verificadas, 7 grupos). Decisión `approved` (experimento
   SMALL de 30 días) registrada en `decision_log`.
4. **READY_TO_CONNECT_SERVICES** alcanzado honestamente con todas las
   precondiciones (candidata activa, brief válido, Quality Gate, decisión,
   experimento, oferta/precio hipótesis 60 EUR, comprador, canal, métrica de
   éxito, condición de cierre, presupuesto 0 EUR reales, 18 misiones
   importadas, sin deuda ni bloqueadores). Producción sigue bloqueada por
   diseño; `services_connected=false`, `owner_authorized=false`.
5. **Paquete de lanzamiento preparado (NO conectado)**: `product/` con
   landing responsive, contrato de checkout Stripe, plantillas de email
   transaccional, contrato de analytics, términos y privacidad adaptables y
   checklist de credenciales (única acción de Javier).
6. **Panel conectado**: secciones «Candidata ganadora», «CONECTAR
   SERVICIOS» (6 servicios, estados MISSING/CONNECTED, sin secretos) y
   «AUTORIZAR CICLO AUTÓNOMO · 30 DÍAS» (mandato completo con
   `PENDING_OWNER_AUTHORIZATION`) en `/mission-control` vía
   `GET /api/agent-telemetry`.
7. **Trazabilidad**: `OpportunityRepository.get_by_concept` (concepto→
   oportunidad por título normalizado + campaña, nunca IDs foráneos) y
   `DiscoveryRepository.update_mission_target` (persiste `opportunity_id` en
   el target para un readiness inequívoco).
8. **Scripts reproducibles**: `scripts/activate_commercial_021.py`
   (importación de investigación + reevaluación) y
   `scripts/readiness_launch_021.py` (decisión, evaluación derivada, plan,
   auditoría). Datos de investigación en
   `deliverables/operacion_activacion_comercial_2026-08-26/investigacion_fase1_021.json`.

Versión v0.20.0 / build 021-commercial-activation. Sin gasto real (0 EUR),
sin Stripe conectado, sin producción activada, sin acción irreversible.

## Archivos

- **Nuevos**:
  - `scripts/activate_commercial_021.py`
  - `scripts/readiness_launch_021.py`
  - `tests/test_activation_commercial_021.py`
  - `product/README.md`, `product/landing.html`, `product/checkout_prep.md`,
    `product/email_templates.md`, `product/analytics_events.md`,
    `product/terms_privacy.md`, `product/launch_checklist.md`
  - `deliverables/operacion_activacion_comercial_2026-08-26/investigacion_fase1_021.json`
  - `deliverables/ITERATION_021_MANIFEST.md`, `deliverables/ITERATION_021_REPORT.md`
- **Modificados**:
  - `app/repositories/opportunities.py` (`get_by_concept`)
  - `app/repositories/discovery.py` (`update_mission_target`)
  - `app/services/command_center.py` (telemetría: `launch_winner`,
    `services_required`, `authorization_mandate`; iteración 021)
  - `app/core/config.py` (v0.20.0)
  - `frontend/index.html` (v0.20.0 / 021)
  - `frontend/mission-control.html`, `frontend/mission-control.js`
  - `tests/test_ox_alpha_sprint_018.py`, `tests/test_mission_control_020.py`
    (sincronización de versión)
  - `docs/ITERATION_HISTORY.md`
- **Eliminados**: ninguno

## Cambios

- **Arquitectura**: sin workers ni microservicios; todo en el flujo
  existente (misiones → evidencia → venture score → readiness).
- **Agentes/prompts**: ninguno (la investigación la ejecuta Freebuff; se
  importa como datos, no como razonamiento de modelo).
- **Scoring y reglas de decisión**: la ganadora se decide por el torneo 018
  (prioridad determinista) + evidencia verificada; `evidence_backed_venture_score`
  se recalcula con `_evaluate_venture` (sin LLM).
- **Seguridad**: sin secretos en Git; el panel solo expone nombres de
  variable y estado; render escapado (XSS-safe).
- **Presupuesto**: 0 EUR reales; `max_cost_usd=0.0`; producción bloqueada.
- **Modelos de datos**: sin cambio de esquema; `opportunity_id` en el
  `target` JSON de las 18 misiones.
- **Dependencias**: ninguna.

## Comandos

- **Instalar**: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- **Ejecutar**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Probar**: `pytest`
- **Reimportar investigación**: `python3 scripts/activate_commercial_021.py`
- **Fijar readiness**: `python3 scripts/readiness_launch_021.py`

## Pruebas

- **Resultado exacto**: `393 passed, 1 warning in 31.12s`

- **Nombre del paquete**: autonomous-business-lab_iteracion-021_2026-08-26.zip.txt

- **Tamaño del paquete**: 6917671 bytes

- **SHA-256 del paquete**: 44fad77ae2404c69e4015a72837a528e0ddff6ce950b59bf0c7ca681d24ad560
