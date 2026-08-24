# Informe de revisión — Iteración 016 (v0.15.0) — 2026-08-24

## 1. Resumen ejecutivo

La instalación real del paquete 013 mostraba un bloqueo incoherente: el sistema
ordenaba "COPIAR MISIÓN PARA FREEBUFF" mientras afirmaba "Sin misiones
planificadas todavía". Se diagnosticó la causa raíz con reproducción completa,
se demostró con datos que el "6" observado eran conceptos NEEDS_REFORMULATION
(no misiones), y se aplicó la corrección mínima: parada contextual honesta del
orquestador, endpoint de misiones trazable, frontend coherente, portada
idempotente y re-planificación determinista tras reformular. 328 pruebas pasan.

## 2. Diagnóstico y causa raíz (definitiva)

Causa TRIPLE, reproducida desde base limpia:

1. **Orquestador** (`_next_step`): al alcanzar RESEARCH_PENDING devolvía
   `next_action="COPIAR MISIÓN PARA FREEBUFF..."` como texto fijo, sin comprobar
   si existían misiones. Con RESEARCH_CANDIDATE=0 no se crea ninguna misión ⇒
   orden imposible.
2. **Endpoint** `/api/orchestrator/runs/{id}/missions`: devolvía lista vacía sin
   motivo cuando la transición RESEARCH_PLANNED no registraba misiones.
3. **Frontend**: `loadOrchestratorMissions` (tarjeta Campaña real) mostraba
   "Sin misiones planificadas todavía." genérico junto a la próxima acción que
   exigía copiar una misión. La vista Investigación era correcta pero el
   conflicto en la tarjeta inducía a error.

Adicionalmente se detectó una brecha de flujo: `/start` avanza automáticamente
hasta RESEARCH_PENDING; completar un Opportunity Brief DESPUÉS de la parada no
replanificaba nunca (advance() devolvía None), dejando las reformulaciones sin
camino hacia la investigación.

## 3. Evidencia del diagnóstico

Reproducción HTTP sobre servidor real con DATABASE_PATH temporal:

- `POST /api/orchestrator/start` → run único, estado RESEARCH_PENDING.
- Conteos reales: 66 conceptos = 51 DIVERSITY_ELIMINATED + 3 COMMODITY_BLOCKED
  + 6 NEEDS_REFORMULATION + 6 RECOMBINATION_INCOHERENT; candidatas 0.

## 4. Significado exacto del número 6

Eran **seis conceptos NEEDS_REFORMULATION**: direcciones abstractas que deben
reformularse a negocio concreto antes de investigar. NO eran 6 misiones ni 6
grupos de investigación. Coincidir con los 6 RECOMBINATION_INCOHERENT alimentó
la confusión. RESEARCH_CANDIDATE=0 ⇒ cero misiones es el comportamiento
CORRECTO (regla iteración 013: nada se investiga sin negocio concreto).

## 5. Estado anterior / 6. Estado corregido

| Aspecto | Antes | Ahora |
|---|---|---|
| Próxima acción sin misiones | "COPIAR MISIÓN PARA FREEBUFF" | "REFORMULAR... (todavía NO hay misión que copiar)" |
| Endpoint de misiones | Lista vacía silenciosa | explanation + status_counts + trazabilidad |
| Tarjeta Campaña real | Mensaje genérico contradictorio | "SIN MISIÓN DISPONIBLE" + explicación del backend |
| Portada con campaña existente | "INICIAR CAMPAÑA REAL" ambiguo | "CONTINUAR CAMPAÑA REAL" idempotente (mismo run) |
| Brief tras la parada | Sin camino (advance=None) | Re-planificación determinista (Caso A) |
| Evidencia sin fragmento | Podía marcarse verified | verified=false obligatorio |

## 7. Comportamiento cuando hay misiones (Caso A)

Brief válido → advance re-ejecuta promote_and_plan_research → 6 misiones Fase 1
(DEMAND_REALITY_CHECK…GENERAL_AI_SUBSTITUTION_CHECK) con mission_id,
concept_id, opportunity_id, título de la candidata y markdown completo;
botón COPIAR MISIÓN PARA FREEBUFF visible; importación exige mission_id.
Verificado por HTTP: count=6, md≈1200–1320 chars por misión.

## 8. Comportamiento sin candidatas investigables (Caso B)

