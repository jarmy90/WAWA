# Manifiesto de iteración 001

- **Identificador de iteración**: 001
- **Fecha y hora**: 2026-08-23 (registro retroactivo al crear el workflow)
- **Objetivo**: construir el MVP local completo del motor de investigación y
  selección de oportunidades (flujo de 13 pasos, 7 agentes, scoring
  determinista, BudgetGuard, dashboard, tests).
- **Estado**: `entregado`

## Resumen de cambios

Primera entrega del sistema: núcleo FastAPI + SQLite + dashboard vanilla,
abstracción de proveedores (mock/gemini/manual), motor de puntuación
determinista con bandas y bloqueadores, pipeline multiagente auditado y demo
MQL5. Todo probado con 80 tests offline. Nota: esta iteración se realizó antes
de la creación del workflow de revisión externa; se registra aquí para mantener
el historial consecutivo.

## Archivos

- **Nuevos**: `app/` (core, models, providers, repositories, scoring, agents,
  services, workflows, api, main), `frontend/` (dashboard), `tests/` (80
  tests), `docs/` (ARCHITECTURE, SCORING, SECURITY, FREEBUFF_WORKFLOW,
  ROADMAP), `data/demo/`, `scripts/` (run.sh, seed_demo.py), `pyproject.toml`,
  `README.md`, `AGENTS.md`, `SECURITY.md`, `env.example`, `.gitignore`.
- **Modificados**: ninguno (repositorio vacío al empezar; `REAME.MD` previo
  intacto).
- **Eliminados**: ninguno.

## Cambios

- **Arquitectura**: FastAPI + SQLite (stdlib) + repositorios tipados + DI
  manual. Juez 100% determinista (sin LLM).
- **Agentes/prompts**: 7 agentes con `AgentContext`/`AgentResult`; plantillas
  deterministas del MockProvider; fallback automático a mock.
- **Scoring y reglas de decisión**: pesos 20/20/15/15/10/10/5/5; bandas
  75/60/40; bloqueadores duros (ver `docs/SCORING.md`).
- **Seguridad**: validación Pydantic estricta, whitelist de extensiones,
  límites de tamaño, UUIDs, sin ejecución de código, sin secretos en Git.
- **Presupuesto**: BudgetGuard (diario, por oportunidad, tope de evaluaciones
  profundas, modos gratuito/simulación).
- **Modelos de datos**: `opportunities`, `evidence`, `competitors`,
  `evaluations`, `experiments`, `decision_log`, `costs`.
- **Dependencias**: fastapi, uvicorn, pydantic, pydantic-settings; dev:
  pytest, httpx; opcional: google-generativeai.

## Comandos

- **Instalar**: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- **Ejecutar**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Probar**: `pytest`

## Pruebas

- **Resultado exacto**: 80 passed, 0 failed.
- **Comandos usados**: `python3 -m pytest tests/ -q`
- **Comprobaciones manuales**: arranque real de uvicorn verificado con
  `curl` sobre `/api/health`, `/`, `/api/opportunities` y export Markdown;
  demo cargada y evaluada (4 oportunidades); `node --check frontend/app.js`.

## Problemas conocidos / limitaciones / riesgos

- **Problemas conocidos**: ninguno bloqueante.
- **Limitaciones**: modo offline = escepticismo por diseño (sin evidencia
  verificada no se aprueba); demo sin verificar; mock tosco fuera del vertical
  MQL5; sin scraping; sin autenticación (solo local).
- **Riesgos abiertos**: los listados en `docs/ROADMAP.md`.
- **Deuda técnica**: deduplicación simple por título; evaluación reemplazada
  en tabla (historial solo en `decision_log`).

## Revisión externa

- **Elementos que debe supervisar el revisor**: coherencia del scoring con la
  especificación; honestidad de las puntuaciones en modo offline; diseño de
  bloqueadores; seguridad de importaciones.
- **Próxima acción recomendada**: validar la tesis con investigación real
  (importar evidencias verificadas y comprobar que las decisiones cambian).

## Paquete

- **Nombre del paquete**: _sin paquete (anterior al workflow de revisión)_
- **Tamaño del paquete**: —
- **SHA-256 del paquete**: —

## Git

- **Commit actual**: `598fcc0 Create REAME.MD` (solo el archivo previo)
- **Estado del repositorio**: en su momento, sin commits del proyecto; hoy el
  contenido vive en el Changes panel de Freebuff.
- **git diff --stat**: sin cambios sobre HEAD (archivos sin trackear).
- **Archivos cambiados**: todos los de esta iteración (nuevos, sin commitear).
