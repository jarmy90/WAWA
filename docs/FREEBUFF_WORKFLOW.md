# Uso de Freebuff en este proyecto

## Investigación previa (hecha en la primera entrega)

Se inspeccionó el entorno de trabajo: **no existe una API pública estable de
Freebuff como runtime para ejecutar este sistema de producción** (no se ha
inventado ninguna). Por lo tanto:

1. Freebuff se usa para **construir, probar, revisar y evolucionar** el
   proyecto durante el desarrollo (lo que estás haciendo ahora).
2. La lógica del proveedor está **separada** (`app/providers/`) para poder
   conectar cualquier runtime futuro sin tocar el resto.
3. Para ejecución 24/7 haría falta un **endpoint externo** (hosting con
   uvicorn) — ver "Ejecución continua" abajo.

## Qué se puede automatizar dentro de Freebuff (ahora)

- **Desarrollo**: editar código, ejecutar `pytest`, revisar resultados,
  generar/importar investigaciones.
- **Investigación asistida**: el `ManualProvider` (`LLM_PROVIDER=manual`)
  escribe solicitudes de investigación en `data/manual_research/requests/`
  con un esquema esperado. Un agente de Freebuff (o el humano) puede:
  1. Leer la solicitud.
  2. Buscar fuentes reales (foros MQL5, documentación, precios observados).
  3. Depositar la respuesta en `data/manual_research/responses/` como JSON:
     ```json
     {
       "request_id": "<id de la solicitud>",
       "content": {
         "evidences": [
           {"evidence_type": "demand_signal", "source_name": "...", "source_url": "...",
            "summary": "...", "reliability_score": 0.7, "independence_group": "forum",
            "verified": false, "verification_notes": "..."}
         ],
         "competitors": [{"name": "...", "observed_price": 120.0, "weaknesses": "..."}],
         "target_customer": "...",
         "unknowns": []
       },
       "verified": true,
       "notes": "Investigación realizada desde Freebuff"
     }
     ```
  4. Volver a evaluar la oportunidad (`POST /api/opportunities/{id}/evaluate`):
     las evidencias verificadas suben la puntuación de forma honesta.
- **Importación directa**: también se puede pegar el paquete JSON en el
  dashboard (`Importar investigación`) o vía `POST /api/import`.
- **Exportación**: Freebuff puede leer los exports JSON/Markdown para
  continuar el análisis.

## Qué necesitaría un endpoint externo (ejecución 24/7)

- Servir la API (`uvicorn app.main:app`) en un hosting con Python 3.10+.
- Un cron/scheduler que ejecute evaluaciones programadas
  (ej. `POST /api/opportunities/{id}/evaluate`).
- Si se quiere Gemini en producción: definir `GEMINI_API_KEY` como secreto de
  producción (nunca en el repo).

## No hacer

- No usar "la API de Freebuff" para llamadas runtime: no existe una API
  estable documentada en este entorno. Cualquier integración futura se
  añadiría en `app/providers/` siguiendo `BaseLLMProvider`.
- No poner claves reales en el repositorio ni en `env.example`.

## Flujo recomendado por iteración

1. Freebuff escribe/refina código y corre `pytest`.
2. Freebuff (o el humano) realiza investigación real para 1-3 oportunidades y
   la deposita en `data/manual_research/responses/`.
3. Se reevalúa y se revisa el dashboard: ¿subió la confianza? ¿cambió la
   decisión?
4. Se exportan las fichas y se decide el siguiente experimento.
