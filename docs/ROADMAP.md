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

### 0. Ejecutar campañas Freebuff-first reales (iteración 006)
El CampaignRunner y el protocolo de sesiones reanudables están implementados
y probados (207 tests). El siguiente paso es **usarlos en serio**:
- Lanzar una campaña real con `scripts/continue_campaign.py --campaign <id> --hours 5`.
- Ejecutar una sesión de 2-6 h de Freebuff investigando misiones reales.
- Finalizar con `finalize_session.py`, revisar `NEXT_SESSION.md` y reanudar.
- Medir: ¿el protocolo ahorra contexto? ¿las misiones mejoran la evidencia?
- Probar el API Readiness Gate sobre los finalistas reales.

### 1. Poner a trabajar el comité de contraste con modelos reales (iteración 005)
El **Laboratorio de oportunidades** ya funciona offline (`MANUAL_IMPORT` +
`MOCK`): expediente idéntico, importación TXT/MD, síntesis con etiqueta de
falso consenso y no-bloqueo. Siguiente paso natural:
- Usar el flujo manual con GPT/Grok/Gemini sobre 2-3 finalistas reales.
- Comprobar si las objeciones del comité mejoran la selección frente al
  Judge solo (medir con decisiones posteriores).
- Evaluar `API_AUTOMATIC` cuando exista API estable, credencial, presupuesto
  y condiciones de uso compatibles (sin inventar integraciones).

### 2. Validar el motor de ideas con investigación real (iteración 004)
El Business Discovery Engine (Ruta B) ya genera campañas, filtra wrappers y
selecciona finalistas offline. Ahora toca validar la **calidad** de las
selecciones:
- Lanzar 2-3 campañas completas y exportar las misiones de los finalistas.
- Freebuff investiga las misiones (foros, precios, competidores, compradores)
  y reimporta los resultados.
- Comprobar: ¿los finalistas del torneo siguen pareciendo buenos con
  evidencia real? ¿alguno se revela como wrapper o sin comprador?
- **Este es el test de la tesis del proyecto.**

### 2. Misiones de investigación con más profundidad
- Permitir adjuntar el JSON de resultados de misión directamente en el panel
  (hoy: import vía API).
- Misión por defecto al promover un finalista (tesis + experimento).

### 3. Conectores de investigación éticos
- Conector opcional a fuentes autorizadas (ej. RSS de foros públicos, docs)
  con: robots.txt, límites de frecuencia, identificación transparente,
  retención mínima (URL, fecha, fragmento, resumen, fiabilidad).

### 4. Mejorar el Scout y el generador
- Generar candidatos de mayor calidad para sectores arbitrarios con Gemini
  (opcional): el MockProvider es determinista y tosco por diseño, pero las
  plantillas por keyword (sector MQL5) producen candidatos genéricos fuera
  del vertical.
- Ajustar las bibliotecas (territorios/lentes/arquetipos) con lo que
  aprendan las campañas (memoria empresarial ya persistida).

### 5. Experimentos con estado real
- Dar estado real a `Experiment` (`running → success/failed`) con registro de
  resultados y aprendizaje (qué hipótesis fallaron y por qué).
- Conectar el coste por experimento del ledger con el blueprint de la
  iteración 004.

### 6. Autonomía económica (solo tras validar)
- Presupuesto por experimento, métricas de ROI, y (más adelante) integración
  con pagos **explícitamente aprobada por el humano**. Fuera de alcance:
  wallet, smart contracts, trading, compras autónomas, muerte irreversible.

### 7. Calidad de código
- Migrar a SQLAlchemy/Alembic si el esquema crece.
- Añadir lint/typecheck (ruff/mypy) al CI.
- Dockerfile opcional (el proyecto ya funciona sin Docker).

### 8. Producción
- Auth (Convex Auth u OIDC), CORS restringido, rate limiting.
- Hosting Python 24/7 para la API + scheduler de evaluaciones.
- Copias de seguridad de `data/abl.db`.

## Criterios para considerar la tesis validada

- Con investigación real, las oportunidades con demanda demostrada suben a
  "aprobada" y las sin demanda se quedan en "aplazada/rechazada".
- La confianza media de las evaluaciones con evidencia verificada > 60%.
- Al menos un experimento propuesto se ejecuta con presupuesto < 50 USD y da
  una señal clara (éxito o fracaso) en < 30 días.
- Los finalistas del torneo de descubrimiento mantienen su atractivo con
  evidencia real, y los COMMODITY_WRAPPER del filtro se confirman como tales.
