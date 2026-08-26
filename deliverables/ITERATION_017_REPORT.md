# Informe de iteración 017 — Importación automática de planes y paquetes portables (v0.16.0)

1. **Número de iteración**: 017.
2. **Objetivo**: automatizar el flujo "paquete de reformulación → aplicación
   local → candidatas locales → misiones locales → investigación importable",
   garantizando que los IDs de los JSON portables (de una reproducción aislada)
   NUNCA se insertan en la base local.
3. **Resumen del trabajo realizado**: servicio de importación con coincidencia
   inequívoca por título normalizado (+territorio/lente/arquetipo), Quality Gate
   y torneo delegados al orquestador existente, misiones Fase 1 con IDs locales,
   idempotencia por contenido, endpoints API, CLI único y bloque visual en el
   panel; 9 tests nuevos offline.
4. **Archivos nuevos**: `app/services/reformulation_import.py`,
   `scripts/apply_reformulation_plan.py`, `frontend/ops17.js`,
   `tests/test_reformulation_import_017.py`,
   `deliverables/ITERATION_017_MANIFEST.md`, este informe.
5. **Archivos modificados**: `app/api/routes.py`, `app/core/config.py`,
   `frontend/index.html`, `frontend/app.js`, `docs/ITERATION_HISTORY.md`.
6. **Archivos eliminados**: ninguno.
7. **Decisiones técnicas**: (a) localización por título normalizado NFKD sin
   acentos con refuerzo territorio+lente+arquetipo; (b) rechazo registrado ante
   0 o ≥2 coincidencias (nunca aplicación dudosa); (c) idempotencia comparando
   el brief almacenado completo (cualquier estado posterior), no el estado;
   (d) mapeo estable título+kind+phase+ordinal para paquetes de investigación,
   delegando la aplicación en `import_research` (raw conservado, dedupe,
   verificación URL+fecha+fragmento); (e) el importador no duplica lógica:
   `advance()` del orquestador ejecuta Quality Gate/torneo/misiones.
8. **Dependencias añadidas o retiradas**: ninguna.
9. **Cambios en arquitectura**: módulo interno `services/` + 2 endpoints;
   sin workers ni microservicios (regla del MVP respetada).
10. **Cambios en modelos de datos**: ninguno (esquema SQLite intacto).
11. **Cambios en prompts o agentes**: ninguno.
12. **Cambios en scoring y reglas de decisión**: ninguno; puntuaciones
    estructural/con-evidencia intactas; evidencia sigue en 0 sin fuentes.
13. **Cambios en seguridad o gestión presupuestaria**: contratos Pydantic
    `extra="forbid"`; archivos subidos tratados como datos no confiables;
    envolvente `real_money_moved=false`; presupuesto 0 €; PRE_CYCLE detenido.
14. **Pruebas ejecutadas**: pytest completo (337 passed) y node --check sobre
    ambos ficheros JS.
15. **Comandos exactos utilizados**:
    - `python3 -m pytest tests/test_reformulation_import_017.py -q`
    - `python3 -m pytest`
    - `node --check frontend/app.js && node --check frontend/ops17.js`
16. **Número de pruebas superadas**: 337 (328 previas + 9 nuevas).
17. **Número de pruebas fallidas**: 0 (2 fallos iniciales corregidos, ver 18).
18. **Errores encontrados y correcciones aplicadas**:
    - Idempotencia fallaba porque tras `advance()` el concepto queda en
      RESEARCH_PENDING (no RESEARCH_CANDIDATE): la comparación ahora es por
      contenido del brief, independiente del estado.
    - El test de API usaba un plan vacío que violaba `min_length=2` (422):
      sustituido por un plan de humo con entrada inexistente que demuestra el
      rechazo honesto vía HTTP.
19. **Comprobaciones manuales realizadas**: flujo offline completo reproducido
    (campaña → plan aplicado → 12 misiones Fase 1 locales → paquete importado →
    RESEARCH_IMPORTED; evidencia sin fragmento ⇒ verified=false); sintaxis JS.
20. **Funcionalidades no verificadas**: la ejecución real del plan sobre la base
    del propietario (requiere su instalación; se deja CLI + panel listos).
21. **Elementos simulados o mock**: nada nuevo; los briefs importados son
    HIPÓTESIS etiquetadas y no elevan ninguna puntuación.
22. **Dependencias de servicios externos**: ninguna (100 % offline).
23. **Limitaciones conocidas**: títulos renombrados a mano no coinciden (rechazo
    trazado); mapeo estable ignora ordinal>1 (Fases futuras).
24. **Riesgos abiertos**: la calidad de las candidatas depende de las misiones
    reales pendientes de investigar; sin ellas no hay finalistas (0 válido).
25. **Deuda técnica**: soporte explícito de ordinal/fase en el paquete portable.
26. **Verificación del paquete**: `scripts/verify_review_package.py` ejecutado
    sobre el paquete final (resultado en el manifiesto/historial).
27. **Estado de la campaña**: sin cambios en bases reales; la operación se
    aplica cuando el propietario la ejecute (preview disponible).
28. **Próximo paso recomendado**: ejecutar
    `python3 scripts/apply_reformulation_plan.py --file reformulaciones_briefs.json --preview`
    en la instalación real, revisar coincidencias, aplicar, copiar las 6 misiones
    Fase 1 por candidata e importar resultados con URL+fecha+fragmento.
