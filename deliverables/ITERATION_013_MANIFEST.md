# MANIFIESTO ITERACIÓN 013 — CALIDAD SEMÁNTICA, ESTADOS HONESTOS Y REFORMULACIÓN ANTES DE INVESTIGAR (v0.12.0)

- **Iteración**: 013 (detectada automáticamente: max(manifiestos)=012 → siguiente=013)
- **Versión**: 0.12.0
- **Fecha**: 2026-08-23
- **Estado**: COMPLETADA — 300 tests pasan (283 previos + 17 nuevos), aceptación real con navegador superada
- **Objetivo**: corregir el fallo estructural detectado en la inspección humana de las 66 ideas: etiquetas ambiguas (passed/promoted/eliminated), ventajas sin evidencia presentadas como hechos, Venture Scores 60-71 sin comprador/demanda/precio/canal, combinaciones mecánicas territorio+lente+arquetipo y recombinaciones incoherentes. Nada de eso se investiga hasta ser una oportunidad concreta.

## Problema que corrige

1. `passed`, `promoted`, `eliminated`, `clone`, `blocked` no explicaban el estado real de cada concepto.
2. `DEFENSIBLE_WORKFLOW`, `DATA_ADVANTAGE`, `NETWORK_ADVANTAGE`, `COMPOUNDING_SYSTEM` se mostraban como conclusiones sin evidencia.
3. Venture 60-71 para conceptos sin comprador confirmado, sin demanda, sin precio y sin canal.
4. Recombinaciones incoherentes como "Capa de confianza para soledad y coordinación social no romántica adaptado a Logística local".
5. Las 3 candidatas promovidas eran abstractas ("Vender tiempo ahorrado para cambios regulatorios", "Activo de memoria personal para intermediarios opacos", "Cooperativa de datos para decisiones con alta incertidumbre").

## Cambios implementados

### 1. Estados inequívocos (en español, con significado)
`app/scoring/semantic_gate.py` define 15 estados y su significado: GENERATED_HYPOTHESIS, DEDUP_PASSED, AI_FILTER_PASSED, STRUCTURAL_FILTER_PASSED, RECOMBINATION_INCOHERENT, DIVERSITY_ELIMINATED, CONCEPTUAL_CLONE, COMMODITY_BLOCKED, NEEDS_REFORMULATION, RESEARCH_CANDIDATE, RESEARCH_PENDING, EVIDENCE_INSUFFICIENT, SHORTLISTED_WITH_EVIDENCE, FINALIST, EXPERIMENT_READY. Los estados prohibidos (`passed`, `promoted`, `blocked`, `eliminated`, `shortlisted`, `finalist`, `clone`, `draft`, `recombined`) nunca se muestran. Cada tarjeta explica estado + qué significa + filtro superado + qué falta + próxima acción.

### 2. Ventajas como hipótesis
Sin evidencia verificable, las clasificaciones se muestran como `HYPOTHESIS_DEFENSIBLE_WORKFLOW` / `HYPOTHESIS_DATA_ADVANTAGE` / `HYPOTHESIS_NETWORK_ADVANTAGE` / `HYPOTHESIS_COMPOUNDING_SYSTEM` ("Hipótesis: posible workflow defendible", etc.). Solo se retira "Hipótesis" con evidencia verificable específica.

### 3. Dos puntuaciones separadas
- `structural_concept_score`: calidad interna de la formulación (pre-evidencia). La interfaz dice "Puntuación estructural", nunca "Venture".
- `evidence_backed_venture_score`: 0 sin evidencia; tope 40 con evidencia insuficiente (<3 grupos independientes); score real solo con ≥3 grupos. Sin evidencia, `proven_demand` y `distribution` valen 0 (nunca se inventa demanda).

### 4. Quality Gate semántico (Opportunity Brief)
Antes de RESEARCH_CANDIDATE, el concepto debe completar un brief de 19 campos concretos (specific_name, user, buyer, situation, observable_problem, current_alternative, economic_or_time_cost, concrete_deliverable, measurable_outcome, revenue_model, expected_price_hypothesis, first_distribution_channel, first_20_buyers_location, test_in_48_hours, generic_ai_limitation, compounding_asset, primary_risk, assumptions, prohibited_claims). Se bloquean marcadores genéricos ("profesional o pequeña organización", "persona interesada", "sufre el territorio", etc.) → NEEDS_REFORMULATION. Un concepto NEEDS_REFORMULATION nunca se promueve ni genera misiones.

