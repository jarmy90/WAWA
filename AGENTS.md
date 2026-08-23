# AGENTS.md — reglas para agentes de desarrollo

Este documento define cómo trabajar sobre este repositorio. Léelo antes de
modificar nada.

## Reglas inmutables

1. **Nunca inventar evidencia.** Ningún agente de desarrollo puede añadir
   lógica que fabrique demanda, precios, competidores, clientes, estadísticas,
   enlaces, testimonios o resultados. Los datos externos sin verificar se
   marcan `verified=false` con `reliability_score` bajo y `verification_notes`.
2. **El Judge es determinista.** No puede llamar a proveedores de IA ni usar
   aleatoriedad/timestamps para calcular puntuaciones. Misma entrada ⇒ misma
   salida. Cualquier cambio en `app/scoring/` debe mantener esta propiedad.
3. **Ninguna API de pago obligatoria.** El sistema debe arrancar, evaluar y
   testearse 100% offline con `MockProvider`. Gemini (y otros) son opcionales
   y cualquier fallo debe hacer fallback a mock registrando el error.
4. **Nunca ejecutar código generado.** No se ejecuta código producido por el
   sistema (ni por agentes de IA) sin validación y sandbox.
5. **Sin acciones irreversibles ni financieras.** No wallet, trading, compras,
   publicaciones automáticas, envío masivo de mensajes ni creación de cuentas.
6. **No almacenar secretos en Git.** Las claves van en `.env` (ignorado) o en
   el gestor de secretos de la plataforma. `env.example` documenta variables,
   nunca valores reales.
7. **Auditoría completa.** Toda decisión (agente, humana, importación, fallo
   de proveedor) se registra en `decision_log` (append-only). No borrar
   entradas de `decision_log`.
8. **El ledger es append-only y simulado.** Los asientos contables
   (`ledger_entries`) no se editan ni se borran; los confirmados se corrigen
   con una entrada `REVERSAL` vinculada. Importes SIEMPRE en `Decimal`
   (nunca float), sin negativos; moneda única; `idempotency_key` única.
   Nunca mover dinero real: toda respuesta económica lleva
   `simulated=true` / `real_money_moved=false`.
9. **AUTONOMOUS_PRODUCTION está bloqueado por capacidad, no solo por
   configuración.** `production_capability_available=false` mientras no exista
   ejecución financiera real verificada. Una variable de entorno puede, como
   máximo, alcanzar `PRODUCTION_ARMED` (con precondiciones económicas
   cumplidas). Ante configuraciones inconsistentes al arrancar (producción sin
   capital, ledger inconsistente, moneda ausente…), el sistema entra en
   `SAFE_PAUSE` registrando motivo, evento crítico y transición; nunca se
   auto-recupera activando producción.
10. **El motor de ideas nunca inventa demanda (Business Discovery Engine).**
    Los conceptos de las campañas son HIPÓTESIS; `proven_demand` permanece en
    0 sin evidencia de mercado. El General AI Substitution Test bloquea los
    `COMMODITY_WRAPPER` (una IA generalista resuelve el problema sin workflow,
    integración ni memoria) aunque tengan demanda aparente. Las bibliotecas
    (territorios/lentes/arquetipos) viven en `app/core/libraries.py`;
    cualquier cambio debe mantenerlas configurables y documentado en
    `docs/DISCOVERY.md`. El Venture Quality Score (`app/scoring/venture.py`)
    es determinista y sin LLM; la originalidad nunca se auto-asigna: usa
    distancia de fingerprint y utilidad tope. Las misiones Freebuff no se
    auto-verifican: una evidencia solo es `verified=true` con URL + fecha +
    fragmento.

## Convenciones de código

- Python ≥ 3.10, tipado (`from __future__ import annotations`), Pydantic v2
  para contratos. Validar entradas siempre (tamaños, UUIDs, extensiones).
- Estructura modular: `core/` (config/log/seguridad), `models/`, `providers/`,
  `repositories/`, `scoring/` (puro), `agents/`, `services/`, `workflows/`,
  `api/`.
- Los agentes reciben solo datos persistidos (`AgentContext`) y devuelven
  `AgentResult`; el workflow persiste, registra costes y loguea decisiones.
