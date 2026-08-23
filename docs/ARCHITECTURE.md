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
Funciones puras deterministas. Dos capas:
- **Opportunity Score** (`engine.py`, iteración 001): peso ponderado,
  calidad de evidencia, confianza, bandas de decisión y bloqueadores
  (ver `docs/SCORING.md`).
- **Venture Quality Score + General AI Substitution Test** (`venture.py`,
  iteración 004): 11 criterios, bloqueadores duros, etiquetas, originalidad
  con tope de utilidad, fingerprints anti-clon y clasificación de
  sustitución por IA generalista (`COMMODITY_WRAPPER` bloqueada)
  (ver `docs/VENTURE_SCORING.md`). Sin efectos laterales ni LLM.

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
- **DiscoveryService** (iteración 004): campañas de descubrimiento abierto en
  7 fases (exploración amplia → filtro de comoditización → recombinación →
  shortlist con diversidad → torneo por pares → finalistas → tesis/
  experimento), promoción de finalistas a `Opportunity`, misiones de
  investigación Freebuff-first (export Markdown/JSON + import con reglas de
  verificación estrictas) y memoria empresarial (learning records).
  Bibliotecas configurables en `app/core/libraries.py` (31 territorios,
  30 lentes, 27 arquetipos).
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
  exportación JSON/Markdown (oportunidades y misiones).

### `app/core/libraries.py`
Bibliotecas configurables del Business Discovery Engine: territorios de
búsqueda, lentes de innovación y arquetipos de negocio (dataclasses
inmutables). Son espacios para explorar, nunca afirmaciones de demanda.

### `app/workflows/pipeline.py`
Orquesta los 13 pasos, registra cada paso en `decision_log` con coste y
errores, y gestiona estados (`draft → researching → approved/
needs_more_research/deferred/rejected/blocked`).

### `frontend/`
Dashboard vanilla (HTML/CSS/JS) servido por FastAPI en `/`: lista con filtros,
ficha completa, desglose de puntuación con bases, evidencias, competidores,
riesgos, crítica del Skeptic, experimento, log de decisiones y acciones
(aprobar/aplazar/rechazar/reevaluar/exportar). Desde la iteración 004 incluye
la pestaña **Descubrimiento**: campañas, fases ejecutables, conceptos con
Venture Score y clasificación de sustitución, promoción a oportunidad y
creación/exportación de misiones de investigación.

## Flujo de datos de una evaluación

1. `POST /api/opportunities/discover` → Scout → dedupe por título → `draft`.
2. `POST /api/opportunities/{id}/evaluate`:
   - BudgetGuard `guard_deep_evaluation`.
   - Researcher (borra resultados previos, conserva `decision_log`).
   - Skeptic → Economist → Builder → Compliance → Judge.
   - Se persiste `evaluations` + `experiments`; estado final según decisión.
3. Cada paso genera una entrada en `decision_log` (append-only) y un registro
   de coste en `costs`.

## Flujo de datos de una campaña de descubrimiento (Ruta B)

1. `POST /api/discovery/campaigns` → campaña con territorios/lentes/
   arquetipos (vacío = toda la biblioteca).
2. `POST .../phase1` → el proveedor (mock offline o Gemini opcional) genera
   20-200 conceptos; cada uno recibe fingerprint y General AI Substitution
   Test al guardarse.
3. `POST .../filter` → bloquea COMMODITY_WRAPPER, sin comprador, sin
   resultado, regulados; crea learning records.
4. `POST .../recombine` → cruza mecanismos de los que pasaron; los nuevos
   pasan el mismo filtro.
5. `POST .../shortlist` → Venture Quality Score por concepto (novelty por
   distancia, utility por dolor+resultado+comprador), greedy con anti-clon.
6. `POST .../tournament` → comparaciones por pares (8 criterios) guardadas en
   `concept_comparisons`; ranking por victorias; finalistas (≤3).
7. `POST /api/discovery/concepts/{id}/promote` → crea `Opportunity`
   (`source=discovery:<campaign>`).
8. `POST /api/discovery/missions` → misión Freebuff exportable; los
   resultados reimportados se adjuntan a la oportunidad promovida
   (`/api/discovery/opportunities/{id}/missions/{mission_id}/attach`).

## Persistencia

SQLite en `data/abl.db` (configurable). Tablas: `opportunities`, `evidence`,
`competitors`, `evaluations`, `experiments`, `decision_log`, `costs`,
`engine_state`, `mode_transitions`, `engine_events`, `ledger_entries`
(importes como TEXT para precisión Decimal; `idempotency_key` UNIQUE),
`reconciliation_runs` y, desde la iteración 004: `discovery_campaigns`,
`discovery_concepts`, `substitution_tests`, `venture_evaluations`,
`concept_comparisons`, `learning_records`, `research_missions` y
`mission_results`. El esquema se crea con `CREATE TABLE IF NOT EXISTS`
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
