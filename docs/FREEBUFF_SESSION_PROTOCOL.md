# FREEBUFF SESSION PROTOCOL

> **Estado: IMPLEMENTADO** (iteración 006). Sesiones reanudables con
> checkpoints persistentes. Freebuff se usa mediante las capacidades reales de
> la sesión (repositorio, terminal, archivos, comandos); **no** existe ninguna
> API de Freebuff ni se finge disponibilidad 24/7.

## Principio

El sistema ejecuta campañas intensivas de descubrimiento, investigación,
contraste y selección en **sesiones de trabajo de 2 a 6 horas** sin consumir
una API LLM de producción. Freebuff actúa como investigador, generador de
conceptos, crítico, analista, operador del torneo, preparador del comité,
constructor de experimentos y mantenedor del repositorio.

El sistema **no** depende de que Freebuff permanezca funcionando 24/7: cada
sesión deja un checkpoint persistente que permite reanudar el trabajo sin
repetirlo.

## Artefactos por sesión

Cada sesión preparada con `scripts/continue_campaign.py --campaign <id> --hours N`
crea (en `data/sessions/<campaign_id>/<session_id>/`):

| Artefacto | Contenido |
|---|---|
| `SESSION_PLAN.md` | Objetivo, tareas priorizadas, archivos a leer, restricciones, entregables, definición de terminado, comando de validación. |
| `SESSION_STATE.json` | Estado estructurado: session_id, campaign_id, stage, tareas planificadas/completadas/pendientes, conceptos, evidencias, blockers, next_action. |
| `SESSION_PROMPT.md` | Prompt breve reutilizable para la siguiente sesión. |
| `SESSION_OUTPUT.json` | (generado por Freebuff durante la sesión) resultados estructurados importables. |
| `SESSION_REPORT.md` | Qué se hizo, qué se verificó, qué es hipótesis y qué quedó pendiente (generado al finalizar). |
| `NEXT_SESSION.md` | Punto de reanudación: permite iniciar una sesión nueva sin reconstruir contexto. |

## Comandos

```bash
# Preparar una sesión (genera plan, estado y prompt breve)
python3 scripts/continue_campaign.py --campaign <id> --hours 5

# Finalizar la sesión (valida, importa, checkpoint, NEXT_SESSION)
python3 scripts/finalize_session.py --session <session_id>
```

El script `continue_campaign.py` imprime el **prompt breve** que el propietario
debe dar a Freebuff en la sesión:

> “Continúa la campaña <id> siguiendo SESSION_PLAN.md. Lee AGENTS.md,
> SESSION_STATE.json y NEXT_SESSION.md. Ejecuta las tareas sin pedirme
> confirmación, valida los resultados, importa los outputs y finaliza la sesión
> con finalize_session.py. No inventes evidencia ni uses APIs de pago.”

## Reglas de sesión

1. Las horas (2-6) representan **alcance y prioridad**, no tiempo garantizado.
2. No repetir tareas ya completadas (dedup por estado persistido).
3. No duplicar conceptos ni evidencias (dedup por título normalizado / URL+resumen).
4. No aumentar silenciosamente los límites del embudo.
5. Cero llamadas API: `api_budget_usd=0` durante el descubrimiento; cualquier
   output con `api_calls_made>0` o `api_cost_usd>0` se rechaza.
6. `SESSION_OUTPUT.json` se valida (Pydantic, `extra="forbid"`, tamaños, no
   negativos) antes de importar.
7. Una sesión sin entregables **no puede finalizarse** (`finalize_session`
   bloquea y explica).
8. Las evidencias sin URL + fecha + fragmento **nunca** se auto-verifican.

## Qué puede hacer Freebuff dentro de una sesión

- Leer/escribir archivos del repositorio (planes, estados, outputs, informes).
- Ejecutar comandos de terminal (tests, scripts, validaciones).
- Importar resultados con `finalize_session.py` o la API `/api/sessions/{id}/import`.
- Ejecutar misiones de investigación y guardar resultados estructurados.
- Preparar expedientes del comité y registrar revisiones manuales.

## Qué NO puede garantizar Freebuff después de la sesión

- Ejecución 24/7, webhooks, jobs permanentes, respuestas inmediatas, monitorización continua.
- Sesiones infinitas ni estado en memoria persistente entre sesiones.

Ver `docs/RUNTIME_STRATEGY.md` para los tres escenarios de runtime y la
arquitectura objetivo recomendada (HYBRID).
