# Seguridad del comité de contraste

> Estado: **implementado** (iteración 005) · Las respuestas importadas son
> **datos no confiables**.

## Modelo de amenaza

Las evidencias externas y las respuestas importadas pueden contener intentos
de **prompt injection** (instrucciones maliciosas dentro del contenido) o
texto arbitrario. El sistema nunca debe:

- Ejecutar código del contenido importado.
- Modificar sus propias instrucciones de sistema.
- Activar herramientas.
- Cambiar presupuestos o modos operativos.
- Autorizar producción.
- Mover fondos.
- Publicar contenido.
- Sobrescribir archivos fuera del área permitida.

## Controles implementados

1. **Guardado como datos**: `raw_response` se conserva verbatim; el parsing
   solo lee claves de una allowlist (`PARSED_FIELDS`). Cualquier otra clave se
   ignora como texto libre.
2. **Límites de tamaño**: `review_max_file_bytes` (200 KB por defecto) →
   `PayloadTooLargeError`.
3. **Lista blanca de extensiones**: `.txt`, `.md`, `.markdown` → otras
   extensiones se rechazan (`ValidationError`).
4. **Detección de duplicados**: SHA-256 del contenido; la misma respuesta para
   la misma oportunidad devuelve 409 con el id de la revisión existente.
5. **Sanitización**: se eliminan caracteres de control (excepto saltos de
   línea) y se acotan los campos a 5 000 caracteres.
6. **Detección de inyección**: frases típicas ("ignore previous instructions",
   "override your instructions", "system prompt", "you are now"...)
   se **señalan** en `parse_errors`/warnings, pero el contenido nunca se
   interpreta como instrucción. Los tests verifican que tras importar una
   respuesta con inyección, el modo de operación, el presupuesto y el ledger
   permanecen intactos.
7. **Hash de archivo**: `file_hash` se almacena por revisión (auditoría).
8. **Asociación por identificadores**: cada revisión se vincula a su
   `opportunity_id` (validado como UUID de 32 hex; sin path traversal).
9. **Sandbox lógico**: el servicio de revisiones no tiene acceso a las APIs de
   modo/budget/economía; sus funciones solo escriben en `external_reviews`,
   `review_queue`, `external_reviews` y `decision_log` (append-only).
10. **Conservación de errores de parsing**: `parse_errors` se guarda y se
    muestra; nunca se descarta silenciosamente.

## Lo que una revisión NO puede hacer

Verificado por tests:

- Autorizar `AUTONOMOUS_PRODUCTION` (el modo queda en `development_and_review`;
  `production_capability_available` sigue `false`).
- Modificar el presupuesto diario ni crear asientos de ledger.
- Convertir estimaciones en ingresos.
- Aprobar actividades bloqueadas.
- Eliminar evidencias contrarias.