### 5. Test de coherencia semántica determinista
`semantic_coherence()` detecta el patrón "X para <contexto A> adaptado a <contexto B>" sin solapamiento y las 3 frases incoherentes reales detectadas (casos fijos que deben fallar siempre). El mecanismo debe compartir términos con problema/comprador/entrega.

### 6. Reformulaciones concretas + torneo
`generate_reformulations()` produce 3-5 reformulaciones concretas por familia (regulatorio: RGPD, modelo 232, Next Generation, Crea y Crece; intermediarios: inmobiliarias, plataformas, administradores de fincas; incertidumbre: clínicas dentales, placas solares, gestorías) con brief pre-rellenado como HIPÓTESIS (nunca evidencia). `run_reformulation_tournament()` selecciona MÁXIMO 3 candidatas (0 es válido; no hay obligación de conservar una idea de cada familia).

### 7. Misiones progresivas
Solo Fase 1 (6 misiones de descarte: DEMAND_REALITY_CHECK, BUYER_BUDGET_CHECK, CURRENT_ALTERNATIVE_CHECK, DISTRIBUTION_ACCESS_CHECK, COMPETITOR_EQUIVALENT_SEARCH, GENERAL_AI_SUBSTITUTION_CHECK) por candidata. La Fase 2 (MOAT, DATA, TOS_LEGAL, EXPERIMENT_FEASIBILITY) solo para supervivientes. Nunca se generan las 10 de golpe.

### 8. Reproceso de la campaña actual (sin borrar nada)
`POST /api/discovery/campaigns/{id}/reprocess`:
- Mapea estados antiguos → nuevos (66/66 mapeados en la campaña real).
- Re-evalúa coherencia y marcadores genéricos.
- Invalida las 30 misiones antiguas con `SUPERSEDED_BY_SEMANTIC_QUALITY_GATE` (conservadas, no contadas como pendientes).
- Genera reformulaciones para las candidatas previas, ejecuta el torneo y crea misiones de Fase 1 solo para candidatas concretas.
- PRE_CYCLE permanece detenido (reloj no arranca).

### 9. Resultado del reproceso de la campaña real (verificado en vivo)
- 66 conceptos conservados + 9 reformulaciones = 75 con trazabilidad.
- 61 → NEEDS_REFORMULATION · 5 → RECOMBINATION_INCOHERENT · 3 → RESEARCH_PENDING (candidatas concretas seleccionadas: Benchmark de tarifas de clínicas dentales, Benchmark de costes de instalación de placas solares, Benchmark de honorarios de gestorías).
- 30 misiones antiguas → SUPERSEDED; 18 misiones de Fase 1 activas (3 candidatas × 6).
- 0 finalistas (resultado válido: no se fuerzan).
- PRE_CYCLE · clock_running=false · started_at=null.

### 10. Exportaciones honestas
CSV con columnas nuevas: `ai_substitution_label`, `structural_concept_score`, `evidence_backed_venture_score`, `status_meaning`, `passed_dedup/passed_ai_filter/passed_structural_filter/entered_shortlist/finalist` calculados con los estados nuevos; Markdown con embudo honesto (incluye "Necesitan reformulación" y "4b. Ideas que necesitan reformulación" sin ocultar descartadas).

### 11. Frontend
Tarjetas de Ideas corregidas (Estado / Qué significa / Filtros superados / Evidencia / Comprador / Problema / Entrega / Canal / Puntuación estructural / Puntuación con evidencia / Motivo / Qué falta / Próxima acción), filtros nuevos (reformulación, descartadas, candidatas, investigación), contadores del embudo honestos, sin "promoted" ni "passed". Versión visible v0.12.0, iteración 013.

## Archivos nuevos
- `app/scoring/semantic_gate.py`
- `tests/test_semantic_gate_013.py` (17 tests)
- `deliverables/ITERATION_013_MANIFEST.md` (este archivo)
- `deliverables/browser_body_text_013.txt`
- `deliverables/screenshots-013/` (01-home-1440, 02-home-390, 03-campaign, 04-ideas, 05-research)
- `deliverables/business_ideas_campaign_reprocesada.csv` y `.md` (descargados desde el navegador)

