# Autonomous Business Lab

Motor local de **descubrimiento, investigación y selección de oportunidades** de microproductos digitales. Un sistema multiagente que convierte problemas de mercado en oportunidades concretas, las investiga, las somete a crítica adversaria y solo selecciona las que tienen evidencias y un experimento barato que las valide.

> **Principio fundamental:** el sistema no confunde una idea bien redactada con una buena oportunidad empresarial. Toda puntuación importante está respaldada por evidencias almacenadas; lo que no está verificado se marca como **desconocido** y reduce la confianza. Nunca inventa demanda, precios, competidores, clientes, estadísticas, enlaces, testimonios ni resultados.

---

## Estado

**MVP v0.4 (iteración 004)** — funciona 100% offline, sin APIs obligatorias. Gemini es un proveedor opcional. Incluye dashboard web local, API, SQLite, 7 agentes, **Business Discovery Engine** (campañas de descubrimiento abierto, General AI Substitution Test, Venture Quality Score, torneo de ideas, misiones Freebuff-first), scoring determinista, BudgetGuard, modos de operación (con `PRODUCTION_ARMED` y arranque seguro → `SAFE_PAUSE`), **economía simulada auditada** (ledger append-only, idempotencia, reversiones, métricas, reconciliación) y **149 tests**.

## Requisitos

- Python ≥ 3.10
- pip

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"          # incluye pytest y httpx
# Opcional, para usar Gemini:
pip install -e ".[gemini]"
```

**Sin API configurada**: el sistema arranca igual (proveedor simulado determinista, coste 0).

## Configuración

Copia `env.example` a `.env` y ajusta lo que quieras:

```bash
cp env.example .env
```

Ninguna variable es obligatoria. Para activar Gemini como proveedor opcional, define `GEMINI_API_KEY` (y opcionalmente `LLM_PROVIDER=gemini` o `auto`). **Nunca** se commitean claves: `.env` está en `.gitignore`.

## Ejecución

```bash
# 1) Inicializa SQLite y arranca la API + dashboard (frontend servido en /)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2) Carga los datos de demostración (MQL5) en otra terminal:
curl -X POST http://localhost:8000/api/demo/load?evaluate=true
```

- **Dashboard**: http://localhost:8000
- **API docs (Swagger)**: http://localhost:8000/docs
- **Health**: http://localhost:8000/api/health

Alternativa con script:

```bash
sh scripts/run.sh
```

## Uso rápido (sin navegador)

```bash
# Descubrir oportunidades desde un problema (Ruta A)
curl -X POST http://localhost:8000/api/opportunities/discover \
  -H "Content-Type: application/json" \
  -d '{"problem":"Los traders MQL5 no tienen forma barata de auditar sus Expert Advisors."}'

# Ruta B: campaña de descubrimiento abierto (sin problema previo)
curl -X POST http://localhost:8000/api/discovery/campaigns \
  -H "Content-Type: application/json" \
  -d '{"title":"Campaña Q4","phase1_target":60,"shortlist_target":10,"finalists_target":3}'
curl -X POST http://localhost:8000/api/discovery/campaigns/<ID>/phase1
curl -X POST http://localhost:8000/api/discovery/campaigns/<ID>/filter
curl -X POST http://localhost:8000/api/discovery/campaigns/<ID>/recombine
curl -X POST http://localhost:8000/api/discovery/campaigns/<ID>/shortlist
curl -X POST http://localhost:8000/api/discovery/campaigns/<ID>/tournament
# Promover un finalista a oportunidad y exportar su misión de investigación:
curl -X POST http://localhost:8000/api/discovery/concepts/<CONCEPT_ID>/promote
curl -X POST http://localhost:8000/api/discovery/missions \
  -H "Content-Type: application/json" \
  -d '{"kind":"candidate","concept_id":"<CONCEPT_ID>"}'

# Evaluar una oportunidad (pipeline completo de 7 agentes)
curl -X POST http://localhost:8000/api/opportunities/<ID>/evaluate

# Decidir manualmente
curl -X POST http://localhost:8000/api/opportunities/<ID>/decision \
  -H "Content-Type: application/json" \
  -d '{"decision":"deferred","note":"Revisar con el equipo"}'

