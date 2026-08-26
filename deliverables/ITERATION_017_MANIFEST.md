# Manifiesto ITERATION 017 — Importación automática de planes de reformulación y paquetes portables

- **Identificador**: 017
- **Fecha y hora**: 2026-08-26 (UTC)
- **Objetivo**: completar el flujo end-to-end de la macrooperación
  "paquete de reformulación → aplicación local automatizada → candidatas
  locales → misiones locales → investigación real → resultados importables":
  un mecanismo que aplica `reformulaciones_briefs.json` sobre la campaña REAL
  local y asocia paquetes de investigación portables a misiones LOCALES,
  sin insertar nunca identificadores foráneos y sin rellenar formularios a mano.
- **Estado**: entregado

## Resumen de cambios

- **Implementado**: servicio `app/services/reformulation_import.py` con dos
  operaciones públicas — `apply_reformulation_plan` (localiza conceptos
  LOCALES por título normalizado, reforzado por territorio+lente+arquetipo;
  exige coincidencia inequívoca; Quality Gate + torneo ≤3 + misiones Fase 1
  con IDs locales; idempotente) y `resolve_research_package` (mapeo estable
  título+kind+phase+ordinal contra misiones locales; ambigüedades rechazadas;
  delega en `import_research`).
- **Implementado**: endpoints `POST /api/orchestrator/reformulation-plan` y
  `POST /api/orchestrator/research-package` (envolvente honesta
  `real_money_moved=false`), CLI `scripts/apply_reformulation_plan.py`
  (preview/apply/import-package) y bloque visual "Operación automática" en el
  panel (`frontend/index.html` + `frontend/ops17.js`).
- **Probado automáticamente**: 337 tests (328 previos + 9 nuevos en
  `tests/test_reformulation_import_017.py`), 100 % offline.
- **Verificado manualmente**: sintaxis JS (`node --check`) y suite completa.
- **Simulado**: nada nuevo; los briefs importados siguen siendo HIPÓTESIS.
- **Pendiente**: ejecutar el plan real del propietario (0 € autorizados) e
  investigar las misiones generadas; ninguna evidencia verificada todavía.

## Archivos nuevos

- `app/services/reformulation_import.py`
- `scripts/apply_reformulation_plan.py`
- `frontend/ops17.js`
- `tests/test_reformulation_import_017.py`
- `deliverables/ITERATION_017_MANIFEST.md` (este archivo)
- `deliverables/ITERATION_017_REPORT.md`

## Archivos modificados

- `app/api/routes.py` (2 endpoints nuevos)
- `app/core/config.py` (versión 0.16.0)
- `frontend/index.html` (bloque Operación automática + marcadores v0.16.0/iteración 017)
- `frontend/app.js` (marcador de iteración)
- `docs/ITERATION_HISTORY.md`

## Archivos eliminados

Ninguno.

## Decisiones técnicas

- **IDs foráneos jamás se insertan**: los `concept_id` del plan son solo
  trazabilidad; la localización es por título normalizado (NFKD, sin acentos,
  espacios colapsados) y refuerzo territorio+lente+arquetipo.
- **Coincidencia inequívoca obligatoria**: 0 o ≥2 coincidencias ⇒ rechazo
  registrado; nunca aplicación dudosa ni IDs inventados.
- **Idempotencia por contenido**: si el concepto ya tiene EXACTAMENTE el mismo
  Opportunity Brief (en cualquier estado posterior) ⇒ `YA_APLICADO_IDEMPOTENTE`;
  si tiene uno distinto ⇒ rechazo honesto (sin sobrescritura silenciosa).
- **El orquestador manda**: tras aplicar, `advance()` ejecuta Quality Gate,
  torneo (≤3) y planificación progresiva de misiones Fase 1 con IDs LOCALES;
  el importador no duplica lógica de negocio.
- **Mapeo estable para investigación**: título normalizado + mission_kind +
  phase + ordinal (nunca mission_id foráneo); la aplicación delega en
  `import_research`, que conserva raw, deduplica y solo verifica con
  URL+fecha+fragmento.

## Cambios

- **Arquitectura**: capa de importación portable como módulo interno de
  servicios (sin workers ni microservicios nuevos).
- **Agentes/prompts**: sin cambios.
- **Scoring y reglas de decisión**: sin cambios (Quality Gate y torneo intactos;
  puntuación con evidencia sigue en 0 sin fuentes verificadas).
- **Seguridad**: validación Pydantic `extra="forbid"` en los payloads; los
  archivos subidos se tratan como datos no confiables; ninguna clave nueva.
- **Presupuesto**: sin cambios; gasto autorizado 0 €; PRE_CYCLE detenido.
- **Modelos de datos**: sin cambios de esquema (usa tablas existentes).
- **Dependencias**: ninguna añadida ni retirada.

## Comandos

```bash
# Vista previa / aplicación del plan sobre la campaña REAL local
python3 scripts/apply_reformulation_plan.py --file reformulaciones_briefs.json --preview
python3 scripts/apply_reformulation_plan.py --file reformulaciones_briefs.json

# Importación en lote de un paquete de investigación portable
python3 scripts/apply_reformulation_plan.py --import-package research_package.json            # vista previa
python3 scripts/apply_reformulation_plan.py --import-package research_package.json --apply-package
```

## Pruebas

- **Resultado exacto**: `337 passed, 1 warning in 24.36s`
- **Comandos usados**:
  - `python3 -m pytest tests/test_reformulation_import_017.py -q` → `9 passed`
  - `python3 -m pytest` → `337 passed`
  - `node --check frontend/app.js && node --check frontend/ops17.js` → OK
- **Comprobaciones manuales**: endpoints probados vía TestClient
  (`/api/orchestrator/reformulation-plan`, `/api/orchestrator/research-package`);
  flujo completo campaña → plan → 12 misiones Fase 1 (2 candidatas × 6) →
  importación de paquete → RESEARCH_IMPORTED reproducido offline.

## Problemas conocidos / limitaciones / riesgos

- **Problemas conocidos**: ninguno abierto de esta iteración.
- **Limitaciones**: la localización por título requiere que el JSON portable
  conserve el título original normalizado (los títulos renombrados a mano no
  coinciden: se rechazan y quedan trazados).
- **Riesgos abiertos**: el propietario debe ejecutar las misiones reales;
  sin evidencia URL+fecha+fragmento la puntuación con evidencia permanece en 0.
- **Deuda técnica**: el mapeo estable ignora ordinal>1 (Fases 2+ futuras).

## Revisión externa

- **Elementos que debe supervisar el revisor**:
  - `_match_concept` (coincidencia inequívoca y rechazo de ambigüedades).
  - Idempotencia por contenido y rechazo ante brief distinto.
  - `resolve_research_package` (mapeo estable, delegación en `import_research`).
  - Que ningún identificador foráneo alcanza la base local (tests dedicados).
- **Próxima acción recomendada**: ejecutar
  `python3 scripts/apply_reformulation_plan.py --file reformulaciones_briefs.json --preview`
  sobre la instalación del propietario, revisar las coincidencias y aplicar.

## Nombre del paquete

autonomous-business-lab_iteracion-017_2026-08-26.zip.txt

- **Tamaño del paquete**: 6764871 bytes
- **SHA-256 del paquete**: 91d1c229b119d0406c480537aea0fc166f46d42982b56cd73ea0125e10e475d2

- **Nombre del paquete**: autonomous-business-lab_iteracion-017_2026-08-26.zip.txt