- Logs estructurados JSON vía `app.core.logging.get_logger`.
- SQL parametrizada siempre. Nunca interpolación de cadenas en SQL.
- No añadir dependencias sin justificarlo: SQLite stdlib es suficiente para
  el MVP; si se añade SQLAlchemy, migrar a través de los repositorios.
- Frontend: vanilla JS/CSS servido por FastAPI. Sin frameworks de build.

## Workflow permanente (obligatorio para este proyecto)

Este proyecto opera en dos fases separadas: **DEVELOPMENT_AND_REVIEW** (actual:
supervisión externa, iteraciones y paquetes `.zip.txt`) y
**AUTONOMOUS_PRODUCTION** (futura, desactivada por defecto, activación
explícita del propietario). Reglas permanentes:

1. **Antes de cada iteración**, lee SIEMPRE:
   - `AGENTS.md`
   - `docs/EXTERNAL_REVIEW_WORKFLOW.md`
   - `docs/OPERATING_MODES.md`
   - `docs/ITERATION_HISTORY.md`
2. **Detecta la última iteración** (escaneando `deliverables/ITERATION_*_MANIFEST.md`)
   y continúa la numeración; no reutilices números.
3. Al terminar una iteración con cambios, **entrega SIEMPRE**:
   - Informe textual de 28 puntos (ver `docs/EXTERNAL_REVIEW_WORKFLOW.md`).
   - `deliverables/ITERATION_NNN_MANIFEST.md`.
   - Paquete `autonomous-business-lab_iteracion-NNN_AAAA-MM-DD.zip.txt`
     generado con `scripts/package_for_review.py`.
   - Verificación del paquete con `scripts/verify_review_package.py` ANTES de
     entregarlo; si falla, corrige, regenera y repite.
4. **Nunca** declares válido un paquete sin ejecutar la verificación.
5. El agente **no puede** activar AUTONOMOUS_PRODUCTION por sí mismo: exige
   `production_capability_available=true` **y** clave de activación del
   propietario (auditable); la variable de entorno nunca lo activa
   directamente (como máximo `PRODUCTION_ARMED`).

## Flujo de trabajo

1. Inspecciona el workspace y lee la documentación afectada
   (`docs/ARCHITECTURE.md`, `docs/SCORING.md`).
2. Escribe o modifica pruebas primero cuando sea posible (pytest, offline).
3. Ejecuta siempre:
   ```bash
   pytest
   ```
4. Verifica el arranque y los endpoints con TestClient (no hace falta levantar
   servidor para confirmar rutas).
5. Si cambias el esquema SQLite, actualiza `app/repositories/db.py` y los
   repositorios, y añade una prueba de persistencia. Usa `CREATE TABLE IF NOT
   EXISTS` (migraciones idempotentes, compatibles con bases anteriores).
6. Si tocas la economía (`app/services/economy.py`, `app/repositories/ledger.py`,
   `app/models/ledger.py`): respeta las reglas de `docs/ECONOMY.md` y
   `docs/LEDGER.md` (append-only, Decimal, idempotencia, reversión,
   reconciliación) y añade pruebas de cada una. El saldo se deriva SIEMPRE de
   los asientos; nunca persistas un saldo editable.
7. Si tocas el discovery (`app/scoring/venture.py`, `app/services/discovery.py`,
   `app/core/libraries.py`, `app/repositories/discovery.py`): respeta
   `docs/DISCOVERY.md` y `docs/VENTURE_SCORING.md` (determinismo, no inventar
   demanda, bloqueo COMMODITY_WRAPPER, fingerprint anti-clon, verificación
   estricta de misiones) y añade pruebas.
8. No declares que algo funciona sin ejecutarlo.

## Qué NO hacer

- No crear microservicios ni workers externos para el MVP: los agentes son
  módulos internos.
- No añadir scraping indiscriminado: solo conectores desacoplados a fuentes
  autorizadas que respeten robots.txt, ToS y límites de frecuencia.
- No editar `.env` ni commitear claves. No ejecutar `git push` salvo petición
  explícita.
- No reescribir la lógica de puntuación sin actualizar `docs/SCORING.md` y las
  pruebas de bandas/bloqueadores.
