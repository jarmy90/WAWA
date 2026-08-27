# Historial de iteraciones

> Numeración **consecutiva y no reutilizable**. La última iteración se detecta
> automáticamente escaneando `deliverables/ITERATION_*_MANIFEST.md` (o esta
> tabla) para continuar la numeración.

| Iteración | Fecha | Objetivo | Estado | Paquete | SHA-256 |
|---|---|---|---|---|---|
| 001 | 2026-08-23 | MVP completo del motor de investigación y selección de oportunidades (7 agentes, scoring, dashboard, tests). | entregado | _sin paquete (anterior al workflow)_ | — |
| 002 | 2026-08-23 | Workflow permanente de revisión externa, modos de operación, motor de estados, huevo vivo v1 y scripts de empaquetado. | entregado | autonomous-business-lab_iteracion-002_2026-08-23.zip.txt | 3e4a0ac6341a8887170c8b7966f1a4d46a31932bbe4118bb0f389ed50b6a2af0 |
| 003 | 2026-08-23 | Economía simulada auditada (ledger append-only, idempotencia, reversiones, métricas, reconciliación), PRODUCTION_ARMED, regla de capacidad de producción, panel económico. | entregado | autonomous-business-lab_iteracion-003_2026-08-23.zip.txt | 2e93847f6db4d3425bcd7c1fac3efcc51e9dfef95f3220b0b8192ccc235b7ddc |
| 004 | 2026-08-23 | Business Discovery Engine: campañas de descubrimiento abierto (7 fases), General AI Substitution Test (bloqueo COMMODITY_WRAPPER), Venture Quality Score, diversidad anti-clon, torneo por pares, memoria empresarial y misiones Freebuff-first. | entregado | autonomous-business-lab_iteracion-004_2026-08-23.zip.txt | 9d18063082fec4343a5bc79c876c7aa1b290528fff364f13556f764499b93e5b (canónico) |
| 005 | 2026-08-23 | Comité de contraste para finalistas: revisiones de modelos independientes (expediente idéntico + prompt normalizado, importación TXT/MD con allowlist y anti-inyección, síntesis con etiqueta de falso consenso, no-bloqueo y auto-continuación neutral), Laboratorio de oportunidades en el dashboard. | entregado | autonomous-business-lab_iteracion-005_2026-08-23.zip.txt | 5ec2742ccf8b467149113e826a70d1a1c21dbb882503d2d8d08678bcdedadb70 (canónico) |
| 006 | 2026-08-23 | FREEBUFF-FIRST Campaign Runner: sesiones reanudables de 2-6 h sin APIs (SESSION_PLAN/STATE/OUTPUT/REPORT + NEXT_SESSION), máquina de estados con entregables obligatorios, embudo con límites inmutables, `api_budget_usd=0` estructural, niveles de razonamiento, API Readiness Gate determinista y piloto sintético (0 llamadas). | entregado | autonomous-business-lab_iteracion-006_2026-08-23.zip.txt | 3786626ba76f1758264dae0d41444d376b0c54ad1349016967d67fdadd96db46 (canónico) |
| 007 | 2026-08-23 | OpenRouter para el comité (Opción A): modelo fijo + router gratuito fallback, `llm_call_log` con coste honesto (reported_cost/estimated_cost/cost_source/billing_verified), guardas deterministas (1 revisión por oportunidad, límites diario/mensual, circuit breaker, reintentos acotados) y no-fabricación de revisiones. Verificado en vivo con 1 llamada real (0.0003006 USD, PROVIDER_RESPONSE). | entregado | autonomous-business-lab_iteracion-007_2026-08-23.zip.txt | 563cab6a8350d29ae268f3c90519d6bc3518b45551f68669973a84f28bc69979 (canónico) |
| 008 | 2026-08-23 | Evaluación e integración aislada de OmniRoute: gateway local OpenAI-compatible como proveedor opcional desactivado por defecto, allowlist de conexiones (UNKNOWN => bloqueado en producción), routing por tarea, perfil Docker separado (127.0.0.1:20128), 2º revisor opcional del comité sin fabricación, benchmark A/B con 10 problemas sintéticos y 6 docs de investigación. Arranque real del gateway pendiente (ENOSPC en el sandbox); sin evidencia de modelo "Alpha 0". | entregado | autonomous-business-lab_iteracion-008_2026-08-23.zip.txt | 39db98c953a556bfd5c119f8f095d42760206b955707ea8fb7bf65b74839316e (canónico) |
| 009 | 2026-08-23 | Comité externo visual con intervención mínima: copiar/pegar el expediente en GPT/Grok/Gemini (token no secreto packet_id/version/content_hash, mismo contenido base), importación combinada (# GPT/# GROK/# GEMINI/# HUMAN_NOTE), decisión autónoma determinista (prioridad/confianza ±5, sin autorizar producción/gasto/ingresos), estados visuales por tarjeta y proveedor, filtro de 3 grupos de evidencia independientes, y ciclo económico inicial 30 días / 50 USD (vías A/B, prórroga única de 14 días; NOT_PASSED honesto sin pago real). | entregado | autonomous-business-lab_iteracion-009_2026-08-23.zip.txt | 0cb0a09d8e39694660911f8d5b267bb88fd0a822c099c68e260eba167f2ae362 (canónico) |
| 010 | 2026-08-23 | Cierre end-to-end + PRE_CYCLE + PRIMERA CAMPAÑA REAL 001: orquestador único auditable (descubrimiento → filtros → torneo → investigación → evidencias → reevaluación → finalistas → comité → decisión → plan de experimento → PRE_CYCLE) que avanza solo hasta donde falten datos externos (RESEARCH_PENDING, sin inventar evidencia); corrección crítica: consultar el estado ya no inicia el reloj de 30 días (started_at NULL, /cycle/start con 12 precondiciones, reloj solo con activación deliberada); única fuente cycle_length_days=30 (initial_cycle_days deprecado); exportaciones CSV/JSON/MD/finalistas/zip; scripts start/stop locales (127.0.0.1) + COMO_ABRIR_WAWA.md; CORS restringido; test de escape XSS. | entregado | autonomous-business-lab_iteracion-010_2026-08-23.zip.txt | 6af9ccc8088b126165ed3ff959cfdafeae4e73af3a160845c4cfb576ee7f2fb0 (canónico) |
| 011 | 2026-08-23 | Corrección de entrega del frontend obsoleto: causa raíz identificada (caché heurística del navegador sin Cache-Control + URLs sin versión + repositorio PRIVADO con enlaces RAW 404 + bug de arranque en start_wawa.sh/START_WAWA.bat que dejaba vivo un servidor antiguo). NoCacheStaticFiles (no-store), assets versionados (?v=011), marcador de versión visible con autochequeo vs /api/health (banner si diverge), eliminado el botón demo MQL5, franja de estado siempre visible (PRE_CYCLE + campaña + próxima acción), pestañas con flex-wrap, versión 0.11.0, y prueba de aceptación de 8 pasos superada en carpeta limpia. | entregado | autonomous-business-lab_iteracion-011_2026-08-23.zip.txt | 517c84b0af2501fe78c7cf6e831c21f0408cc00ef2a8ebb98a0ec34cd1b8e01d (canónico) |
| 012 | 2026-08-23 | Corrección EXCLUSIVA de la interfaz entregada (v0.11.1): causa raíz confirmada con navegador real — el layout colapsaba a una columna ≤1100 px con el sidebar primero, dejando toda la navegación bajo el pliegue. Portada hero-first con navegación estática (Inicio/Campaña real/Ideas/Investigación/Comité/Experimento/Economía/Actividad/Configuración), PRE_CYCLE e INICIAR CAMPAÑA REAL visibles sin JS ni scroll, bloque noscript, diagnóstico visible (Backend/Frontend/Iteración/JS/Paquete), franja roja CSS si el init falla, panel antiguo movido a sub-vistas, sin textos MQL5/demo, y aceptación de navegador real (1440/390, clic INICIAR → RESEARCH_PENDING, Ideas 66, descargas CSV/MD/zip, body.innerText) superada sobre el paquete en carpeta limpia. | entregado | autonomous-business-lab_iteracion-012_2026-08-23.zip.txt | d08aecf7990094a71351ec25158cb1b30243af12e4329d782d679e8281e04852 (canónico) |
| 013 | 2026-08-23 | Calidad semántica, estados honestos y reformulación ANTES de investigar (v0.12.0): sustitución de etiquetas ambiguas (passed/promoted/blocked/eliminated/clone) por 15 estados inequívocos en español con significado visible (GENERATED_HYPOTHESIS…EXPERIMENT_READY, incl. NEEDS_REFORMULATION, RECOMBINATION_INCOHERENT, RESEARCH_CANDIDATE, RESEARCH_PENDING, FINALIST); ventajas sin evidencia mostradas como HIPÓTESIS (HYPOTHESIS_DEFENSIBLE_WORKFLOW…); dos puntuaciones separadas — estructural (pre-evidencia) y con evidencia (0 sin evidencia, tope 40 con <3 grupos, real con ≥3); Quality Gate del Opportunity Brief de 19 campos (bloquea 'profesional o pequeña organización' y frases genéricas; sin brief concreto no hay candidata); detector determinista de coherencia semántica (3 frases incoherentes reales de la campaña como casos); reformulaciones concretas (3-5 por familia regulatorio/intermediarios/incertidumbre) + torneo de reformulaciones (máx. 3, 0 válido); misiones PROGRESIVAS (solo 6 de Fase 1 por candidata, nunca las 10); reproceso de la campaña real conservando las 66 ideas y superseding las 30 misiones antiguas (SUPERSEDED_BY_SEMANTIC_QUALITY_GATE); PRE_CYCLE permanece detenido; exportaciones CSV con puntuación estructural/evidencia y motivo; tarjetas de Ideas corregidas (Estado/Qué significa/Filtro/Evidencia/Comprador/Problema/Entrega/Canal/Estructura/Con evidencia/Motivo/Qué falta/Próxima acción). Aceptación real: 66 conceptos reprocesados → 61 reformulación + 5 incoherentes + 3 candidatas concretas seleccionadas + 18 misiones de Fase 1, capturas de navegador y CSV/MD descargados. | entregado | autonomous-business-lab_iteracion-013_2026-08-23.zip.txt | 263e0021ef27b132cdf34136312a37df66554bec03122368a91ff4a7ed40b18a (canónico) |
| 014 | 2026-08-23 | Flujo E2E: selector de misión para importar investigación, badge de Ideas actualizado, versión v0.13.0 sincronizada. | en curso | _pendiente_ | — |
| 016 | 2026-08-24 | Continuidad tras primera instalación real (v0.15.0): parada contextual honesta del orquestador (nunca ordena COPIAR MISIÓN sin misiones; explica RESEARCH_CANDIDATE=0), re-planificación determinista post-parada tras Opportunity Brief válido sin duplicar misiones, endpoint de misiones trazable (mission_id/concept_id/markdown/explanation), tarjeta Campaña real honesta, portada idempotente CONTINUAR CAMPAÑA REAL, raw_excerpt obligatorio para evidencia verificada. Demostrado: el '6' observado eran NEEDS_REFORMULATION. Suite: 328 passed. | entregado | autonomous-business-lab_iteracion-016_2026-08-24.zip.txt | 1d32a9f772f76262cb3d4770f7fff3298b7641b5afff6ee21a524f21d6f03d38 (canónico) |
| 017 | 2026-08-26 | Importación automática de planes de reformulación y paquetes portables (v0.16.0): `apply_reformulation_plan` localiza conceptos LOCALES por título normalizado (+territorio/lente/arquetipo) con coincidencia inequívoca (ambiguo ⇒ rechazo registrado), nunca inserta IDs foráneos, idempotente por contenido de brief; delega Quality Gate + torneo ≤3 + misiones Fase 1 en el orquestador. `resolve_research_package` asocia investigación portable a misiones locales por mapeo estable y delega en import_research (URL+fecha+fragmento). Endpoints API + CLI único + bloque visual en panel. Suite: 337 passed. | entregado | autonomous-business-lab_iteracion-017_2026-08-26.zip.txt | 91d1c229b119d0406c480537aea0fc166f46d42982b56cd73ea0125e10e475d2 (canónico) |

## Iteración 016 — Continuidad tras primera instalación real (v0.15.0) — 2026-08-24

**Contexto**: el propietario instaló el paquete 013 en un ordenador nuevo y observó
RESEARCH_PENDING con "Próxima acción: COPIAR MISIÓN PARA FREEBUFF" y, a la vez,
"Sin misiones planificadas todavía"; además el contador de Ideas mostraba 0 y la
portada seguía ofreciendo INICIAR CAMPAÑA REAL con campaña ya creada.

**Significado exacto del número 6 (demostrado con datos reales)**: de los 66
conceptos: 51 DIVERSITY_ELIMINATED + 3 COMMODITY_BLOCKED + **6 NEEDS_REFORMULATION**
+ 6 RECOMBINATION_INCOHERENT. El "6" eran direcciones abstractas que necesitan
REFORMULACIÓN (no 6 misiones ni 6 candidatas): RESEARCH_CANDIDATE=0 ⇒ 0 misiones es
el comportamiento CORRECTO. El defecto era de interfaz/orquestación, no de datos.

**Causa raíz (triple)**:
1. `_next_step` devolvía next_action fijo "COPIAR MISIÓN PARA FREEBUFF" desde
   RESEARCH_PENDING aunque no existiera ninguna misión (sin explicar por qué).
2. `/api/orchestrator/runs/{id}/missions` devolvía lista vacía sin motivo.
3. `loadOrchestratorMissions` (tarjeta Campaña real) mostraba un mensaje genérico,
   desconectado de la explicación del backend; la vista Investigación era correcta.

**Corrección mínima**: parada contextual del orquestador (con misiones ⇒ COPIAR
MISIÓN; sin ellas ⇒ razón honesta + no_mission_explanation + concept_status_counts +
next_action REFORMULAR); re-planificación determinista post-parada (brief válido sin
misión activa ⇒ promote_and_plan_research; nunca duplica misiones); endpoint de
misiones con fallback a BD, explanation y trazabilidad completa por misión; frontend
con explicación honesta SIN MISIÓN DISPONIBLE, mission_id/concept_id visibles y
botón de copia solo con misión real; portada idempotente (CONTINUAR CAMPAÑA REAL);
raw_excerpt obligatorio para verified=true junto a URL+fecha.

**Verificación**: servidor real aislado (DATABASE_PATH temporal) — start idempotente,
Caso B honesto, brief válido ⇒ 6 misiones Fase 1 copiables, importación sin fragmento
⇒ verified=false, PRE_CYCLE intacto (started_at NULL), reinicio conserva estado.
Suite completa: **328 passed**.

## Registro de entregas (lo completa `scripts/package_for_review.py`)
- **Iteración 16** · paquete: `autonomous-business-lab_iteracion-016_2026-08-24.zip.txt` · SHA-256 (canónico): `1d32a9f772f76262cb3d4770f7fff3298b7641b5afff6ee21a524f21d6f03d38`

- **Iteración 002** · 2026-08-23T09:40:05+00:00 · paquete:
  `autonomous-business-lab_iteracion-002_2026-08-23.zip.txt` · tamaño:
  144746 bytes · SHA-256:
  `3e4a0ac6341a8887170c8b7966f1a4d46a31932bbe4118bb0f389ed50b6a2af0`
- **Iteración 3** · 2026-08-23T10:05:00.020794+00:00 · paquete: `autonomous-business-lab_iteracion-003_2026-08-23.zip.txt` · tamaño: 181458 bytes · SHA-256: `2e93847f6db4d3425bcd7c1fac3efcc51e9dfef95f3220b0b8192ccc235b7ddc`
- **Iteración 4** · 2026-08-23T10:40:24.525956+00:00 · paquete: `autonomous-business-lab_iteracion-004_2026-08-23.zip.txt` · tamaño: 240629 bytes · SHA-256 (canónico): `9d18063082fec4343a5bc79c876c7aa1b290528fff364f13556f764499b93e5b`
- **Iteración 5** · 2026-08-23T11:05:41.963199+00:00 · paquete: `autonomous-business-lab_iteracion-005_2026-08-23.zip.txt` · tamaño: 283882 bytes · SHA-256 (canónico): `f19a63360935d5f317a1dc6d97c655817fbe6873170a33f4f387f95024de6fe4`
- **Iteración 6** · 2026-08-23T11:32:45.941047+00:00 · paquete: `autonomous-business-lab_iteracion-006_2026-08-23.zip.txt` · tamaño: 336834 bytes · SHA-256 (canónico): `cdcf5d5432589d1ab988a2783380466bc080e227dafe4935b06a04685e14d097`
- **Iteración 7** · 2026-08-23T11:58:10.624198+00:00 · paquete: `autonomous-business-lab_iteracion-007_2026-08-23.zip.txt` · tamaño: 357465 bytes · SHA-256 (canónico): `563cab6a8350d29ae268f3c90519d6bc3518b45551f68669973a84f28bc69979`
- **Iteración 8** · 2026-08-23T12:23:13.781881+00:00 · paquete: `autonomous-business-lab_iteracion-008_2026-08-23.zip.txt` · tamaño: 391267 bytes · SHA-256 (canónico): `39db98c953a556bfd5c119f8f095d42760206b955707ea8fb7bf65b74839316e`
- **Iteración 9** · 2026-08-23T12:39:35.185266+00:00 · paquete: `autonomous-business-lab_iteracion-009_2026-08-23.zip.txt` · tamaño: 414022 bytes · SHA-256 (canónico): `0cb0a09d8e39694660911f8d5b267bb88fd0a822c099c68e260eba167f2ae362`


## Trazabilidad del paquete de la iteración 009 (auditoría externa)

El paquete `autonomous-business-lab_iteracion-009_2026-08-23.zip.txt` fue
auditado externamente. Esta sección conserva la trazabilidad completa sin
borrar el historial previo.

### Artefacto anterior (SUPERSEDED)

- Tamaño: **413955 bytes**
- SHA-256 (canónico): `87351f4958825c307704edbba0df949065cfc64d62997369274d9b9e62db7375`
- Estado: **SUPERSEDED**
- Motivo de sustitución: el manifiesto registraba 414024 bytes, pero el
  artefacto recibido medía 414022 bytes. El paquete se regeneró para que el
  manifiesto coincidiera con el artefacto real, y la ITERATION_HISTORY quedó
  sincronizada con el paquete final (misma práctica que en iteraciones 006-008).

### Artefacto final auditado

- Nombre: `autonomous-business-lab_iteracion-009_2026-08-23.zip.txt`
- Tamaño exacto: **414022 bytes**
- SHA-256 (canónico): `0cb0a09d8e39694660911f8d5b267bb88fd0a822c099c68e260eba167f2ae362`
- SHA-256 (binario completo): `9618cba17e16ff4b81289db2401303cc32520a73a63512efbfaed7cb912762da`
- Estado: **AUDITADO**
- Fecha: 2026-08-23
- Commit: `7307e1f` (Iteración 009: comité externo visual con intervención mínima)
- Verificación: 15/15 (`scripts/verify_review_package.py`)
- **Iteración 10** · 2026-08-23T13:17:57.661484+00:00 · paquete: `autonomous-business-lab_iteracion-010_2026-08-23.zip.txt` · tamaño: 453498 bytes · SHA-256 (canónico): `6af9ccc8088b126165ed3ff959cfdafeae4e73af3a160845c4cfb576ee7f2fb0`
- **Iteración 11** · 2026-08-23T13:52:51.667736+00:00 · paquete: `autonomous-business-lab_iteracion-011_2026-08-23.zip.txt` · tamaño: 459020 bytes · SHA-256 (canónico): `517c84b0af2501fe78c7cf6e831c21f0408cc00ef2a8ebb98a0ec34cd1b8e01d`
- **Iteración 12** · 2026-08-23T14:27:02.143303+00:00 · paquete: `autonomous-business-lab_iteracion-012_2026-08-23.zip.txt` · tamaño: 1077638 bytes · SHA-256 (canónico): `d08aecf7990094a71351ec25158cb1b30243af12e4329d782d679e8281e04852`
- **Iteración 13** · 2026-08-23T15:25:09.816481+00:00 · paquete: `autonomous-business-lab_iteracion-013_2026-08-23.zip.txt` · tamaño: 6653840 bytes · SHA-256 (canónico): `658df1dfd7c7d986f807ea6c82ce2ac3ef57059ded87abd874bbe808b45fb460`
- **Iteración 13** · 2026-08-23T15:25:35.651711+00:00 · paquete: `autonomous-business-lab_iteracion-013_2026-08-23.zip.txt` · tamaño: 6653908 bytes · SHA-256 (canónico): `d6064e9a445c9fecebe3a5eaf3ee34069d80da7fbd9cb8eb53ad3cda58d77519`
- **Iteración 13** · 2026-08-23T15:25:45.711480+00:00 · paquete: `autonomous-business-lab_iteracion-013_2026-08-23.zip.txt` · tamaño: 6653968 bytes · SHA-256 (canónico): `263e0021ef27b132cdf34136312a37df66554bec03122368a91ff4a7ed40b18a`

## Iteración 017 — Importación automática de planes y paquetes portables (v0.16.0) — 2026-08-26

- **Servicio**: `app/services/reformulation_import.py` (`apply_reformulation_plan`,
  `resolve_research_package`). Coincidencia inequívoca por título normalizado
  NFKD (reforzada por territorio+lente+arquetipo); los concept_id/opportunity_id/
  mission_id del paquete portable son SOLO trazabilidad y jamás se insertan.
- **Idempotencia**: brief almacenado idéntico ⇒ `YA_APLICADO_IDEMPOTENTE`
  (cualquier estado posterior); distinto ⇒ rechazo honesto sin sobrescribir.
- **Delegación**: tras aplicar, `advance()` ejecuta Quality Gate, torneo (≤3)
  y planificación progresiva Fase 1 con IDs LOCALES; el importador no duplica
  lógica de negocio.
- **Investigación portable**: mapeo estable título+kind+phase+ordinal;
  ambigüedades rechazadas; aplicación vía `import_research` (raw conservado,
  dedupe, verificación URL+fecha+fragmento).
- **Superficie**: `POST /api/orchestrator/reformulation-plan`,
  `POST /api/orchestrator/research-package`, CLI
  `scripts/apply_reformulation_plan.py`, panel "Operación automática"
  (`frontend/ops17.js`).
- **Verificación**: paquete 15/15; suite **337 passed**; flujo offline completo
  reproducido (plan → 12 misiones → paquete → RESEARCH_IMPORTED).

## Iteración 021 — Activación comercial: de Mission Control a READY_TO_CONNECT_SERVICES (v0.20.0) — 2026-08-26

- **Estado real recuperado**: 3 candidatas REALES de la campaña (no las 3 del
  enunciado): Benchmark de tarifas de ortodoncia (torneo 77.5), Benchmark de
  honorarios de gestorías (72.5) y Benchmark de costes de placas solares
  (72.5), todas `RESEARCH_PENDING` con 0 evidencia verificada. «Cuaderno de
  cuotas» y «modelo 232» NO existen en el universo de la campaña (75
  conceptos: 67 NEEDS_REFORMULATION + 5 RECOMBINATION_INCOHERENT + 3
  RESEARCH_PENDING).
- **Investigación Fase 1 REAL importada**: 18 misiones (6 por candidata) con
  31 evidencias verificadas (URL + fecha 2026-08-26 + fragmento), fuentes
  primarias (tarifarios de clínicas/aseguradoras, gestorías online, asociación
  UNEF, registros oficiales de colegios), competidores y buyer_confirmed como
  HIPÓTESIS. `evidence_backed_venture_score` sube de 0 a 59.14 en las 3 con 7
  grupos independientes (tope de score 100).
- **Ganadora determinista**: Benchmark anónimo de tarifas de ortodoncia
  (única con `low_launch_cost=2/2` y `concierge_delivery=2/2` en el torneo
  018; 11 evidencias, 7 grupos). Decisión `approved` (experimento SMALL de 30
  días), registrada en `decision_log`.
- **READY_TO_CONNECT_SERVICES** alcanzado honestamente: candidata activa,
  brief válido, Quality Gate, decisión, experimento, oferta/precio (60 EUR
  hipótesis), comprador, canal, métrica de éxito, condición de cierre,
  presupuesto (0 EUR reales), 18 misiones importadas, sin deuda/bloqueadores.
  Producción bloqueada por diseño; condiciones `services_connected=false`,
  `owner_authorized=false`.
- **Paquete de lanzamiento preparado (no conectado)**: `product/` (landing
  responsive, contrato de checkout Stripe, plantillas de email, contrato de
  analytics, términos/privacidad adaptables, checklist de credenciales).
- **Panel**: secciones «Candidata ganadora», «CONECTAR SERVICIOS» (6 servicios
  con estado MISSING/CONNECTED, sin secretos) y «AUTORIZAR CICLO AUTÓNOMO
  · 30 DÍAS» (mandato completo, `PENDING_OWNER_AUTHORIZATION`).
- **Trazabilidad**: `OpportunityRepository.get_by_concept` (concepto→
  oportunidad por título normalizado + campaña) y
  `DiscoveryRepository.update_mission_target` (`opportunity_id` en target).
- **Verificación**: suite **393 passed** (387 + 6 nuevos); `node --check` OK;
  servidor real: rutas 200 y readiness confirmado; paquete verificado;
  versión v0.20.0 / build 021-commercial-activation.

## Iteración 018 — OX Alpha Grand Intelligence Sprint (v0.17.0) — 2026-08-26

- **OX Alpha honesto**: verificación real de la puerta (B2): sin slug
  verificado contra el catálogo y con `OMNIROUTE_ENABLED=false` ⇒ identidad
  `OX_ALPHA_UNVERIFIED` (nunca se inventa el slug; `auto` no cuenta).
  Benchmark reproducible (B3): `scripts/benchmark_ox_alpha.py` con rúbrica
  determinista → veredicto `OX_ALPHA_UNVERIFIED` (no se puntúa sin identidad).
- **Super-torneo (B4-B7)**: `app/scoring/super_tournament.py` (20 criterios,
  sin LLM, sin timestamps) + servicio con `decision_log` append-only. Brief
  completo obligatorio, deduplicación por título normalizado (defecto real
  corregido: el mismo negocio ganaba 3 veces), máx. 3 ganadoras, 0 válido.
  Resultado local: **3 candidatas** (benchmarks de tarifas para clínicas
  dentales / gestorías / placas solares) con `is_not_evidence=true` y
  `proven_demand=0`.
- **Plan de investigación (B8)**: `scripts/run_super_tournament.py` genera
  `deliverables/operacion_super_torneo_2026-08-26/` (resultado + plan portable
  con 6 misiones Fase 1 por candidata: consultas ES/EN, fuentes primarias,
  contradicciones, kill conditions). Investigación web inicial real guardada
  como PROVISIONAL (URL+fecha+fragmento), nunca evidencia en BD.
- **Autonomous Launch (B10)**: `docs/AUTONOMOUS_LAUNCH.md` con estados
  `READY_TO_CONNECT_SERVICES` / `READY_TO_LAUNCH` (bloqueado sin autorización
  única); readiness determinista en `/api/command-center`.
- **Centro de mando (B11)**: `app/services/command_center.py` +
  `GET /api/command-center` + `frontend/ops18.js` (panel cyberpunk con
  código de color y etiquetas REAL/SIMULADO/HIPÓTESIS/MODELO/DESCONOCIDO).
- **Herramientas (B6)**: `docs/TOOL_ANALYSIS_018.md` (Agent Reach `UNKNOWN`,
  Reddit/Stripe `BENCHMARK_FIRST`, n8n `REJECT`, SQLite backups/observabilidad
  `INTEGRATE_NOW`).
- **Verificación**: suite **367 passed** (337 + 30 nuevos); `node --check`
  OK en app.js/ops17.js/ops18.js; versión v0.17.0 / build 018-ox-alpha-sprint;
  PRE_CYCLE detenido; gasto real 0; producción bloqueada por capacidad.

## Iteración 015 — Ventana prioritaria OX Alpha (v0.14.0) — 2026-08-23

- Puerta determinista `app/core/ox_alpha.py`: identidad OX_ALPHA_UNVERIFIED hasta que el propietario verifique el slug real contra el catálogo de OmniRoute; la ventana expira sola el 2026-08-27; límite diario y recorte de entrada.
- Servicio `app/services/deep_reasoning.py`: tareas reformulation / coherence / red_team / variation_comparison con registro honesto por llamada en llm_call_log, ausencia NEUTRAL ante fallo (nunca mock silencioso ni salida sintética como OX Alpha).
- La salida del modelo NUNCA es evidencia: no toca proven_demand, grupos de evidencia, finalistas ni PRE_CYCLE.
- API: GET /api/oxalpha/status · POST /api/oxalpha/catalog-check · POST /api/oxalpha/task.
- Docs: docs/OX_ALPHA_WINDOW.md + env.example (OX_ALPHA_*). Benchmark A/B/C/D obligatorio antes de preferir OX Alpha.
- 14 tests nuevos offline → total **314 passed**.
- **Iteración 16** · 2026-08-24T16:33:27.296509+00:00 · paquete: `autonomous-business-lab_iteracion-016_2026-08-24.zip.txt` · tamaño: 6804465 bytes · SHA-256 (canónico): `1d32a9f772f76262cb3d4770f7fff3298b7641b5afff6ee21a524f21d6f03d38`
- **Iteración 16** · 2026-08-24T16:43:01.840024+00:00 · paquete: `autonomous-business-lab_iteracion-016_2026-08-24.zip.txt` · tamaño: 6692081 bytes · SHA-256 (canónico): `1d32a9f772f76262cb3d4770f7fff3298b7641b5afff6ee21a524f21d6f03d38`
- **Iteración 17** · 2026-08-26T10:28:29.165722+00:00 · paquete: `autonomous-business-lab_iteracion-017_2026-08-26.zip.txt` · tamaño: 6764871 bytes · SHA-256 (canónico): `91d1c229b119d0406c480537aea0fc166f46d42982b56cd73ea0125e10e475d2`
- **Iteración 18** · 2026-08-26T14:37:16.598823+00:00 · paquete: `autonomous-business-lab_iteracion-018_2026-08-26.zip.txt` · tamaño: 6824166 bytes · SHA-256 (canónico): `d44dccbd229895067b6ba508c7be46613a8cbf6f7d1f03f98298317fffd8388e`
- **Iteración 19** · 2026-08-26T18:19:12.180563+00:00 · paquete: `autonomous-business-lab_iteracion-019_2026-08-26.zip.txt` · tamaño: 6834827 bytes · SHA-256 (canónico): `431dfafc4e40c8ab5729e887fc22fe1d433a8bd23bdbda9f5dc6304fdebc9818`
- **Iteración 20** · 2026-08-26T18:31:01.537951+00:00 · paquete: `autonomous-business-lab_iteracion-020_2026-08-26.zip.txt` · tamaño: 6879637 bytes · SHA-256 (canónico): `76dfb286bfb78c9d61571b2f609c8c39dfc1133d8ed56ed9d64649210db687f2`
- **Iteración 21** · 2026-08-26T20:06:50.376666+00:00 · paquete: `autonomous-business-lab_iteracion-021_2026-08-26.zip.txt` · tamaño: 6917671 bytes · SHA-256 (canónico): `44fad77ae2404c69e4015a72837a528e0ddff6ce950b59bf0c7ca681d24ad560`

## Iteración 022 — One-Click Owner Activation (v0.21.0) — 2026-08-26

- **Modo demo corregido (causa del demo persistente)**: el estado demo era
  volátil pero la vista lo volvía a activar al recargar por una lectura
  temprana del parámetro `?demo=1`; ahora el estado vive SOLO en memoria,
  `?demo=1` se elimina de la URL en la misma carga (refrescar/reiniciar nunca
  reactiva demo), se limpian claves demo de localStorage/sessionStorage, el
  botón indica `ACTIVAR DEMO` / `SALIR DE DEMO` según el estado real y los
  datos demo y reales nunca se mezclan (`data_nature=DEMO` vs `REAL`).
  Smoke headless `scripts/demo_state_smoke.js` (6 casos) + verificación en
  navegador real: clic en SALIR DE DEMO deja la URL sin `?demo`.
- **Causa del error PowerShell**: se ejecutó `.venv\Scripts\python.exe …`
  desde `C:\Users\j` (fuera de la carpeta de WAWA). `START_WAWA.bat` ahora
  hace `cd /d "%~dp0"`, crea/reutiliza el `.venv` con rutas entre comillas
  (espacios OK) y es el único punto de entrada: doble clic → 7 pasos
  `[1/7]…[7/7]` → bootstrap → navegador. Sin comandos manuales.
- **CommercialBootstrapService** (`app/services/commercial_bootstrap.py`):
  convierte `activate/readiness_021` en servicio interno idempotente y
  transaccional con checkpoints append-only. Detecta instalación limpia /
  parcial / FAILED recuperable, materializa las 3 candidatas del paquete
  portable en la campaña LOCAL por mapeo estable (título normalizado; NUNCA
  inserta IDs foráneos), importa 18 misiones y 31 evidencias verificadas sin
  duplicar, recalcula puntuaciones (7 grupos independientes), selecciona la
  ganadora determinista, crea el experimento, encola el comité y deja
  `READY_TO_CONNECT_SERVICES`. Deja PRE_CYCLE detenido, gasto real 0 y
  producción bloqueada. Cada paso en `decision_log`. Reanudable tras corte.
- **Activos integrados** `resources/bootstrap/commercial_021/`: manifiesto
  inmutable por versión + investigación portable + tarjetas de candidatas,
  con checksum SHA-256 verificado, sin secretos/SQLite/logs,
  `buyer_confirmed` como HIPÓTESIS.
- **Panel**: ruta `/candidates` (3 tarjetas con puntuación estructural/con
  evidencia, evidencias, grupos, comprador, problema, oferta, precio
  hipótesis, canal, alternativas, fuentes, contradicciones, riesgos, kill
  condition; la ganadora muestra `GANADORA DETERMINISTA PARA EXPERIMENTO`,
  nunca demanda validada) + comité directo (COPIAR GPT/GROK/GEMINI,
  DESCARGAR EXPEDIENTE, PEGAR RESPUESTA, IMPORTAR COMBINADO, wizard
  PASO 1-2-3 con estados pendiente/importado/válido) + botón
  `REPARAR Y CONTINUAR AUTOMÁTICAMENTE` con `VER DIAGNÓSTICO` (solo si
  FAILED/falta activación) + asistente `CONECTAR SERVICIOS`
  (`/api/services/status|save|check`; estado CONNECTED/PARTIAL/INVALID/
  MISSING + últimos 4; secretos fuera de Git, nunca por API/logs/paquetes;
  GitHub permanece CONNECTED).
- **Verificación visual real**: Playwright/Chromium temporal (fuera del
  paquete) → 9 capturas PNG en `deliverables/iteracion_022_capturas/`
  (inicio, candidatas, tarjeta ganadora, wizard, Mission Control sin demo /
  con demo / tras salir de demo, CONECTAR SERVICIOS, móvil).
- **Pruebas**: suite **423 passed** (393 + 30 nuevos); `node --check` OK;
  smoke bootstrap end-to-end en instalación limpia y sobre la base real 021
  (recuperación idempotente: applied, sin duplicados).
- Versión v0.21.0 / build 022-one-click-activation.
- **Iteración 22** · 2026-08-26T21:41:48.109087+00:00 · paquete: `autonomous-business-lab_iteracion-022_2026-08-26.zip.txt` · tamaño: 9303052 bytes · SHA-256 (canónico): `999fdd5c2f3c70d95d4728d19ddb8c65f31fb9df147afcfc6e98b978171f71b1`
- **Iteración 23** · 2026-08-27 · paquete: `autonomous-business-lab_iteracion-023_2026-08-27.zip.txt` · tamaño: 9316830 bytes · SHA-256 (canónico): `1c41e8ffc3d31f7be30563183695d0965cf82bacfef4ad93e7b6f500d78ec224`
- **Iteración 24** · 2026-08-27T15:37:10.986193+00:00 · paquete: `autonomous-business-lab_iteracion-024_2026-08-27.zip.txt` · tamaño: 9348848 bytes · SHA-256 (canónico): `b43e8d6a118b575119f96ddf7601002a5e8c92b8b74f93a522aca20dfb99bc4d`
