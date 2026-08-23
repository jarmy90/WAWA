# Seguridad — modelo de amenazas y mitigaciones

## Alcance

Aplicación local (MVP) con API FastAPI y dashboard servido por la misma app.
Sin autenticación de usuarios en esta versión (entorno local/desarrollo).

## Modelo de amenazas inicial

| # | Amenaza | Riesgo | Mitigación |
|---|---|---|---|
| 1 | Ejecución de código generado (por IA o por importaciones) | **Alto** | El sistema **nunca ejecuta código** generado ni importado. No existe ruta de ejecución de código arbitrario (sin `eval`/`exec`, sin subprocesos de usuario). |
| 2 | Inyección SQL | Medio | 100% SQL parametrizada a través de repositorios. Sin interpolación de cadenas. |
| 3 | Command injection | Medio | No se ejecutan comandos del sistema con entrada de usuario. |
| 4 | Path traversal | Medio | IDs validados como UUID hex (32 chars); rutas de archivo internas fijas (`data/`, `frontend/`); extensiones de importación en lista blanca (`.json`). |
| 5 | Payloads abusivamente grandes | Medio | `MAX_UPLOAD_BYTES` (por defecto 1 MB) comprobado por `Content-Length`; límites de longitud en todos los campos Pydantic. |
| 6 | Fuga de secretos | Medio | `.env` en `.gitignore`; `env.example` sin valores; logging con `redact()` para claves/tokens; errores internos no exponen trazas (handler 500 genérico). |
| 7 | Datos inventados como "evidencia" | Medio (integridad) | Toda evidencia lleva `method`, `reliability_score`, `verified` y `verification_notes`; el scoring penaliza lo no verificado; el Judge marca bases `evidence/estimate/unknown`. |
| 8 | Fraude financiero / asesoramiento no regulado | Medio | Sin operaciones financieras; Compliance bloquea promesas de rentabilidad; la interfaz avisa de que el análisis es de software, no asesoramiento. |
| 9 | Exfiltración de datos externos | Bajo | Sin scraping automático; solo se guardan URL, fecha, fragmento breve, resumen y fiabilidad. |
| 10 | Envenenamiento de prompts a Gemini | Bajo-Medio | La salida de Gemini nunca se trata como evidencia verificada (solo hipótesis). El sistema no ejecuta sus instrucciones. |
| 11 | CSRF/XSS en el dashboard | Bajo (local) | Escape HTML en el frontend (`esc()`); sin cookies de sesión; CORS por defecto `*` solo en desarrollo. Revisar antes de exponer. |
| 12 | Abuso de costes de API | Medio | BudgetGuard: presupuesto diario/por oportunidad, tope de evaluaciones profundas/día, modos gratuito/simulación, bloqueo manual, registro por acción. |
| 13 | Manipulación del ledger (saldo falso) | **Alto** | Ledger append-only: los asientos confirmados no se editan ni se borran; el saldo se deriva siempre de los movimientos (nunca se persiste un saldo editable); `idempotency_key` UNIQUE; reversiones vinculadas con doble reversión bloqueada; reconciliación que reconstruye saldos desde cero y entra en `SAFE_PAUSE` ante inconsistencias graves. |
| 14 | Confundir simulación con dinero real | **Alto** | Toda respuesta económica incluye `simulated: true` y `real_money_moved: false`; el dashboard muestra "SIMULACIÓN — NO REPRESENTA DINERO REAL"; no existe integración bancaria, Stripe, wallet ni cripto; AUTONOMOUS_PRODUCTION bloqueado por capacidad. |
| 15 | Activación de producción no autorizada | **Alto** | Una variable de entorno puede, como máximo, alcanzar `PRODUCTION_ARMED` (con precondiciones económicas); la activación final exige `production_capability_available=true` + `ENGINE_ACTIVATION_KEY`; arranque con configuraciones inconsistentes ⇒ `SAFE_PAUSE` auditado. |
| 16 | Envenenamiento de metadata contable | Bajo | `metadata` de asientos limitada a 4 KB y validada; importes en Decimal con redondeo fijo; moneda distinta de la base rechazada; importes negativos rechazados. |

## Prácticas obligatorias

- **Nunca** ejecutar código generado por el sistema o por agentes sin sandbox.
- **Nunca** almacenar secretos en Git.
- **Validar todas las entradas** (Pydantic + utilidades de `core/security.py`).
- **No** realizar operaciones financieras reales, trading, envíos masivos ni
  publicaciones automáticas. La economía es 100% simulada y etiquetada como
  tal.
- **No** permitir que un prompt altere el ledger directamente: solo los
  servicios contables (deterministas) crean asientos.
- **No** almacenar más contenido externo del necesario (URL, fecha, fragmento,
  resumen, fiabilidad).

## Zonas de confianza

```
[ Entrada (API) ] → validación → [ Lógica (agentes/scoring) ] → [ SQLite ]
                                       │
                    [ Proveedores LLM (mock/gemini/manual) ]  ← nunca se confía
                                       │
                    [ Salida (dashboard/export) ] ← escape HTML en frontend
```

## Si esto se expone a internet (futuro)

- Añadir autenticación/authorization (Convex Auth u OIDC) y control de acceso.
- Restringir CORS a orígenes conocidos.
- Revisar límites de tasa por IP.
- Mover claves a secretos gestionados; rotación.
- Auditoría de `decision_log` como dato inmutable (backup).
