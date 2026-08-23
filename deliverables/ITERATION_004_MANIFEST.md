# Manifiesto de iteración 004

- **Identificador de iteración**: 004
- **Fecha y hora**: 2026-08-23 (fecha de entrega; hora exacta en el historial)
- **Objetivo**: construir el **Business Discovery Engine** — descubrir, diseñar,
  comparar y seleccionar ideas de negocio extraordinarias, originales,
  rentables, baratas de validar y **difíciles de sustituir por una IA
  generalista**. Ruta B (open opportunity discovery) con campañas en 7 fases,
  General AI Substitution Test, Venture Quality Score, diversidad anti-clon,
  torneo por pares, memoria empresarial y misiones de investigación
  Freebuff-first.
- **Estado**: `entregado`

## Resumen de cambios

- **Implementado**: Ruta B completa (campañas: exploración amplia → filtro de
  comoditización → recombinación → shortlist con diversidad → torneo → hasta 3
  finalistas → promoción a Opportunity); General AI Substitution Test con
  bloqueo duro de `COMMODITY_WRAPPER`; Venture Quality Score (11 criterios,
  bloqueadores duros, etiquetas, originalidad novelty/utility con tope de
  utilidad); fingerprints estructurales y detección de clones conceptuales;
  memoria empresarial (learning records por rechazo); misiones Freebuff-first
  (Markdown/JSON export + import con reglas de verificación estrictas:
  URL+fecha+fragmento); bibliotecas configurables (31 territorios × 30 lentes
  × 27 arquetipos); API `/api/discovery/*`; pestaña Descubrimiento en el
  dashboard.
- **Probado automáticamente**: 149 tests (125 previos + 24 nuevos de
  discovery), todos superados.
- **Verificado manualmente**: servidor real (uvicorn, BD aislada): campaña
  completa por HTTP, 40 conceptos, diversidad 0.777, filtro 37 passed / 3
  blocked (wrappers de control), recombine 46, shortlist con scores 66-71,
  torneo con ranking, promoción a oportunidad, misión exportada, learning
  records registrados.
- **Simulado**: generación de conceptos offline (mock determinista) con
  controles de comoditización; `proven_demand=0` sin evidencia.
- **Pendiente**: validar la calidad de las selecciones con investigación real
  (misiones Freebuff); ajustar bibliotecas con lo aprendido.

## Archivos

- **Nuevos**:
  - `app/models/discovery.py` (conceptos, misiones, substitution, venture)
  - `app/scoring/venture.py` (Substitution Test + Venture Quality Score)
  - `app/core/libraries.py` (territorios, lentes, arquetipos)
  - `app/repositories/discovery.py` (memoria empresarial SQLite)
  - `app/services/discovery.py` (DiscoveryService, 7 fases, misiones)
  - `tests/test_discovery.py` (24 tests)
  - `docs/DISCOVERY.md`, `docs/VENTURE_SCORING.md`
  - `deliverables/ITERATION_004_MANIFEST.md` (este)
