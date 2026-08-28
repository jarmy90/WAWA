# Manifiesto de iteración 027

- **Número**: 027
- **Fecha**: 2026-08-28
- **Objetivo**: reparar integridad, versionar evaluaciones, preparar runtime local y mantener la oportunidad dental protegida.
- **Estado**: IMPLEMENTADO Y PROBADO OFFLINE; OmniRoute local queda PENDING_LOCAL_VALIDATION.

## Cambios

- Evaluaciones históricas append-only con `evaluation_id`, `version`, `supersedes_id`, `integrity_status`, provenance y modo de ejecución.
- La evaluación dental contaminada permanece `QUARANTINED`; no se restaura 59,14.
- El pipeline ya no ejecuta DELETE de evaluaciones al reevaluar.
- Scripts PowerShell de runtime, actualización, backup/restore, preflight y arranque automático.
- Reporte local sin secretos.

## Verificación

- `pytest`: 544 passed, 0 failed.
- `compileall`: OK.
- `node --check`: OK.
- `git diff --check`: OK.
- Escaneo estático de secretos: OK.
- Docker Compose: no verificable, Docker no está instalado.
- OmniRoute real: PENDING_LOCAL_VALIDATION; no se accedió al localhost del portátil.

## Estado dental

`evaluation_contaminated=QUARANTINED`; `score_contaminated=INVALID`; `valid_score=NONE`; `opportunity=EVALUATION_BLOCKED`; `reason=INTEGRITY_INCIDENT_OPEN`.

## Artefacto

- **Nombre del paquete**: autonomous-business-lab_iteracion-027_2026-08-28.zip.txt
- **SHA-256**: se rellena automáticamente al empaquetar.

## Próximo paso

Ejecutar localmente el activador ya preparado cuando Javier decida validar OmniRoute.

- **Tamaño del paquete**: 9423488 bytes

- **SHA-256 del paquete**: 7812cc009ffcc3f8ba4e3bc097d8cfed5c4544533202b28f7a2fb07fa52878b2
