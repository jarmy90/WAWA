# Flujo manual de revisión (MANUAL_IMPORT)

> Estado: **implementado** (iteración 005). Es la vía principal y funcional del
> comité de contraste; no requiere ninguna API de pago.

## Pasos

1. **Generar el expediente** desde el panel (Laboratorio → "Descargar
   expediente") o vía API:

   ```
   POST /api/reviews/opportunities/{id}/packet
   GET  /api/reviews/opportunities/{id}/packet
   ```

   Se obtiene `review_packet.md`, **idéntico** para todos los revisores y con
   el prompt normalizado al final.

2. **Consultar manualmente** en uno o varios modelos (GPT, Grok, Gemini,
   Claude, DeepSeek...). No se fijan versiones en el código: se registran
   `provider`, `model`, `model_version` y `review_date`.

3. **Guardar la respuesta** en un archivo `.txt` o `.md` (o copiar el texto).

4. **Importar la respuesta** desde el panel (Laboratorio → "Importar
   revisión") o vía API:

   ```
   POST /api/reviews/opportunities/{id}/import
   ```

   El sistema:
   - valida tamaño (200 KB por defecto) y extensión (`.txt`, `.md`, `.markdown`);
   - calcula el SHA-256 y rechaza duplicados del mismo contenido para la misma
     oportunidad (409 con `existing_review_id`);
   - conserva el **texto original** y extrae los campos estructurados con la
     allowlist (ver `docs/REVIEW_SYNTHESIS.md`);
   - señala posibles inyecciones de prompt sin ejecutarlas
     (ver `docs/REVIEW_SECURITY.md`);
   - registra la importación en el `decision_log` (auditoría append-only).

5. **Generar la síntesis**:

   ```
   POST /api/reviews/opportunities/{id}/synthesize
   ```

   Muestra distribución de recomendaciones, consenso (con etiqueta
   opinión/evidencia), riesgos repetidos, evidencia ausente y acción
   recomendada.

6. **Decidir**:
   - Marcar una revisión como inválida si no aplica:
     `POST /api/reviews/{review_id}/invalidate`.
   - Añadir una nota humana: `POST /api/reviews/opportunities/{id}/note`.
   - Continuar sin revisión (ausencia NEUTRAL):
     `POST /api/reviews/opportunities/{id}/continue`.

## Ejemplo de importación (JSON)

```json
{
  "filename": "revision_gpt-4o.txt",
  "content": "recommendation: SMALL_EXPERIMENT\nconfidence: 65\nprimary_risk: ...",
  "provider": "gpt",
  "model": "gpt-4o",
  "execution_mode": "MANUAL_IMPORT",
  "imported_by": "human"
}
```

## Sin bloqueo

- La ventana por defecto es 48 h. Al caducar, el sistema continúa
  automáticamente con su evaluación interna (ausencia = neutral) si
  `review_continue_without_review=true`.
- El propietario no recibe notificaciones por cada idea; las finalistas
  aparecen en el panel y en el resumen semanal.
- No se requiere revisión para gasto simulado (configurable); sí para
  actividades sensibles marcadas por Compliance (riesgo legal/ToS/plataforma).
