# Autonomous Business Lab

Motor local de **descubrimiento, investigación y selección de oportunidades** de microproductos digitales. Un sistema multiagente que convierte problemas de mercado en oportunidades concretas, las investiga, las somete a crítica adversaria y solo selecciona las que tienen evidencias y un experimento barato que las valide.

> **Principio fundamental:** el sistema no confunde una idea bien redactada con una buena oportunidad empresarial. Toda puntuación importante está respaldada por evidencias almacenadas; lo que no está verificado se marca como **desconocido** y reduce la confianza. Nunca inventa demanda, precios, competidores, clientes, estadísticas, enlaces, testimonios ni resultados.

---

## Estado

**MVP v0.3 (iteración 003)** — funciona 100% offline, sin APIs obligatorias. Gemini es un proveedor opcional. Incluye dashboard web local, API, SQLite, 7 agentes, scoring determinista, BudgetGuard, modos de operación (con `PRODUCTION_ARMED` y arranque seguro → `SAFE_PAUSE`), **economía simulada auditada** (ledger append-only, idempotencia, reversiones, métricas, reconciliación) y **124 tests**.

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
# Descubrir oportunidades desde un problema
curl -X POST http://localhost:8000/api/opportunities/discover \
  -H "Content-Type: application/json" \
  -d '{"problem":"Los traders MQL5 no tienen forma barata de auditar sus Expert Advisors."}'

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
├── core/         # Config, logging, seguridad, DI container
├── models/       # Contratos Pydantic (Opportunity, Evidence, Evaluation, ...)
├── providers/    # BaseLLMProvider, Mock, Gemini (opcional), Manual/Freebuff
├── repositories/ # SQLite (stdlib) + repositorios tipados
├── scoring/      # Motor de puntuación determinista (funciones puras)
├── services/     # BudgetGuard, oportunidades, import/export
├── workflows/    # Pipeline de 13 pasos + datos de demo
└── main.py
frontend/         # Dashboard (HTML/CSS/JS vanilla, servido por FastAPI)
tests/            # 80+ tests pytest
data/             # SQLite, demo, research manual
docs/             # Arquitectura, scoring, seguridad, roadmap, workflow Freebuff
scripts/          # run.sh, seed_demo.py
```

La base de datos SQLite se crea automáticamente en `data/abl.db` al arrancar.

## Documentación

| Documento | Contenido |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Arquitectura, flujo de datos, agentes, proveedores, ledger |
| [docs/SCORING.md](docs/SCORING.md) | Pesos, fórmulas, bandas de decisión, bloqueadores |
| [docs/ECONOMY.md](docs/ECONOMY.md) | Economía simulada: reglas contables, métricas, survival status |
| [docs/LEDGER.md](docs/LEDGER.md) | Ledger append-only: modelo, contratos, API, límites |
| [docs/RECONCILIATION.md](docs/RECONCILIATION.md) | Reconciliación y entrada automática en SAFE_PAUSE |
| [docs/OPERATING_MODES.md](docs/OPERATING_MODES.md) | Modos de operación, PRODUCTION_ARMED, arranque seguro |
| [docs/AUTONOMOUS_PRODUCTION.md](docs/AUTONOMOUS_PRODUCTION.md) | Diseño de la fase final (desactivada) |
| [docs/EXTERNAL_REVIEW_WORKFLOW.md](docs/EXTERNAL_REVIEW_WORKFLOW.md) | Workflow de revisión externa (28 puntos, paquetes) |
| [docs/ITERATION_HISTORY.md](docs/ITERATION_HISTORY.md) | Historial de iteraciones y entregas |
| [docs/SECURITY.md](docs/SECURITY.md) | Modelo de amenazas y mitigaciones |
| [docs/FREEBUFF_WORKFLOW.md](docs/FREEBUFF_WORKFLOW.md) | Cómo usar Freebuff para construir y operar |
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

## Decisiones técnicas clave

- **SQLite con `sqlite3` de la stdlib** en lugar de SQLAlchemy: menos dependencias y suficiente para el MVP; los repositorios encapsulan la SQL para migrar fácilmente si hace falta.
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
