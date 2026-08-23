# Arquitectura

## Visión general

Autonomous Business Lab es un motor local (FastAPI + SQLite + dashboard web)
que ejecuta un **pipeline multiagente** para convertir problemas de mercado en
oportunidades evaluadas con evidencias, puntuación determinista y un
experimento barato de validación.

```
                         ┌──────────────────────────┐
  Problema / necesidad ─▶│  Scout (1-3)             │──▶ Oportunidades candidatas
                         └──────────────────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │ Researcher (4-6)         │──▶ Evidencias, competidores, cliente
                         └──────────────────────────┘
                                      │
              ┌───────────┬───────────┼───────────┬───────────┐
              ▼           ▼           ▼           ▼           ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Skeptic  │ │ Economist│ │ Builder  │ │Compliance│ │  Judge   │
        │ (crítica)│ │ (costes) │ │(build)   │ │(riesgos) │ │(score)   │
        └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │ Decisión + experimento   │──▶ SQLite + DecisionLog
                         └──────────────────────────┘
```

## Componentes

### `app/core`
- **config.py**: configuración centralizada (pydantic-settings + `.env`).
  Pesos de scoring y bandas de decisión sobreescribibles por entorno.
- **logging.py**: logs estructurados JSON (consola + archivo rotativo).
- **security.py**: límites de tamaño, whitelist de extensiones, validación de
  UUIDs.
- **container.py**: inyección de dependencias manual (fácil de testear).

### `app/models`
Contratos Pydantic: `Opportunity`, `Evidence`, `Competitor`, `Evaluation`,
`Experiment`, `DecisionLog`, `CostRecord`, `LedgerEntry` (asientos contables
simulados con Decimal), `EngineEvent`/`ModeTransition`/`EngineSnapshot`.
Validación estricta (`extra="forbid"`).

### `app/providers`
Abstracción `BaseLLMProvider` con `LLMResponse` normalizado:

| Proveedor | Uso | Coste | Verificación |
|---|---|---|---|
| `MockProvider` | Por defecto / fallback | 0 (offline) | Nunca verifica: marca DESCONOCIDO |
| `GeminiProvider` | Opcional (`GEMINI_API_KEY`) | Estimado por caracteres | No: salida sin verificar |
| `ManualProvider` | Asistido por humano/Freebuff | 0 | Sí si el humano declara `verified: true` |

`ProviderManager` resuelve el proveedor según `LLM_PROVIDER` (`auto|mock|gemini|manual`),
aplica BudgetGuard y hace **fallback automático a mock** ante cualquier fallo
(cuota 429, red, no configurado), registrando el error.

### `app/scoring`
Funciones puras deterministas (ver `docs/SCORING.md`): peso ponderado,
calidad de evidencia, confianza, bandas de decisión y bloqueadores. Sin
efectos laterales.

### `app/agents`
Siete agentes lógicos (módulos internos, no microservicios):

1. **Scout** — genera oportunidades candidatas desde un problema (con
   proveedor LLM o plantillas deterministas).
2. **Researcher** — persiste evidencias/competidores/cliente; nunca inventa:
   lo desconocido se guarda marcado como tal.
3. **Skeptic** — crítica adversaria basada en las evidencias guardadas.
4. **Economist** — estimaciones de precio/margen/recurrencia/tiempo.
5. **Builder** — complejidad, días de construcción, dependencias, %
   automatizable.
6. **Compliance** — riesgos legales/ToS/privacidad/regulatorios; los graves
   bloquean.
7. **Judge** — **determinista**: agrega criterios (con `basis`:
   evidence/estimate/unknown), puntúa y propone experimento.

### `app/repositories`
SQLite (stdlib) con repositorios tipados. Esquema en `db.py`, creado
automáticamente al arrancar. `decision_log` y `costs` son append-only.

### `app/services`
- **BudgetGuard**: presupuesto diario/por oportunidad, tope de evaluaciones
  profundas/día, modos gratuito/simulación, bloqueo manual, registro de coste
  estimado por acción con su método. Consulta el estado económico (modo,
  capacidad, saldo disponible, comprometidos, límites, reconciliación,
  supervivencia) antes de autorizar gasto.
- **EngineService**: modos de operación (incluido `PRODUCTION_ARMED`),
  máquina de estados, guardas deterministas, arranque seguro (→ `SAFE_PAUSE`
  ante inconsistencias) y timeline de eventos.
- **EconomyService**: economía SIMULADA — ledger append-only, capital
  inicial, ingresos, gastos (request→committed→confirmed/rejected),
  reversiones, métricas deterministas (runway, burn rate, coste por
  oportunidad/experimento, margen, survival status) y reconciliación
  (ver `docs/ECONOMY.md`).
- **OpportunityService**: CRUD, detalle agregado, decisiones manuales.
- **ImportService/ExportService**: importación de investigación (JSON) y
  exportación JSON/Markdown.

### `app/workflows/pipeline.py`
Orquesta los 13 pasos, registra cada paso en `decision_log` con coste y
errores, y gestiona estados (`draft → researching → approved/
needs_more_research/deferred/rejected/blocked`).

### `frontend/`
Dashboard vanilla (HTML/CSS/JS) servido por FastAPI en `/`: lista con filtros,
ficha completa, desglose de puntuación con bases, evidencias, competidores,
riesgos, crítica del Skeptic, experimento, log de decisiones y acciones
(aprobar/aplazar/rechazar/reevaluar/exportar).

## Flujo de datos de una evaluación

1. `POST /api/opportunities/discover` → Scout → dedupe por título → `draft`.
2. `POST /api/opportunities/{id}/evaluate`:
   - BudgetGuard `guard_deep_evaluation`.
   - Researcher (borra resultados previos, conserva `decision_log`).
   - Skeptic → Economist → Builder → Compliance → Judge.
   - Se persiste `evaluations` + `experiments`; estado final según decisión.
3. Cada paso genera una entrada en `decision_log` (append-only) y un registro
   de coste en `costs`.

## Persistencia

SQLite en `data/abl.db` (configurable). Tablas: `opportunities`, `evidence`,
`competitors`, `evaluations`, `experiments`, `decision_log`, `costs`,
`engine_state`, `mode_transitions`, `engine_events`, `ledger_entries`
(importes como TEXT para precisión Decimal; `idempotency_key` UNIQUE) y
`reconciliation_runs`. El esquema se crea con `CREATE TABLE IF NOT EXISTS`
(compatible con bases de iteraciones anteriores, sin borrar datos).
`check_same_thread=False` + WAL porque el servidor atiende peticiones en
varios hilos.

El **ledger es append-only**: el saldo se deriva siempre de los asientos,
nunca se persiste un saldo editable. Los asientos confirmados no se editan ni
se borran: se corrigen con una entrada de reversión vinculada
(`reversed_entry_id`).

## Decisiones de diseño

- **SQLite stdlib vs SQLAlchemy**: menos dependencias, cero setup, suficiente
  para el MVP. Los repositorios aíslan la SQL: migrar a SQLAlchemy/Alembic es
  mecánico.
- **Judge sin LLM**: garantiza reproducibilidad y auditaridad de la
  puntuación (requisito del proyecto).
- **Fallback obligatorio**: ningún proveedor es obligatorio; el sistema
  degrada a mock de forma controlada y visible.
- **Sin scraping**: la investigación llega por importación manual/Freebuff o
  (futuro) conectores desacoplados que respeten robots.txt/ToS.
