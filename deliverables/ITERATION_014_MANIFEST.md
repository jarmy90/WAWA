# MANIFIESTO ITERACIÓN 014 — FLUJO E2E: INVESTIGACIÓN SELECCIONABLE, BADGES HONESTOS Y VERSIÓN v0.13.0 (v0.13.0)

- **Iteración**: 014 (detectada automáticamente: max(manifiestos)=013 → siguiente=014)
- **Versión**: 0.13.0
- **Fecha**: 2026-08-23
- **Estado**: COMPLETADA — 300 tests pasan, frontend mejorado
- **Objetivo**: mejorar la experiencia del flujo end-to-end de investigación a decisión: selector de misión para importar respuestas, badge de ideas actualizado, y versión consistente en todo el stack.

## Problema que corrige

1. La importación de investigación siempre asociaba la respuesta a la primera misión pendiente, sin permitir seleccionar a qué misión corresponde la respuesta.
2. El badge de Ideas no mostraba el conteo real de conceptos al cargar la vista.
3. La versión del frontend (v0.12.0) no estaba sincronizada con la versión del backend.

## Cambios implementados

### 1. Selector de misión en la importación de investigación
En la vista de Campaña real, ahora aparece un `<select>` con todas las misiones pendientes. El propietario puede elegir a qué misión corresponde la respuesta que pega, en lugar de asumir siempre la primera. La opción por defecto sigue siendo "Primera misión pendiente (automático)".

### 2. Badge de Ideas actualizado al cargar
Al cargar la vista de Ideas, el badge junto al enlace "Ideas" en la navegación se actualiza con el número total de conceptos de la campaña, no solo con las filtradas.

### 3. Sincronización de versión a v0.13.0
- `app/core/config.py`: version = "0.13.0"
- `frontend/index.html`: data-wawa-version="0.13.0", data-iteration="014", data-build="014-e2e-flow"
- Chip de versión y diagnóstico actualizados

### 4. Refresco automático del selector tras importar
Después de importar una respuesta de investigación, el selector de misiones se recarga automáticamente para reflejar las misiones restantes.

## Archivos modificados
- `app/core/config.py` (version bump a 0.13.0)
- `frontend/index.html` (versión, iteración, build, chip, diagnóstico)
- `frontend/app.js` (selector de misión en importación, badge de ideas, refresco post-import)

## Resultado de pruebas
- `python3 -m pytest tests/` → **300 passed**, 1 warning.
- Verificación de versión: Settings().version == "0.13.0" ✓

## Notas
- El flujo end-to-end completo (descubrimiento → filtros → torneo → investigación → evidencias → reevaluación → finalistas → comité → decisión → experimento → PRE_CYCLE) sigue el mismo orquestador de iteración 010-013.
- El selector de misión es el primer paso para hacer la importación de investigación más precisa.
- No se consumió ninguna API de pago; 0 llamadas externas.
- AUTONOMOUS_PRODUCTION sigue bloqueado (production_capability_available=false).
- PRE_CYCLE permanece detenido (reloj no arranca solo).

- **Nombre del paquete**: pendiente de generar