count=0 + explanation ("RESEARCH_CANDIDATE=0: 6 conceptos necesitan
reformulación y 6 recombinaciones son incoherentes") + next_action REFORMULAR.
No se fabrican misiones ni mission_id artificiales; el cuadro de importación no
aparece; no se avanza falsamente a investigación ejecutable.

## 9. Archivos modificados

`app/services/orchestrator.py`, `app/api/routes.py`,
`app/services/discovery.py`, `frontend/app.js`, `frontend/index.html`,
`app/core/config.py`, `tests/test_continuity_016.py` (nuevo),
`tests/test_orchestrator_010.py`, `docs/ITERATION_HISTORY.md`,
`deliverables/ITERATION_016_MANIFEST.md`, este informe.

## 10. Cambios de backend

- Parada contextual con `no_mission_explanation` y `concept_status_counts`.
- Re-planificación post-parada solo si (candidatas ≥1 Y misiones activas =0).
- Misiones: fallback a BD (nunca superseded), markdown, títulos, counts.
- `VERIFIED_REQUIRED_FIELDS += raw_excerpt`; import exige URL+fecha+fragmento.

## 11. Cambios de frontend

Tarjeta honesta, trazabilidad visible, botón de copia condicionado a misión
real, portada CONTINUAR CAMPAÑA REAL (dataset.mode="continue"), versión v0.15.0.

## 12. Cambios de persistencia o migraciones

NINGUNO en esquema (CREATE TABLE intactos). Todo el estado nuevo vive en
transiciones existentes (outputs JSON append-only).

## 13. Cambios de documentación

`docs/ITERATION_HISTORY.md` (entrada 016), manifiesto 016, este informe.

## 14. Pruebas añadidas o modificadas

Nuevas (`tests/test_continuity_016.py`, 14): llegada a RESEARCH_PENDING; caso B
explicado; trazabilidad de misiones vía brief real; re-planificación post-parada
sin duplicar; importación asociada a mission_id (genérico rechazado); verificación
URL/fecha/fragmento (4 casos); referencia anti-evidencia de modelos; contadores =
backend; persistencia tras reinicio; idempotencia de inicio; PRE_CYCLE detenido;
presupuesto 0/simulación; producción bloqueada; suite offline.
Modificada: `test_orchestrator_010.py` (contrato honesto de parada).

## 15. Resultado exacto de pruebas parciales

`python3 -m pytest tests/test_continuity_016.py -q` → **14 passed**
(3 fallos intermedios investigados y corregidos durante el desarrollo: parsing
del test, ruta legítima de candidata, campo verified del caso positivo).
`pytest tests/test_orchestrator_010.py tests/test_full_flow.py tests/test_continuity_016.py`
→ **28 passed**.

## 16. Resultado exacto de la suite completa

Comando: `python3 -m pytest` → **328 passed, 0 failed**, 1 warning
(deprecación httpx/starlette del entorno, externa), ~20 s.

## 17. Verificación visual

Servidor real uvicorn (puerto 8931, DATABASE_PATH=/tmp):
1. GET / → HTTP 200, `Cache-Control: no-store`, data-wawa-version=0.15.0,
   data-iteration=016, botón INICIAR CAMPAÑA REAL presente (sin campaña).
2. POST start ×2 → mismo run (idempotente), RESEARCH_PENDING.
3. Caso B → missions.count=0 + explanation + REFORMULAR.
4. Brief válido → RESEARCH_CANDIDATE → advance → 6 misiones con markdown y
   next_action "COPIAR MISIÓN PARA FREEBUFF".
5. Import sin fragmento → verified=false ("No cumple los criterios mínimos").
6. PRE_CYCLE → status PRE_CYCLE, clock False, started_at null, days_remaining 30.
7. Reinicio del proceso → run/estado/misiones conservados.

## 18. Garantías PRE_CYCLE

started_at=NULL tras todo el flujo; consultar estado no inicia reloj; ninguna
ruta nueva toca cycle_state.

## 19. Comprobación económica

budget.daily.spent=0.0, free_mode=true, simulation_mode=true,
real_money_moved=false (verificado por /api/health y /api/economy/cycle).

## 20. Comprobación de modos de producción

production_capability_available=false; AUTONOMOUS_PRODUCTION inalcanzable;
OpenRouter/OmniRoute sin llamadas; cero conexiones externas; sin cookies; .env
intacto; base de datos real del propietario no borrada ni sustituida (nota
honesta: una comprobación inicial abrió data/abl.db en modo lectura para
/api/health antes de corregir el nombre de la variable; solo creó WAL, sin
escrituras de datos).

## 21. Riesgos pendientes

- El contador de Ideas del badge depende de loadIdeas(); verificado que carga el
  total real, pero conviene confirmarlo en el navegador del propietario.
- Iteración 014 quedó marcada "en curso" sin paquete propio (su funcionalidad
  está incluida y superada por 015/016); pendiente regularizar su fila.

## 22. Decisión de versionado

Iteración 016 (no parche): modifica orquestador, API, contrato de evidencias y
frontend. Numeración verificada contra manifiestos reales 001–015. Versión
0.14.0 → 0.15.0 sincronizada en backend, frontend y health.

## 23. Paquete

`autonomous-business-lab_iteracion-016_2026-08-24.zip.txt` generado con
`scripts/package_for_review.py` y verificado con `scripts/verify_review_package.py`.

## 24. SHA-256 y 25. Resultado de verificación

- Paquete: `deliverables/packages/autonomous-business-lab_iteracion-016_2026-08-24.zip.txt` (6.692.081 bytes, 201 archivos; `data/logs` excluido del empaquetado: los logs privados en runtime —incluidos rotados *.log.N— quedan fuera del paquete).
- **SHA-256 (canónico): `1d32a9f772f76262cb3d4770f7fff3298b7641b5afff6ee21a524f21d6f03d38`**
- SHA-256 (archivo completo, referencia): `9722f0826742e029bb46341fd1833d6deebf2d2ac044aac638343593025fdb59`
- `python3 scripts/verify_review_package.py --path <paquete>` → **RESULTADO: VÁLIDO (15/15 comprobaciones)**: sin path traversal ni rutas absolutas, incluye README/AGENTS/manifiesto 016, sin archivos prohibidos, sin secretos detectables, extracción temporal OK, SHA coincide.

## 26. Próxima acción del propietario

Extraer el paquete 016 siguiendo COMO_ABRIR_WAWA.md, arrancar WAWA y, en la
tarjeta Campaña real: si aparece "REFORMULAR", completar Opportunity Briefs de
las direcciones interesantes hasta obtener candidatas; cuando aparezca
"COPIAR MISIÓN PARA FREEBUFF", copiar la misión, entregarla a Freebuff y pegar
la respuesta en el panel (con mission_id asociado).
