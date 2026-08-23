# Comité externo visual — experiencia del propietario (iteración 009)

## La única tarea del propietario (opcional, < 5 minutos)

1. **Copiar** el expediente desde el panel (botones "Copiar para GPT / Grok / Gemini").
2. **Pegarlo** en el modelo elegido y esperar la respuesta.
3. **Copiar la respuesta** y **pegarla de vuelta** en el panel ("Pegar respuesta / Importar").

Nada más. No hace falta GitHub, terminal, JSON, identificadores manuales, editar
archivos ni conocer la API. Si el propietario no hace nada, el sistema continúa
(ausencia neutral, nunca bloquea).

## Qué garantiza el panel

- Los tres botones de copiado usan **exactamente el mismo contenido base**; solo
  varía una cabecera de metadatos que identifica al revisor (GPT/Grok/Gemini).
- El expediente incluye un **token no secreto**: `opportunity_id`, `packet_id`,
  `packet_version`, `generated_at` y `content_hash` (mismo valor para los tres
  revisores). Nunca incluye claves ni instrucciones operativas del sistema.
- Al pegar una respuesta se valida tamaño, oportunidad y versión del expediente,
  se calcula el hash (detección de duplicados), se conserva el texto original y
  se procesa como **dato no confiable** (parser con allowlist; las instrucciones
  inyectadas nunca cambian el sistema).
- Se puede importar un **archivo combinado** con secciones:

  ```markdown
  # GPT
  <respuesta>

  # GROK
  <respuesta>

  # GEMINI
  <respuesta>

  # HUMAN_NOTE
  <nota opcional>
  ```

  Si falta una sección, se importan las restantes.

## Estados visuales de cada tarjeta

Pendiente · Importada · Procesada · Parcial · Inválida · Caducada · Continuó sin revisión.

Además, cada proveedor (GPT/Grok/Gemini/OpenRouter/OmniRoute) muestra su propio
estado en la tarjeta, junto con la puntuación interna, la confianza media, el
consenso, la ventana restante y la próxima acción.

## Decisión autónoma

El propietario **no vota**. El botón "Decidir (automático)" aplica reglas
deterministas que combinan: puntuación interna, evidencias, riesgos, presupuesto,
recomendaciones externas y calidad del expediente. Las revisiones solo ajustan
**prioridad** y **confianza** (±5 máx.) y **nunca** pueden:

- autorizar producción;
- aumentar presupuesto;
- mover dinero;
- eliminar bloqueadores;
- registrar ingresos;
- convertirse en evidencia de demanda.

## Filtros de entrada al comité

Solo entran oportunidades que superen los filtros internos:

- Puntuación interna mínima: 72 (configurable).
- Máximo: 3 finalistas por semana.
- Mínimo: 3 grupos de evidencia independientes (configurable).
- Sin bloqueadores críticos.
- Evidence Quality mínima configurable (umbral de puntuación interna).

## Ventana y funcionamiento sin propietario

- Ventana opcional: 48 h (configurable). Al caducar sin revisiones, el sistema
  continúa con la evaluación interna; la ausencia es **neutral** (no aprobación).
- Notificaciones: resumen semanal. Alertas inmediatas solo para riesgos críticos.
