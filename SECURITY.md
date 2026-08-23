# Seguridad

El modelo de amenazas completo, las mitigaciones y las prácticas de la
aplicación están en **[docs/SECURITY.md](docs/SECURITY.md)**.

Resumen:

- **No se ejecuta código generado.** El sistema no ejecuta código producido
  por IA ni por usuarios sin validación y sandbox.
- **No hay operaciones financieras, trading ni publicaciones automáticas.**
  El motor solo analiza y puntúa; no actúa en el mundo real.
- **Secretos**: nunca se almacenan en Git. `env.example` documenta variables;
  `.env` está ignorado. Claves solo en el gestor de secretos de la plataforma.
- **Validación de entradas**: contratos Pydantic, límites de tamaño de
  payloads, lista blanca de extensiones y validación de UUIDs (anti path
  traversal).

## Reportar una vulnerabilidad

Por favor, no abras issues públicos con detalles de seguridad. En su lugar:

- Abre un issue privado en el repositorio (si está disponible) o contacta con
  el mantenedor por el canal privado de la plataforma, indicando:
  - Descripción del problema y pasos para reproducirlo.
  - Impacto potencial.
  - Sugerencia de mitigación (si la tienes).

Se agradece la divulgación responsable: espera a una corrección antes de
publicar detalles.
