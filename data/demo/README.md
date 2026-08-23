# Datos de demostración

`demo_opportunities.json` contiene 4 oportunidades del vertical MQL5:

1. **Auditoría automática de Expert Advisors MQL5** — con evidencias de demo.
2. **Diagnóstico de discrepancias entre un EA y su backtest** — con evidencias.
3. **Revisión de archivos SET y gestión de posiciones** — con evidencias.
4. **Bot de trading con rentabilidad garantizada** — sin evidencias: ejemplo
   de oportunidad que el sistema **bloquea** (riesgo grave + falta de
   evidencia).

> ⚠️ **Importante**: toda la evidencia está marcada `verified=false` y
> `method=demo`. Son **ilustraciones**, no investigación real de mercado.
> La puntuación resultante refleja esa falta de verificación (fiabilidad
> reducida, confianza baja). Para decisiones reales, importa investigación
> verificada (ver `docs/FREEBUFF_WORKFLOW.md`).

Carga: `POST /api/demo/load?evaluate=true` o `python3 scripts/seed_demo.py`.
