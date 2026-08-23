# Roadmap y próximos pasos

## Limitaciones reales de esta primera entrega (honestas)

1. **Modo offline = escepticismo por diseño.** Sin evidencia verificada,
   ninguna oportunidad llega a "aprobada": es la consecuencia directa del
   principio fundamental. Para aprobar hay que importar investigación
   verificada (manual/Freebuff). Esto puede parecer "que no selecciona", pero
   es la propiedad que se quiere medir.
2. **La demo (`data/demo/`) es material ilustrativo** con fuentes plausibles
   pero sin verificar: no es investigación real de mercado. Las puntuaciones
   de demo no deben usarse para decidir negocios reales.
3. **El proveedor mock es determinista pero tosco**: plantillas por keywords
   (sector MQL5) y heurísticas simples. Un problema fuera del vertical puede
   producir candidatos genéricos de baja calidad.
4. **Sin scraping automático**: la investigación externa llega por
   importación. Los conectores a fuentes autorizadas (con robots.txt/ToS)
   son trabajo futuro.
5. **Gemini no verifica nada**: su salida se marca como no verificada.
6. **Sin autenticación** en el dashboard (solo local). No exponer a internet
   sin añadir auth.
7. **Presupuesto estimado, no real**: sin API de pago no hay coste real que
   medir; el BudgetGuard registra estimaciones o 0 con método indicado.
8. **Una sola BD SQLite**: suficiente para el MVP, no para multi-usuario.
9. **Deduplicación simple** (título normalizado): puede fallar con títulos
   muy distintos que describan lo mismo.
10. **El DecisionLog es append-only pero la evaluación se reemplaza**:
    el historial de decisiones queda en el log; las puntuaciones anteriores
    no se versionan en tabla aparte (sí en el log).

## Próximos pasos recomendados (por prioridad)

### 1. Validar el sistema con investigación real
- Usar Freebuff para investigar 2-3 de las oportunidades MQL5 de la demo
  (hilos reales de MQL5.com, precios del Mercado/Freelance, perfiles).
- Depositar la investigación como respuestas manuales y reevaluar.
- Comprobar si la puntuación sube y si las decisiones cambian de forma
  razonable. **Este es el test de la tesis del proyecto.**

### 2. Conectores de investigación éticos
- Conector opcional a fuentes autorizadas (ej. RSS de foros públicos, docs)
  con: robots.txt, límites de frecuencia, identificación transparente,
  retención mínima (URL, fecha, fragmento, resumen, fiabilidad).

### 3. Mejorar el Scout
- Generar candidatos de mayor calidad para sectores arbitrarios
  (plantillas por vertical + refinamiento con Gemini cuando esté disponible).

### 4. Experimentos
- Dar estado real a `Experiment` (`running → success/failed`) con registro de
  resultados y aprendizaje (qué hipótesis fallaron y por qué).

### 5. Autonomía económica (solo tras validar)
- Presupuesto por experimento, métricas de ROI, y (más adelante) integración
  con pagos **explícitamente aprobada por el humano**. Fuera de alcance:
  wallet, smart contracts, trading, compras autónomas, muerte irreversible.

### 6. Calidad de código
- Migrar a SQLAlchemy/Alembic si el esquema crece.
- Añadir lint/typecheck (ruff/mypy) al CI.
- Dockerfile opcional (el proyecto ya funciona sin Docker).

### 7. Producción
- Auth (Convex Auth u OIDC), CORS restringido, rate limiting.
- Hosting Python 24/7 para la API + scheduler de evaluaciones.
- Copias de seguridad de `data/abl.db`.

## Criterios para considerar la tesis validada

- Con investigación real, las oportunidades con demanda demostrada suben a
  "aprobada" y las sin demanda se quedan en "aplazada/rechazada".
- La confianza media de las evaluaciones con evidencia verificada > 60%.
- Al menos un experimento propuesto se ejecuta con presupuesto < 50 USD y da
  una señal clara (éxito o fracaso) en < 30 días.
