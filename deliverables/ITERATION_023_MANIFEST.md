# Manifiesto ITERACIÓN 023 — Recuperación en vivo del comité

- **Identificador**: 023
- **Fecha**: 2026-08-27 UTC
- **Versión**: v0.22.0
- **Build**: `023-committee-recovery`
- **Estado**: entregado; implementado, probado y paquete verificado 15/15

## Objetivo

Corregir el bloqueo visual de más de 10 minutos en “Sintetizando revisiones…” y garantizar una operación de comité determinista, idempotente, reintentable y sin llamadas LLM.

## Hallazgos

La base persistida del sandbox contiene 0 revisiones externas, 1 entrada de cola para la ganadora de ortodoncia, 0 síntesis iniciales y 3 candidatas. Por tanto, no se afirma que GPT/Grok/Gemini estén importados en la base inspeccionada. La recuperación ejecutada creó una síntesis honesta `NONE`, decisión `MORE_RESEARCH` y una misión específica única; mantuvo `READY_TO_CONNECT_SERVICES`, evidencia intacta, PRE_CYCLE detenido y producción bloqueada.

## Cambios

- Endpoint compuesto `POST /api/reviews/opportunities/{opportunity_id}/synthesize-and-decide`.
- Single-flight `RLock` para importación/síntesis/decisión.
- SQLite `busy_timeout=5000`.
- Reutilización idempotente de síntesis y `operation_id` determinista.
- `MORE_RESEARCH` → una única misión específica; `REJECT` → candidatas alternativas persistidas.
- Frontend con timeout `AbortController` de 20 s, cuatro etapas, doble clic bloqueado, reintento, recuperación tras refresco y `finally` restaurador.
- Versión/assets 0.22.0 / iteración 023.
- 14 tests nuevos de recuperación y sincronización.

## Garantías

- Sin llamadas de proveedor LLM.
- Opiniones nunca son evidencia.
- Evidencia no se modifica.
- No se inicia PRE_CYCLE.
- No se conectan servicios.
- No se autoriza producción ni dinero real.
- No se inventan revisiones, demanda o sustitutas.

## Verificación

- `python3 -m pytest` → 437 passed, 1 warning.
- `node --check frontend/*.js` → OK.
- Endpoints TestClient → GET/POST del comité, command-center y agent-telemetry OK.
- Operación compuesta → 0.06 s en DB temporal; segundo intento reutiliza síntesis y conserva el mismo operation_id.
- Recuperación sobre `data/abl.db` → idempotente; 13 misiones antes/después del segundo intento; evidencia 11 filas sin cambio.

## Archivos clave

`app/api/routes.py`, `app/core/config.py`, `app/core/container.py`, `app/repositories/db.py`, `app/services/reviews.py`, `frontend/candidates.js`, `frontend/index.html`, `frontend/candidates.html`, `frontend/mission-control.html`, `frontend/agents-viz.html`, `tests/test_committee_recovery.py` y tests de sincronización.

## Paquete

- **Nombre**: `autonomous-business-lab_iteracion-023_2026-08-27.zip.txt`
- **Tamaño**: 9316830 bytes
- **SHA-256 canónico**: `1c41e8ffc3d31f7be30563183695d0965cf82bacfef4ad93e7b6f500d78ec224`
- **Verificación**: `scripts/verify_review_package.py --iteration 023` → VÁLIDO **15/15**.

- **Nombre del paquete**: autonomous-business-lab_iteracion-023_2026-08-27.zip.txt

- **Tamaño del paquete**: 9316830 bytes

- **SHA-256 del paquete**: 1c41e8ffc3d31f7be30563183695d0965cf82bacfef4ad93e7b6f500d78ec224
