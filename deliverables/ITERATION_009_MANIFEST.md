# Manifiesto ITERACIÓN 009 — Comité externo visual con intervención mínima

- **Identificador**: 009
- **Fecha y hora**: 2026-08-23 (UTC)
- **Objetivo**: convertir el comité de contraste en una experiencia **visual** en
  la que la única tarea del propietario es copiar el expediente, pegarlo en
  GPT/Grok/Gemini y pegar la respuesta de vuelta. Todo lo demás lo hace el
  sistema: copiado con token de expediente, importación combinada, síntesis
  automática y **decisión autónoma determinista**. Añade además el **ciclo
  económico inicial** (30 días / 50 USD, vías A/B, prórroga única de 14 días).
- **Estado**: Implementado + probado automáticamente (270 tests) + verificado
  por HTTP (26/26). Sin llamadas reales a modelos en esta iteración.
- **Cómo acerca al primer experimento y a la primera venta**: el propietario ya
  no necesita técnica para usar el comité (5 minutos por revisión); la decisión
  autónoma desbloquea el avance hacia el experimento comercial; y el ciclo
  económico define la primera meta medible: **un pago real confirmado** (vía B)
  o 50 USD confirmados (vía A) — mientras tanto el estado es honestamente
  `NOT_PASSED`.

## Resumen de cambios

- **Copiado del expediente** con token no secreto (`packet_id`, `packet_version`,
  `generated_at`, `content_hash`), determinista e idéntico para los tres
  revisores; solo varía la cabecera de metadatos del revisor.
- **Importación combinada** de un único archivo con secciones
  `# GPT` / `# GROK` / `# GEMINI` / `# HUMAN_NOTE` (se importan las presentes;
  la nota humana va a la cola, nunca como opinión de modelo).
- **Decisión autónoma determinista** (`committee_decision`): combina
  puntuación interna, evidencias, riesgos, presupuesto, recomendaciones
  externas y calidad del expediente; ajusta prioridad/confianza (±5 máx.) y
  NUNCA autoriza producción, gasto, ingresos, ni elimina bloqueadores.
- **Filtro de entrada**: mínimo de 3 grupos de evidencia independientes
  (`review_min_evidence_groups`), además del umbral interno (72) y el máximo
  semanal (3).
- **Estados visuales** por tarjeta y por proveedor (Pendiente/Importada/
  Procesada/Parcial/Inválida/Caducada/Continuó sin revisión) + tiempo restante
  de ventana.
- **Ciclo económico** (30 días / 50 USD): `CycleEvaluator` determinista, vías
  A/B, prórroga única de 14 días persistida en `cycle_state`; `NOT_PASSED`
  honesto sin pago real confirmado; `POST /api/economy/cycle/extend` rechaza
  sin pago real y un intento rechazado no consume el cupo.

## Archivos nuevos

- `app/services/cycle.py` (CycleEvaluator)
- `docs/OWNER_COMMITTEE_UX.md`
- `docs/ECONOMIC_CYCLE.md`
- `tests/test_committee_ux.py` (22 tests)
- `deliverables/ITERATION_009_MANIFEST.md` (este archivo)

## Archivos modificados

- `app/core/config.py` (review_min_evidence_groups, review_packet_version,
  ciclo: cycle_length_days/capital_usd/extension_days/max_extensions)
- `app/models/external_review.py` (REVIEWER_HEADERS, CombinedReviewImportIn)
- `app/repositories/db.py` (tabla `cycle_state`, idempotente)
- `app/services/reviews.py` (token de expediente + copy, importación combinada,
  committee_decision, estados por proveedor, filtro de grupos)
- `app/core/container.py` (cycle)
- `app/api/routes.py` (packet/copy, import-combined, decide, economy/cycle,
  economy/cycle/extend)
- `frontend/{index.html,app.js,styles.css}` (Comité externo visual)
- `README.md`, `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`

## Archivos eliminados

- Ninguno.

## Cambios arquitectónicos

- `CycleEvaluator` como servicio nuevo (estado persistente mínimo en
  `cycle_state`). Sin cambios en el ledger: el ciclo solo LEE el ledger y la
  regla excluye ingresos simulados.

## Cambios en agentes/scoring/seguridad

- Sin cambios en scoring (las opiniones siguen sin tocar la puntuación interna).
- Nueva regla AGENTS.md nº 11 (comité visual, decisión autónoma, ciclo).
- Garantías estructurales en `committee_decision` (producción/gasto/ingreso
  nunca autorizados; bloqueadores intocables).

## Dependencias

- Ninguna añadida ni retirada (stdlib + FastAPI existente).

## Comandos

- Instalar: `pip install -e .`
- Ejecutar: `uvicorn app.main:app`
- Probar: `python3 -m pytest tests/`
- Flujo: panel → Comité externo → copiar → pegar en modelo → pegar respuesta.

## Resultado exacto de las pruebas

- `python3 -m pytest tests/` → **270 passed** (248 previos + 22 nuevos), 1
  warning, 11.3 s.
- `node --check frontend/app.js` → OK.
- **26/26 comprobaciones en vivo por HTTP**: cola con filtro de grupos de
  evidencia, copiado idéntico para GPT/Grok/Gemini, token no secreto sin
  claves, pegado individual, archivo combinado (2/3 secciones + nota humana),
  síntesis con desacuerdo (score sin cambios), decisión autónoma segura,
  ventana restante, continuación neutral, ciclo `NOT_PASSED`, prórroga
  rechazada, producción bloqueada, economía simulada.
- `GET /` (dashboard) → 200 con la sección Comité y el modal combinado.

## Problemas conocidos / limitaciones

- El ciclo económico es honestamente `NOT_PASSED`: no existe aún ejecución
  financiera real (por diseño); cualquier avance exige un pago real verificado.
- Los botones de copiado dependen del portapapeles del navegador (hay fallback
  manual); en entornos sin clipboard API se muestra la descarga .md.

## Riesgos abiertos

- Dependencia de disponibilidad/disposición del propietario para las revisiones
  manuales (mitigada: ausencia neutral, decisión autónoma).
- La concesión de prórroga solo será alcanzable cuando exista una vía de pago
  real (fase futura auditada).

## Deuda técnica

- `committee_decision` no persiste aún el `confidence_delta` en el ledger de
  decisiones (solo en `decision_log`); pendiente de panel de trazabilidad.

## Componentes para revisión del supervisor

- `app/services/reviews.py`: `review_packet_for_copy`, `import_combined_review`,
  `committee_decision`, `_committee_state`, filtro de grupos de evidencia.
- `app/services/cycle.py`: reglas del ciclo y concesión única de prórroga.
- `frontend/app.js`: flujo copiar/pegar/importar/decidir y estados visuales.
- `tests/test_committee_ux.py` (22 casos) y las garantías de no-autorización.

## Próxima acción recomendada

Ejecutar el flujo completo del comité con 2-3 finalistas reales de una campaña
Freebuff, comparar las objeciones del comité frente al Judge solo y medir si la
prioridad resultante mejora la selección. En paralelo, preparar el **primer
experimento comercial manual** (la meta del ciclo: un pago real confirmado para
la vía B). No avanzar a pagos/infraestructura reales hasta que una oportunidad
supere el API Readiness Gate.

- **Nombre del paquete**: autonomous-business-lab_iteracion-009_2026-08-23.zip.txt

- **Tamaño del paquete**: 414022 bytes

- **SHA-256 del paquete**: 0cb0a09d8e39694660911f8d5b267bb88fd0a822c099c68e260eba167f2ae362