- **Modificados**:
  - `app/repositories/db.py` (8 tablas discovery: campaigns, concepts,
    substitution_tests, venture_evaluations, concept_comparisons,
    learning_records, research_missions, mission_results)
  - `app/repositories/__init__.py` (DiscoveryRepository en Repos)
  - `app/core/container.py` (DiscoveryService)
  - `app/providers/mock.py` (tareas discover_phase1 / discover_recombine +
    controles COMMODITY_WRAPPER)
  - `app/api/routes.py` (15 endpoints /api/discovery/*)
  - `frontend/index.html`, `frontend/styles.css`, `frontend/app.js` (pestaña
    Descubrimiento)
  - `README.md`, `AGENTS.md`, `docs/ARCHITECTURE.md`,
    `docs/FREEBUFF_WORKFLOW.md`, `docs/ROADMAP.md`
- **Eliminados**: ninguno (el `REAME.MD` previo permanece intacto).

## Cambios

- **Arquitectura**: nueva capa DiscoveryService + bibliotecas + scoring de
  venture; el pipeline clásico (Ruta A) permanece intacto.
- **Agentes/prompts**: sin cambios en los 7 agentes; nuevas tareas de
  proveedor `discover_phase1` y `discover_recombine` (MockProvider);
  Gemini las hereda por contrato `BaseLLMProvider` (opcional).
- **Scoring**: se AÑADE la segunda capa Venture Quality Score; el Opportunity
  Score (iteración 001) no se modifica.
- **Modelos de datos**: 8 tablas nuevas con `CREATE TABLE IF NOT EXISTS`
  (compatible con bases anteriores, sin borrar datos).
- **Seguridad**: misiones con regla de no auto-verificación; validación
  estricta de contratos (`extra="forbid"`); sin nuevos secretos ni
  credenciales.
- **Presupuesto**: cada fase registra coste vía BudgetGuard (0 offline);
  ninguna fase nueva requiere API.
- **Dependencias**: ninguna añadida ni retirada.

## Comandos

- **Instalar**: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- **Ejecutar**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Probar**: `pytest`
- **Empaquetar**: `python3 scripts/package_for_review.py --iteration 4`
- **Verificar**: `python3 scripts/verify_review_package.py`

## Pruebas

- **Resultado exacto**: 149 passed, 0 failed.
- **Comandos usados**: `python3 -m pytest tests/ -q --tb=short` (múltiples
  ejecuciones durante la iteración), `node --check frontend/app.js`.
- **Comprobaciones manuales**: servidor real (uvicorn, BD temporal aislada):
  health, frontend 200, campaña completa por HTTP (fase1 40 conceptos /
  diversidad 0.777 / filtro 37+3 / recombine 46 / shortlist 8 / torneo
  ranking / promoción / misión export / learning 3). Resultado: todo OK.

## Problemas conocidos / limitaciones / riesgos

- **Problemas conocidos**: ninguno bloqueante. Durante la iteración se
  corrigieron: (1) el generador offline dejaba buyer/outcome en None y el
  filtro bloqueaba todo — ahora el concepto incluye hipótesis de comprador y
  resultado marcadas como PENDIENTE; (2) el torneo no tenía los venture
  evaluations adjuntos — corregido; (3) FK de mission_results apuntaba al id
  interno en vez de mission_id — corregido; (4) el esquema JSON de la misión
  usaba clases Python (`str`) no serializables — corregido a literales.
- **Limitaciones**: la generación offline es determinista y tosca (perfiles
  por arquetipo/territorio); las respuestas del Substitution Test son
  estimaciones estructurales en modo offline (las misiones pueden
  sustituirlas); la originalidad depende de la distancia dentro de la campaña.
- **Riesgos abiertos**: si el generador produjera siempre los mismos patrones,
  las campañas convergerían — mitigado con wrappers de control y memoria
  empresarial; falta validar con investigación real.
- **Deuda técnica**: el DiscoveryService mezcla orquestación y reglas (aceptable
  para MVP; separar el torneo a un módulo puro si crece); `semantic_distance`
  usa tokens simples (sin stemming); la UI de misiones reimporta por API, no
  por formulario.

## Revisión externa

- **Elementos que debe supervisar el revisor**:
  - Regla dura: `COMMODITY_WRAPPER` no puede aprobarse aunque tenga demanda.
  - Originalidad con tope de utilidad (nadie se autopuntúa).
  - Fingerprints anti-clon (cambiar de sector no es diversidad).
  - Torneo por pares: criterios, guardado y ranking.
  - Misiones: regla de no auto-verificación (URL+fecha+fragmento).
  - Bibliotecas configurables y sesgos a evitar en el generador.
- **Próxima acción recomendada**: usar Freebuff para ejecutar 2-3 misiones de
  los finalistas con investigación real y comprobar si las decisiones del
  torneo se mantienen con evidencia (test de la tesis del motor de ideas).

## Paquete

- **Nombre del paquete**: autonomous-business-lab_iteracion-004_2026-08-23.zip.txt
- **Tamaño del paquete**: 240629 bytes
- **SHA-256 del paquete**: 9d18063082fec4343a5bc79c876c7aa1b290528fff364f13556f764499b93e5b

## Git

- **Commit actual**: ver sección Git del informe de la iteración.
- **Estado del repositorio**: los cambios de esta iteración se commitean al
  final; ver informe.
- **git diff --stat**: ver informe de la iteración.
- **Archivos cambiados**: todos los listados arriba.
