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

## Registro de entregas (lo completa `scripts/package_for_review.py`)

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
