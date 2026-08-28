# INFORME DE ITERACIÓN 027

1. **Número:** 027.
2. **Objetivo:** reparación de integridad y preparación local de runtime.
3. **Resumen:** se conservó la cuarentena dental, se eliminó el borrado destructivo de evaluaciones y se añadieron scripts locales.
4. **Archivos nuevos:** scripts de automatización local, reporte runtime, pruebas 027, manifiesto e informe.
5. **Archivos modificados:** agentes de análisis, repositorio de evaluaciones, esquema SQLite, pipeline e historial.
6. **Archivos eliminados:** ninguno.
7. **Decisiones técnicas:** append-only; cada reevaluación se enlaza mediante `supersedes_id`.
8. **Dependencias:** ninguna nueva.
9. **Arquitectura:** migración SQLite idempotente y runtime local desacoplado.
10. **Modelos:** evaluación con versión, procedencia, proveedor y modo de ejecución.
11. **Agentes:** filtros contra salidas incompatibles del MockProvider.
12. **Scoring:** la cuarentena no participa; misión sin evidencia no puntúa.
13. **Seguridad/economía:** sin secretos, gasto, publicaciones, contactos ni producción.
14. **Pruebas:** suite completa y comprobaciones estáticas.
15. **Comandos:** `python3 -m pytest -q`; `python3 -m compileall -q app tests scripts`; `node --check`; `git diff --check`.
16. **Superadas:** 544.
17. **Fallidas:** 0.
18. **Errores corregidos:** compatibilidad del conversor del modelo y columnas de migración.
19. **Manual:** auditoría de la evaluación dental contaminada y backup SQLite.
20. **No verificado:** OmniRoute del portátil y Docker local.
21. **Simulado:** pruebas Mock/offline; no representan llamada real.
22. **Externos:** OmniRoute local requiere ejecución en el portátil.
23. **Limitaciones:** no se puede declarar GPT Luna validado desde Freebuff.
24. **Riesgos:** reevaluación dental permanece bloqueada hasta validación limpia.
25. **Deuda:** completar en una futura iteración la integración de revisiones separadas y operador continuo.
26. **Revisión externa:** comprobar append-only y exclusión de QUARANTINED.
27. **Ejecución:** usar el activador PowerShell local preparado.
28. **Próximo paso:** validación local de OmniRoute; no se inicia automáticamente desde Freebuff.
