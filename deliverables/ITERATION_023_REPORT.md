# Informe de iteración 023 — Recuperación en vivo del comité (v0.22.0)

1. **Número de iteración**: 023.
2. **Objetivo**: eliminar el estado visual indefinido “Sintetizando revisiones…” y hacer idempotente, reintentable y observable la síntesis/decisión del comité.
3. **Estado final**: implementado, probado offline y listo para revisión.
4. **Inspección persistida real**: `data/abl.db` contiene 0 revisiones externas en el sandbox, 1 entrada de cola para la ganadora `c1dfd7d527904468997785f8ba18342c`, sin síntesis previa; 3 candidatas persistidas; la ganadora tiene 11 evidencias verificadas en esta base.
5. **GPT**: ausente en la base persistida inspeccionada (`external_reviews`: 0 filas).
6. **Grok**: ausente en la base persistida inspeccionada (`external_reviews`: 0 filas).
7. **Gemini**: ausente en la base persistida inspeccionada (`external_reviews`: 0 filas).
8. **Síntesis**: creada de forma determinista sobre el estado real: 0 revisiones válidas, consenso `NONE`; se persiste en `review_syntheses`.
9. **Decisión**: `MORE_RESEARCH`, por ausencia neutral y ventana de revisión caducada; no se fabrica aprobación.
10. **Candidata ganadora**: Benchmark anónimo de tarifas de ortodoncia; permanece como ganadora determinista para experimento, sin demanda validada.
11. **Riesgos repetidos**: no hay riesgos repetidos porque no existen revisiones importadas en esta base.
12. **Evidencia ausente**: no hay evidencia de opinión externa persistida; la siguiente misión solicita comprobar demanda real/pago sin inventar datos.
13. **Bloqueadores**: falta de revisiones externas no es bloqueo crítico; sí impide declarar consenso. Producción continúa bloqueada por capacidad.
14. **Readiness**: `READY_TO_CONNECT_SERVICES`; no se conectaron credenciales ni se inició el ciclo.
15. **Causa raíz**: frontend ejecutaba dos POST secuenciales sin timeout, sin guard de doble clic y sin `finally`; además, la conexión SQLite compartida no tenía `busy_timeout` ni serialización de operaciones del comité. Cualquier fallo de red/HTTP/transacción dejaba el mensaje indefinidamente.
16. **Corrección backend**: nuevo `POST /api/reviews/opportunities/{opportunity_id}/synthesize-and-decide`, con contrato único `{operation_id,status,synthesis,decision,followup}`; no llama modelos, no cambia evidencia, no autoriza producción y reutiliza síntesis persistida cuando el conjunto de revisiones no cambió.
17. **Corrección de concurrencia**: single-flight `RLock` para importar, sintetizar y decidir; `PRAGMA busy_timeout=5000` para colisiones SQLite externas; todos los accesos son acotados y reintentables.
18. **Corrección de seguimiento**: `MORE_RESEARCH` crea como máximo una misión `DEMAND_REALITY_CHECK` específica; `REJECT` señala candidatas alternativas persistidas sin inventar sustitutas; experimentos habilitan visualmente CONECTAR SERVICIOS sin conectar nada.
19. **Corrección frontend**: `AbortController` con timeout de 20 segundos, cuatro etapas visibles, detección de HTTP/error de contrato, protección contra doble clic, reintento, restauración de botones en `finally` y mensaje sanitizado.
20. **Recuperación tras refresco**: `sessionStorage` marca temporalmente la operación y la tarjeta recupera la síntesis persistida; la llamada compuesta devuelve el mismo `operation_id` en reintentos.
21. **Pruebas nuevas**: 14 tests en `tests/test_committee_recovery.py`: 3/2/1/0 revisiones, invalidación, idempotencia, regeneración al cambiar revisiones, refresco, concurrencia, errores, garantías y sincronización frontend/backend.
22. **Pruebas completas**: `python3 -m pytest` → **437 passed**, 1 warning.
23. **JavaScript**: `node --check` sobre todos los `frontend/*.js` → OK.
24. **Seguridad**: errores al cliente siguen sanitizados; secretos nunca se devuelven; las opiniones no se convierten en evidencia; no se altera ledger, presupuesto, ciclo ni producción.
25. **Versionado**: backend `0.22.0`; assets HTML actualizados a iteración `023`, build `023-committee-recovery`; tests de sincronización actualizados.
26. **Archivos modificados**: `app/api/routes.py`, `app/core/config.py`, `app/core/container.py`, `app/repositories/db.py`, `app/services/reviews.py`, `frontend/candidates.js`, cuatro HTML del frontend y tests de sincronización.
27. **Archivo nuevo**: `tests/test_committee_recovery.py`; este informe y el manifiesto completan la entrega documental.
28. **Próxima acción**: revisar/importar respuestas reales de GPT, Grok y Gemini en `/candidates`; pulsar una vez `PASO 3 · SINTETIZAR Y DECIDIR`. La operación ahora finaliza o muestra error/reintento, nunca queda esperando indefinidamente.
