# Manifiesto de iteración 005

- **Identificador de iteración**: 005
- **Fecha y hora**: 2026-08-23 (fecha de entrega; hora exacta en el historial)
- **Objetivo**: implementar el **comité de contraste** para oportunidades
  finalistas: revisiones de modelos independientes (GPT, Grok, Gemini, el
  modelo operativo, un supervisor humano...) sin depender de la intervención
  rutinaria del propietario, y sin convertir opiniones de modelos en evidencia.
- **Estado**: `entregado`

## Resumen de cambios

- **Implementado**: cola de finalistas (umbral interno ≥ 72, máximo
  semanal, ventana de 48 h, auto-continuación neutral al caducar); expediente
  de revisión idéntico para todos los revisores (`review_packet.md` con prompt
  normalizado); importación segura de revisiones TXT/Markdown/JSON (raw
  conservado + SHA-256 anti-duplicado + parsing con allowlist + detección de
  prompt injection); síntesis determinista (distribución de recomendaciones,
  consenso `HIGH/MEDIUM/LOW/OPINION_CONSENSUS`, riesgos repetidos/únicos,
  evidencia ausente, acción recomendada); API `/api/reviews/*`; pestaña
  **Laboratorio de oportunidades** en el dashboard; demo 100% sintética
  (`POST /api/reviews/demo`) con sobrecédula del umbral auditable.
- **Probado automáticamente**: 172 tests (149 previos + 23 nuevos), todos
  superados.
- **Verificado manualmente**: 9/9 comprobaciones en vivo con servidor real
  (demo con desacuerdo, cola, expediente + SHA-256, importación HTTP, nueva
  síntesis con 4 revisiones, duplicado 409, inyección señalada sin efectos,
  marcadores `model_opinion_not_evidence`/`real_money_moved`, bajo umbral 422,
  persistencia tras reinicio).
- **Simulado**: todas las revisiones de la demo son `MOCK` etiquetadas; la vía
  funcional es `MANUAL_IMPORT` (sin APIs de pago).
- **Pendiente**: `API_AUTOMATIC` (solo cuando exista API estable, credencial,
  presupuesto y condiciones compatibles — no se inventan integraciones);
  validar con modelos reales si el comité mejora la selección.

## Archivos

- **Nuevos**:
  - `app/models/external_review.py` (ExternalReview, ReviewSynthesis,
    recomendación/ejecución, ReviewImportIn)
  - `app/repositories/reviews.py` (ReviewRepository: cola, revisiones,
    síntesis)
  - `app/services/reviews.py` (ReviewService: expediente, parsing, síntesis,
    demo)
  - `tests/test_external_reviews.py` (23 tests)
  - `docs/EXTERNAL_MODEL_REVIEW.md`, `docs/REVIEW_PACKET_FORMAT.md`,
    `docs/REVIEW_SYNTHESIS.md`, `docs/MANUAL_REVIEW_WORKFLOW.md`,
    `docs/MODEL_CONSENSUS_LIMITATIONS.md`, `docs/REVIEW_SECURITY.md`
  - `deliverables/ITERATION_005_MANIFEST.md` (este)