# Exportar
curl http://localhost:8000/api/opportunities/<ID>/export?format=json -o opp.json
curl http://localhost:8000/api/opportunities/<ID>/export?format=md   -o opp.md
```

## Tests

```bash
pytest            # suite completa, 100% offline
```

## Estructura

```
app/
├── agents/       # Scout, Researcher, Skeptic, Economist, Builder, Compliance, Judge
├── api/          # Rutas FastAPI
├── core/         # Config, logging, seguridad, DI container, bibliotecas de discovery
├── models/       # Contratos Pydantic (Opportunity, Evidence, Evaluation, discovery...)
├── providers/    # BaseLLMProvider, Mock, Gemini (opcional), Manual/Freebuff
├── repositories/ # SQLite (stdlib) + repositorios tipados (incl. discovery)
├── scoring/      # Opportunity Score + Venture Score + General AI Substitution Test
├── services/     # BudgetGuard, oportunidades, economía, discovery, import/export
├── workflows/    # Pipeline de 13 pasos + datos de demo
└── main.py
frontend/         # Dashboard (HTML/CSS/JS vanilla, servido por FastAPI)
tests/            # 207 tests pytest
data/             # SQLite, demo, research manual
docs/             # Arquitectura, scoring, discovery, seguridad, roadmap...
scripts/          # run.sh, seed_demo.py, empaquetado/verificación
```

La base de datos SQLite se crea automáticamente en `data/abl.db` al arrancar.

## Documentación

| Documento | Contenido |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Arquitectura, flujo de datos, agentes, proveedores, ledger |
| [docs/SCORING.md](docs/SCORING.md) | Pesos, fórmulas, bandas de decisión, bloqueadores |
| [docs/DISCOVERY.md](docs/DISCOVERY.md) | Business Discovery Engine: campañas, fases, territorios/lentes/arquetipos, misiones |
| [docs/VENTURE_SCORING.md](docs/VENTURE_SCORING.md) | Venture Quality Score y General AI Substitution Test (fórmulas y reglas) |
| [docs/ECONOMY.md](docs/ECONOMY.md) | Economía simulada: reglas contables, métricas, survival status |
| [docs/LEDGER.md](docs/LEDGER.md) | Ledger append-only: modelo, contratos, API, límites |
| [docs/RECONCILIATION.md](docs/RECONCILIATION.md) | Reconciliación y entrada automática en SAFE_PAUSE |
| [docs/OPERATING_MODES.md](docs/OPERATING_MODES.md) | Modos de operación, PRODUCTION_ARMED, arranque seguro |
| [docs/AUTONOMOUS_PRODUCTION.md](docs/AUTONOMOUS_PRODUCTION.md) | Diseño de la fase final (desactivada) |
| [docs/EXTERNAL_REVIEW_WORKFLOW.md](docs/EXTERNAL_REVIEW_WORKFLOW.md) | Workflow de revisión externa (28 puntos, paquetes) |
| [docs/ITERATION_HISTORY.md](docs/ITERATION_HISTORY.md) | Historial de iteraciones y entregas |
| [docs/SECURITY.md](docs/SECURITY.md) | Modelo de amenazas y mitigaciones |
| [docs/FREEBUFF_WORKFLOW.md](docs/FREEBUFF_WORKFLOW.md) | Cómo usar Freebuff para construir y operar |
| [docs/FREEBUFF_SESSION_PROTOCOL.md](docs/FREEBUFF_SESSION_PROTOCOL.md) | Sesiones reanudables de 2-6 h: plan, estado, output, report, NEXT_SESSION |
| [docs/CAMPAIGN_RUNNER.md](docs/CAMPAIGN_RUNNER.md) | Máquina de estados de campañas y embudo con límites inmutables |
| [docs/REASONING_BUDGET.md](docs/REASONING_BUDGET.md) | Niveles de profundidad de razonamiento (0-4) y política de coste 0 |
| [docs/API_READINESS_GATE.md](docs/API_READINESS_GATE.md) | Cuándo empieza a tener sentido gastar tokens (por defecto: no) |
| [docs/RUNTIME_STRATEGY.md](docs/RUNTIME_STRATEGY.md) | Escenarios de runtime final (FREEBUFF_SESSION_ONLY / CHEAP / HYBRID) |
| [docs/FREEBUFF_RESEARCH_MISSIONS.md](docs/FREEBUFF_RESEARCH_MISSIONS.md) | Las 10 misiones de investigación para Freebuff y su verificación |
| [docs/EXTERNAL_MODEL_REVIEW.md](docs/EXTERNAL_MODEL_REVIEW.md) | Comité de contraste: revisiones de modelos independientes para finalistas |
| [docs/REVIEW_PACKET_FORMAT.md](docs/REVIEW_PACKET_FORMAT.md) | Formato del expediente de revisión y prompt normalizado |
| [docs/REVIEW_SYNTHESIS.md](docs/REVIEW_SYNTHESIS.md) | Parsing estructurado y síntesis agregada |
| [docs/MANUAL_REVIEW_WORKFLOW.md](docs/MANUAL_REVIEW_WORKFLOW.md) | Flujo manual de revisión con modelos externos |
| [docs/MODEL_CONSENSUS_LIMITATIONS.md](docs/MODEL_CONSENSUS_LIMITATIONS.md) | Falso consenso: límites del acuerdo entre modelos |
| [docs/REVIEW_SECURITY.md](docs/REVIEW_SECURITY.md) | Seguridad del comité (prompt injection, sandbox lógico) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Próximos pasos y limitaciones honestas |
| [AGENTS.md](AGENTS.md) | Reglas para agentes de desarrollo futuros |
| [SECURITY.md](SECURITY.md) | Reporte de vulnerabilidades |

## Workflow permanente del proyecto

El proyecto tiene dos fases separadas: **DEVELOPMENT_AND_REVIEW** (actual:
iteraciones con supervisión externa y paquetes `.zip.txt`) y
**AUTONOMOUS_PRODUCTION** (futura, **desactivada por defecto**, requiere
activación explícita y auditable del propietario).

Antes de cualquier iteración, lee: `AGENTS.md`,
`docs/EXTERNAL_REVIEW_WORKFLOW.md`, `docs/OPERATING_MODES.md` y
`docs/ITERATION_HISTORY.md`. Cada iteración entrega: informe de 28 puntos,
manifiesto `deliverables/ITERATION_NNN_MANIFEST.md`, paquete
`autonomous-business-lab_iteracion-NNN_AAAA-MM-DD.zip.txt` (generado y
**verificado** con `scripts/package_for_review.py` y
`scripts/verify_review_package.py`).

El sistema incluye un mecanismo de modos de operación (`/api/engine/status`,
`/api/engine/mode`): desarrollo, simulación, sombra, `PRODUCTION_ARMED`
(estado previo que una variable de entorno puede alcanzar como máximo) y
pausa segura. **AUTONOMOUS_PRODUCTION está bloqueado por una regla explícita
de capacidad** (`production_capability_available=false`): ni una variable de
entorno ni una clave pueden activarlo — no existe ejecución financiera real
ni verificada. Ante configuraciones inconsistentes (producción sin capital,
ledger inconsistente, etc.) el sistema entra automáticamente en `SAFE_PAUSE`
con motivo auditable.

### Economía simulada

Desde la iteración 003 existe un **ledger contable append-only simulado**
(`/api/economy/*`): capital inicial ficticio, ingresos, gastos
(request → committed → confirmado/rechazado), reversiones auditadas,
idempotencia, métricas deterministas (saldo, burn rate, runway, coste por
oportunidad/experimento, margen, survival status) y reconciliación con
entrada en `SAFE_PAUSE` ante inconsistencias. **Nada de esto mueve dinero
real**: toda respuesta incluye `simulated: true` y `real_money_moved: false`,
y el panel muestra el aviso "SIMULACIÓN — NO REPRESENTA DINERO REAL".
Documentación: `docs/ECONOMY.md`, `docs/LEDGER.md`, `docs/RECONCILIATION.md`.

### Comité de contraste (iteración 005)

El **Laboratorio de oportunidades** (pestaña del dashboard y API
`/api/reviews/*`) somete a las finalistas (puntuación interna ≥ 72) a
revisiones de contraste de **modelos independientes** (GPT, Grok, Gemini,
Claude, humano...). Se genera un expediente idéntico para todos los revisores
(`review_packet.md` con prompt normalizado), se importan respuestas
TXT/Markdown (raw conservado + parsing con allowlist + hash anti-duplicado) y
se agrega una síntesis determinista (distribución de recomendaciones,
consenso con etiqueta `OPINION_CONSENSUS` para falso consenso, riesgos
repetidos, evidencia ausente). **Las opiniones de modelos NO son evidencia**
de demanda: no modifican puntuaciones ni autorizan nada; la ausencia de
revisión es neutral y nunca bloquea el flujo. Prueba: `POST /api/reviews/demo`
(100% sintética). Ver `docs/EXTERNAL_MODEL_REVIEW.md`.

### Business Discovery Engine (iteración 004)

La prioridad central del proyecto es ahora la **calidad del motor de ideas**.
El sistema ya no depende de que le entregues un problema: desde el panel
(pestaña **Descubrimiento**) puedes lanzar **campañas de descubrimiento
abierto** (Ruta B) que:

1. Generan 20-200 conceptos breves combinando **31 territorios × 30 lentes de
   innovación × 27 arquetipos** (`app/core/libraries.py`, configurables).
2. Ejecutan el **General AI Substitution Test**: una idea que una IA
   generalista resuelve sin workflow/integración/memoria se clasifica
   `COMMODITY_WRAPPER` y **no puede aprobarse** (aunque tenga demanda
   aparente).
3. Filtran, **recombinan** mecanismos, hacen **shortlist con diversidad**
   (detecta clones conceptuales) y celebran un **torneo por pares** con 8
   criterios (dolor económico, resistencia a IA, velocidad de validación,
   distribución, activo acumulativo, explicabilidad, margen, merecimiento
   del siguiente euro/hora).
4. Promueven hasta 3 **finalistas** a `Opportunity` y generan **misiones de
   investigación exportables** (Markdown/JSON) para que Freebuff investigue
   con fuentes reales y reimporte los resultados (nada se auto-verifica: se
   exige URL + fecha + fragmento).

El **Venture Quality Score** (11 criterios, 100 puntos) valora la calidad
empresarial y estratégica sin sustituir al Opportunity Score de la iteración
001. En offline, `proven_demand=0`: la demanda nunca se inventa.
Documentación: `docs/DISCOVERY.md`, `docs/VENTURE_SCORING.md`.

### Sesiones Freebuff-first (iteración 006)

El sistema ejecuta campañas de descubrimiento en **sesiones reanudables de
2-6 horas** sin consumir APIs LLM (pestaña **Campañas** del dashboard y API
`/api/campaigns/*`). El `CampaignRunner` persiste estados
(CREATED → … → COMPLETED con PAUSED/BLOCKED/FAILED/CANCELLED), embudo con
límites configurables que nunca aumentan en silencio, niveles de
razonamiento registrados, y un **API Readiness Gate** determinista que decide
si gastar tokens empieza a tener sentido (por defecto: no).

```bash
python3 scripts/continue_campaign.py --campaign <id> --hours 5   # prepara sesión + prompt breve
python3 scripts/finalize_session.py --session <session_id>        # valida, importa, checkpoint
```

Cada sesión deja `SESSION_PLAN.md`, `SESSION_STATE.json`, `SESSION_REPORT.md`
y `NEXT_SESSION.md`; el prompt breve generado se pega directamente a
Freebuff. **Freebuff no es un runtime 24/7** y el proyecto no finge lo
contrario (ver `docs/RUNTIME_STRATEGY.md`). El piloto sintético se lanza con
`POST /api/campaigns/demo` (FREEBUFF-FIRST PILOT 001, 0 llamadas API).

## Decisiones técnicas clave

- **SQLite con `sqlite3` de la stdlib** en lugar de SQLAlchemy: menos dependencias y suficiente para el MVP; los repositorios encapsulan la SQL para migrar fácilmente si hace falta.
- **Business Discovery Engine** (iteración 004): bibliotecas configurables (territorios/lentes/arquetipos), `General AI Substitution Test` con bloqueo duro de `COMMODITY_WRAPPER`, `Venture Quality Score` determinista (11 criterios + bloqueadores + etiquetas), fingerprints anti-clon, torneo por pares, memoria empresarial y misiones Freebuff-first con reglas de verificación estrictas.
- **Judge 100% determinista**: puntúa solo con datos guardados (sin LLM), garantizando reproducibilidad.
- **Proveedores desacoplados**: `MockProvider` (offline, determinista), `GeminiProvider` (opcional, fallback automático a mock), `ManualProvider` (asistido por humano/Freebuff vía JSON).
- **BudgetGuard**: presupuesto diario, por oportunidad, tope de evaluaciones profundas/día, modos gratuito/simulación, bloqueo manual; consulta el estado económico (modo, saldo, comprometidos, límites) antes de autorizar gasto.
- **Ledger contable append-only**: los saldos se derivan siempre de los asientos (Decimal, nunca float); idempotencia por clave; reversiones auditadas; reconciliación con `SAFE_PAUSE` automática.
- **Capacidad de producción explícita**: `production_capability_available=false` bloquea AUTONOMOUS_PRODUCTION de forma auditable, no solo por ausencia de configuración.
- **Nunca se ejecuta código generado**; sin operaciones financieras reales ni publicación automática.

## Limitaciones (resumen honesto)

- En modo offline **ninguna oportunidad alcanza "aprobada"** sin evidencia verificada: es el comportamiento deseado. Para aprobar hace falta importar investigación verificada (ver `docs/FREEBUFF_WORKFLOW.md`).
- La evidencia de la demo (`data/demo/`) es **material ilustrativo sin verificar**: se puntúa con fiabilidad reducida.
- Los datos de demostración no son investigación real de mercado.
- No hay scraping automático en esta versión (solo conectores manuales/importación).
- Ver la lista completa en `docs/ROADMAP.md`.