## Archivos modificados
- `app/scoring/venture.py` (split estructural/evidencia; proven_demand/distribution a 0 sin evidencia)
- `app/models/discovery.py` (VentureEvaluation: structural_concept_score, evidence_backed_venture_score, has_verified_evidence)
- `app/models/orchestrator.py` (RESEARCH_PHASE1_KINDS / RESEARCH_PHASE2_KINDS)
- `app/repositories/db.py` (migración idempotente: columnas venture + brief/coherence en concepts)
- `app/repositories/discovery.py` (save/read de columnas nuevas, update_mission_status, missions_by_campaign, update_concept con brief)
- `app/services/discovery.py` (estados nuevos, gate en shortlist, torneo con 0 finalistas válido, recombinación opcional, reprocess, reformulaciones, complete_opportunity_brief, demo_brief_for, enriquecimiento de conceptos)
- `app/services/orchestrator.py` (planificación de investigación solo con candidatas concretas, misiones de Fase 1, supersede de misiones previas, contadores nuevos)
- `app/services/campaign_exports.py` (columnas/embudo/estados nuevos)
- `app/services/campaign.py` (demo con briefs de hipótesis, estados nuevos)
- `app/api/routes.py` (POST /reprocess, /reformulations/{concept_id}, /concepts/{id}/brief)
- `frontend/app.js`, `frontend/index.html` (tarjetas honestas, filtros, contadores, v0.12.0)
- `app/core/config.py`, `app/__init__.py` (v0.12.0)
- `tests/test_discovery.py` (contrato nuevo)
- `docs/ITERATION_HISTORY.md`, `README.md`

## Resultado de pruebas
- `python3 -m pytest tests/` → **300 passed** (283 previos + 17 nuevos), 1 warning.
- `node --check frontend/app.js` → OK.
- Aceptación real (navegador, puppeteer/Chromium sobre la página HTTP servida):
  - 1440×900: navegación + INICIAR CAMPAÑA REAL + PRE_CYCLE visibles, sin scroll (docH==winH==900). ✅
  - 390×844: navegación + botón visibles, sin scroll. ✅
  - Vista Campaña real: embudo honesto (75 conceptos, 67 reformulación, 5 descartados, 3 candidatas, 0 finalistas). ✅
  - Vista Ideas: tarjetas corregidas (67 × "NECESITA REFORMULACIÓN" con significado, puntuación estructural/evidencia). ✅
  - Vista Investigación: 18 misiones de Fase 1. ✅
  - Descargas reales desde el navegador: CSV (123 269 B), Markdown (150 148 B), research .zip (28 838 B). ✅
  - `document.body.innerText`: contiene "Campaña real", "Ideas", "INICIAR CAMPAÑA REAL", "PRE_CYCLE", "PRIMERA CAMPAÑA REAL 001"; NO contiene "Cargar demo", "MQL5", "MetaTrader", "Expert Advisor". ✅
  - 0 errores de consola. ✅

## Validación de los criterios de cierre (sección 13 del requisito)
- 66 ideas conservan trazabilidad: ✅ (75 conceptos, ids originales intactos)
- Ninguna etiqueta ambigua: ✅ (vocabulario nuevo; FORBIDDEN_STATUSES test)
- Ventajas sin evidencia como hipótesis: ✅
- Score previo llamado "puntuación estructural": ✅ (frontend + CSV)
- Score de viabilidad con evidencia comienza en 0: ✅ (test)
- Candidatas son propuestas concretas: ✅ (gate de brief de 19 campos)
- Misiones antiguas superseded: ✅ (30/30 en la campaña real)
- Solo 6 misiones iniciales por candidata: ✅ (18 = 3×6; test de no-10)
- Puede haber 0 candidatas / 0 shortlist / 0 finalistas: ✅ (tests + 0 finalistas reales)
- PRE_CYCLE detenido: ✅ (cycle.evaluate tras reprocess)
- No se inventa evidencia: ✅ (briefs = hipótesis; misiones de descarte con regla de no invención)
- Captura de tarjetas corregidas y CSV reprocesado: ✅ (screenshots-013, business_ideas_campaign_reprocesada.csv)

## Notas
- La campaña real (data/abl.db) quedó reprocesada: el propietario puede seguir desde las 3 candidatas concretas (copiar misiones de Fase 1 → investigar con Freebuff → pegar respuestas).
- El reloj del ciclo NO arrancó en ningún momento (PRE_CYCLE).
- No se consumió ninguna API de pago; 0 llamadas externas.
- AUTONOMOUS_PRODUCTION sigue bloqueado (production_capability_available=false).

- **Nombre del paquete**: autonomous-business-lab_iteracion-013_2026-08-23.zip.txt

- **Tamaño del paquete**: 6653968 bytes

- **SHA-256 del paquete**: 263e0021ef27b132cdf34136312a37df66554bec03122368a91ff4a7ed40b18a
