# Manifiesto de iteración — plantilla

> Copia esta plantilla a `deliverables/ITERATION_NNN_MANIFEST.md` y rellena
> todos los campos. Los campos de paquete los completa
> `scripts/package_for_review.py` (tokens `*_TOKEN`).

- **Identificador de iteración**: NNN
- **Fecha y hora**: AAAA-MM-DD HH:MM UTC
- **Objetivo**: _(qué se pretendía conseguir en esta iteración)_
- **Estado**: `entregado | en progreso | bloqueado`

## Resumen de cambios

_(2-5 frases, sin genéricos; distinguir implementado / probado
automáticamente / verificado manualmente / simulado / parcial / pendiente /
bloqueado)_

## Archivos

- **Nuevos**:
  - _ruta_
- **Modificados**:
  - _ruta_
- **Eliminados**:
  - _ruta_

## Cambios

- **Arquitectura**: _(cambios estructurales)_
- **Agentes/prompts**: _(cambios en agentes o plantillas)_
- **Scoring y reglas de decisión**: _(cambios en puntuación/bandas/bloqueadores)_
- **Seguridad**: _(cambios en seguridad, secretos, validación)_
- **Presupuesto**: _(cambios en BudgetGuard o modos de operación)_
- **Modelos de datos**: _(tablas/campos SQLite o contratos Pydantic)_
- **Dependencias**: _(añadidas / retiradas; instaladas con qué comando)_

## Comandos

- **Instalar**: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- **Ejecutar**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Probar**: `pytest`

## Pruebas

- **Resultado exacto**: `X passed, Y failed in Zs` (o el equivalente)
- **Comandos usados**: _(lista de comandos de prueba ejecutados)_
- **Comprobaciones manuales**: _(endpoints probados, arranque, etc.)_

## Problemas conocidos / limitaciones / riesgos

- **Problemas conocidos**: _(p. ej. fallos menores conocidos)_
- **Limitaciones**: _(comportamiento intencionadamente limitado)_
- **Riesgos abiertos**: _(riesgos pendientes de la fase)_
- **Deuda técnica**: _(lo que quedó pendiente por simplicidad)_

## Revisión externa

- **Elementos que debe supervisar el revisor**:
  - _(componentes concretos que requieren mirada humana)_
- **Próxima acción recomendada**: _(siguiente paso concreto)_

## Paquete

- **Nombre del paquete**: PACKAGE_NAME_TOKEN
- **Tamaño del paquete**: PACKAGE_SIZE_TOKEN
- **SHA-256 del paquete**: PACKAGE_SHA256_TOKEN

## Git

- **Commit actual**: _(hash o «sin commits todavía»)_
- **Estado del repositorio**: _(p. ej. «todo sin commitear, listo para revisión»)_
- **git diff --stat**: _(salida o «sin commits»)_
- **Archivos cambiados**: _(lista)_
