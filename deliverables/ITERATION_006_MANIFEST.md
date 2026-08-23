# MANIFIESTO ITERACIÓN 006 — FREEBUFF-FIRST CAMPAIGN RUNNER

- **Iteración**: 006
- **Fecha**: 2026-08-23
- **Estado**: COMPLETADA
- **Objetivo**: Sistema Freebuff-first para campañas intensivas de descubrimiento
  por sesiones reanudables de 2-6 h, sin consumir APIs LLM y sin fingir que
  Freebuff es un runtime 24/7. CampaignRunner persistente, protocolo de sesión,
  embudo con límites inmutables, niveles de razonamiento, API Readiness Gate y
  elección documentada del runtime final.

## Resumen de cambios

- **Implementado**: `CampaignService` (máquina de estados CREATED→…→COMPLETED
  con PAUSED/BLOCKED/FAILED/CANCELLED y entregables obligatorios por transición);
  sesiones reanudables (SESSION_PLAN.md, SESSION_STATE.json, SESSION_PROMPT.md,
  SESSION_REPORT.md, NEXT_SESSION.md); `continue_campaign.py` /
  `finalize_session.py`; importación de SESSION_OUTPUT.json con deduplicación y
  política `api_budget_usd=0` (rechaza cualquier output con llamadas/coste > 0);
  niveles de razonamiento registrados; API Readiness Gate determinista
  (API_PREMATURE por defecto, nunca activa claves); piloto sintético
  FREEBUFF-FIRST PILOT 001 (0 llamadas); API `/api/campaigns/*` y
  `/api/sessions/*`; pestaña **Campañas** en el dashboard con badges
  FREEBUFF SESSION / NO 24/7 / API COST 0.
- **Probado automáticamente**: 207 tests (172 previos + 35 nuevos).
- **Verificado manualmente**: 20/20 comprobaciones en vivo por HTTP (piloto,
  sesión, reanudación sin repetir tareas, comité, readiness, economía simulada,
  producción bloqueada).
- **Simulado**: todo el piloto (etiquetado SINTÉTICO; conceptos como hipótesis).
- **Pendiente**: ejecución de campañas reales; runtime externo; APIs tras el gate.

## Archivos nuevos

- `app/models/campaign.py` (Campaign, CampaignTransition, FreebuffSession,
  SessionOutputIn, APIReadinessGate, ReasoningRecord, CampaignCreate, enums)
- `app/core/mission_templates.py` (10 tipos de misión con preguntas/consultas/criterios)
- `app/repositories/campaigns.py` (ff_campaigns, ff_transitions, ff_sessions,
  ff_readiness, ff_reasoning_log)
- `app/services/campaign.py` (CampaignService: 1165 líneas)
- `scripts/continue_campaign.py`
- `scripts/finalize_session.py`
- `tests/test_campaigns.py` (35 tests)
- `docs/FREEBUFF_SESSION_PROTOCOL.md`
- `docs/CAMPAIGN_RUNNER.md`
- `docs/REASONING_BUDGET.md`
- `docs/API_READINESS_GATE.md`
- `docs/RUNTIME_STRATEGY.md`
- `docs/FREEBUFF_RESEARCH_MISSIONS.md`
- `deliverables/ITERATION_006_MANIFEST.md`

## Archivos modificados

- `app/models/campaign.py` (nuevo) — `app/core/config.py` — `app/repositories/db.py`
  — `app/repositories/__init__.py` — `app/services/discovery.py` (import_concept
  público + misiones con plantillas) — `app/services/campaign.py` — `app/core/container.py`
  — `app/api/routes.py` — `frontend/index.html` — `frontend/styles.css` — `frontend/app.js`
  — `README.md` — `AGENTS.md` — `docs/ARCHITECTURE.md` — `docs/SECURITY.md` —
  `docs/ROADMAP.md` — `docs/FREEBUFF_WORKFLOW.md` — `docs/ITERATION_HISTORY.md`

## Archivos eliminados

Ninguno.

## Decisiones técnicas

- Máquina de estados y embudo **sin LLM**: las transiciones validan entregables
  obligatorios de forma determinista.
- `api_budget_usd=0` es **política estructural** (rechazo en la importación),
  no una convención.
- Los límites del embudo viven en `funnel_limits` y nunca aumentan en silencio.
- `maximum_finalists` puede ser 0: ninguna campaña está obligada a producir
  finalistas; los rechazos se conservan como aprendizajes.
- Readiness Gate: solo propuesta (`proposed_daily_limit_usd`), sin claves.
- El piloto reutiliza el Discovery Engine y el ReviewService existentes (sin
  duplicar lógica).

## Cambios en seguridad

- Outputs de sesión = datos no confiables (Pydantic `extra="forbid"`, tamaños,
  no negativos).
- Evidencia sin URL+fecha+fragmento nunca se auto-verifica.
- `docs/SECURITY.md` ampliado (sesiones, coste 0, no inventar capacidades).

## Dependencias añadidas o retiradas

Ninguna.

## Comandos

```bash
# Instalar / ejecutar / probar
pip install -e .            # o: pip install -r requirements.txt (si existe)
uvicorn app.main:app        # arranca API + dashboard en / (o scripts/run.sh)
pytest                      # 207 tests, 100% offline

# Campañas Freebuff-first
python3 scripts/continue_campaign.py --campaign <id> --hours 5
python3 scripts/finalize_session.py --session <session_id>
```

## Resultado exacto de las pruebas

- `python3 -m pytest tests/` → **207 passed** (172 previos + 35 nuevos).
- `node --check frontend/app.js` → OK.
- Validación en vivo por HTTP → **20/20 PASS**.

## Problemas conocidos

- El contador `evidences_added` de la sesión es acumulativo (el delta se mide
  en el repositorio de evidencias); documentado en el test.
- Los finalistas del piloto incluyen variantes recombinadas cercanas al
  original (el anti-clon admite distancia estructural); aceptable para demo.

## Limitaciones

- El piloto es 100% sintético (0 evidencia real, 0 llamadas API).
- El `ManualProvider` y las misiones dependen de que Freebuff investigue en la
  sesión; fuera de sesión no hay proceso garantizado.
- La activación de APIs reales queda pendiente del gate y de una fase futura.

## Riesgos

- Sesiones que no dejan checkpoint pierden contexto (mitigado: finalize
  bloqueado sin entregables; NEXT_SESSION obligatorio).
- Falso consenso del comité (mitigado por etiqueta OPINION_CONSENSUS, 005).

## Componentes que debe revisar el supervisor

1. `app/services/campaign.py` (máquina de estados, importación, readiness).
2. Política `api_budget_usd=0` (rechazo estructural de llamadas).
3. Protocolo de sesión (artefactos y reanudación).
4. Scripts CLI.
5. Tests nuevos (35) y su cobertura de los 38 casos pedidos.

## Próxima acción recomendada

Ejecutar una **campaña real** con sesiones de Freebuff de 2-6 h usando las 10
misiones, medir la calidad de las selecciones y probar el gate con finalistas
reales. No avanzar a APIs ni a runtime hasta que una campaña real lo justifique.

## Nombre del paquete

autonomous-business-lab_iteracion-006_2026-08-23.zip.txt

- **Tamaño del paquete**: 336834 bytes
- **SHA-256 del paquete**: cdcf5d5432589d1ab988a2783380466bc080e227dafe4935b06a04685e14d097

- **Nombre del paquete**: autonomous-business-lab_iteracion-006_2026-08-23.zip.txt