- **Modificados**:
  - `app/repositories/db.py` (3 tablas: review_queue, external_reviews,
    review_syntheses)
  - `app/repositories/__init__.py` (ReviewRepository en Repos)
  - `app/core/config.py` (config del comité: umbral, máximo semanal, ventana,
    tamaños, extensiones)
  - `app/core/container.py` (ReviewService + hook en pipeline)
  - `app/workflows/pipeline.py` (auto_queue silencioso al aprobar el Judge)
  - `app/api/routes.py` (13 endpoints /api/reviews/* + demo)
  - `frontend/index.html`, `frontend/styles.css`, `frontend/app.js` (pestaña
    Laboratorio)
  - `README.md`, `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`,
    `docs/SECURITY.md`, `.gitignore` (data/external_reviews), 
    `scripts/_review_common.py` (exclusión de expedientes runtime)
- **Eliminados**: ninguno.

## Cambios

- **Arquitectura**: nueva capa `ReviewService` + `ReviewRepository`; el
  pipeline clásico (Ruta A) y el Discovery Engine (Ruta B) permanecen intactos.
- **Modelos de datos**: 3 tablas nuevas con `CREATE TABLE IF NOT EXISTS`
  (compatible con bases anteriores, sin borrar datos); UNIQUE
  (opportunity_id, file_hash) para duplicados.
- **Agentes/prompts**: sin cambios en los 7 agentes; el comité es un servicio
  determinista que complementa al Judge.
- **Scoring**: NO se modifica ningún scoring. Las revisiones externas solo
  informan prioridad/riesgo; `internal_score_after == internal_score_before`.
- **Seguridad**: las respuestas importadas son datos no confiables (allowlist,
  tamaño, hash, detección de inyección, sandbox lógico sin acceso a
  modo/budget/economía). Verificado por tests.
- **Presupuesto**: el comité no gasta (0 offline); `API_AUTOMATIC` queda
  documentado como futuro.
- **Dependencias**: ninguna añadida ni retirada.

## Comandos

- **Instalar**: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- **Ejecutar**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Probar**: `pytest`
- **Empaquetar**: `python3 scripts/package_for_review.py --iteration 5`
- **Verificar**: `python3 scripts/verify_review_package.py`

## Pruebas

- **Resultado exacto**: 172 passed, 0 failed.
- **Comandos usados**: `python3 -m pytest tests/ -q --tb=short` (múltiples
  ejecuciones), `node --check frontend/app.js`, `python3 -c "import app.main"`.
- **Comprobaciones manuales**: servidor real (uvicorn, BD temporal aislada):
  demo del comité por HTTP, expediente con SHA-256, importación + síntesis,
  duplicado 409, inyección señalada con modo intacto, bajo umbral 422,
  persistencia tras reinicio del servidor. Resultado: 9/9.

## Problemas conocidos / limitaciones / riesgos

- **Problemas conocidos**: ninguno bloqueante. Durante la iteración se
  corrigieron: (1) la síntesis perdía la distribución de recomendaciones al
  leer de BD (bug del mapper) — corregido y cubierto; (2) el expediente usaba
  timestamp de generación, rompiendo la idempotencia — corregido a fecha de
  creación de la oportunidad; (3) los expedientes generados en smoke tests
  quedaban en `data/external_reviews` — ahora en `.gitignore` y excluidos del
  paquete.
- **Limitaciones**: el umbral 72 exige evidencia verificada (URL + fecha +
  fragmento), que el mock nunca fabrica — por eso la demo usa una sobrecédula
  explícita y auditada (source=demo-review). El parser es determinista y
  tolerante pero puede necesitar validación humana en respuestas muy libres.
  La vía `API_AUTOMATIC` está documentada, no implementada (sin APIs
  inventadas).
- **Riesgos abiertos**: falso consenso mitigado con etiqueta
  `OPINION_CONSENSUS`; un revisor humano podría querer más control sobre el
  parsing (futuro: editor de campos).
- **Deuda técnica**: `_review_required` usa heurística de texto sobre
  blockers/riesgos (aceptable); la síntesis no pesa la independencia real de
  los modelos (imposible de conocer); la UI importa pegando texto o archivo
  (sin multipart).

## Revisión externa

- **Elementos que debe supervisar el revisor**:
  - Las opiniones de modelos NUNCA son evidencia: no cambian puntuaciones,
    modos ni presupuesto (tests `test_prompt_injection_flagged_not_executed`,
    `test_cannot_authorize_production`, `test_cannot_modify_budget`).
  - Falso consenso: 4 modelos coincidiendo sin citar evidencia → 
    `OPINION_CONSENSUS` y CERO evidencias nuevas añadidas.
  - No-bloqueo: ventana caducada → continuación automática neutral; el
    propietario nunca es un cuello de botella.
  - Sobrecédula demo auditable (solo source=demo-review); la API normal
    rechaza bajo umbral (422) y el máximo semanal (422).
  - Expediente idéntico e idempotente para todos los revisores.
- **Próxima acción recomendada**: usar el flujo manual con GPT/Grok/Gemini
  sobre 2-3 finalistas reales y medir si las objeciones del comité mejoran la
  selección frente al Judge solo; evaluar `API_AUTOMATIC` cuando exista una
  API estable y compatible.

## Paquete

- **Nombre del paquete**: autonomous-business-lab_iteracion-005_2026-08-23.zip.txt
- **Tamaño del paquete**: 283882 bytes
- **SHA-256 del paquete**: f19a63360935d5f317a1dc6d97c655817fbe6873170a33f4f387f95024de6fe4

## Git

- **Commit actual**: pendiente de esta iteración (se completa al commitear).
- **Estado del repositorio**: cambios de la iteración 005 sin commitear.
- **git diff --stat**: (se completa al commitear)
- **Archivos cambiados**: todos los listados arriba.
