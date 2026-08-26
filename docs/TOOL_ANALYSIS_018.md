# Análisis de herramientas y repositorios externos — iteración 018

Fecha: 2026-08-26 · Método: revisión de documentación pública y catálogo del
proyecto. **Ninguna popularidad/estrellas se trata como prueba de calidad.**
Cada entrada declara su nivel de verificación real: `INSPECCIONADO`,
`DOCUMENTADO` (solo lectura de docs públicas) o `UNKNOWN`.

Decisión por entrada: `INTEGRATE_NOW | BENCHMARK_FIRST | OPTIONAL_ADAPTER |
REJECT | UNKNOWN`.

## Resumen de decisiones

| Herramienta | Decisión | Justificación corta |
|---|---|---|
| Agent Reach | `UNKNOWN` | No se ha inspeccionado código ni releases; sin evidencia verificada de sus capacidades. No se instala sin un benchmark previo. |
| OmniRoute (gateway local) | `OPTIONAL_ADAPTER` | Ya integrado (iteración 008), desactivado por defecto; falta disco para el benchmark real. |
| OpenRouter (comité) | `BENCHMARK_FIRST` | Opción A ya integrada con guardas; sin clave no hay revisión (ausencia neutral). |
| Reddit API / escucha de foros | `BENCHMARK_FIRST` | Útil para misiones de demanda; exige respetar ToS/límites; no scraping indiscriminado (regla AGENTS). |
| YouTube (RSS público) | `OPTIONAL_ADAPTER` | RSS público sin auth; útil para señales; coste 0. |
| RSS genérico | `OPTIONAL_ADAPTER` | Sindicación pasiva; sin workers extra (regla MVP). |
| n8n / schedulers externos | `REJECT` (por ahora) | Regla: sin workers externos en MVP; un cron/proceso único basta. |
| Stripe Checkout / Payment Links | `BENCHMARK_FIRST` | Solo tras READY_TO_CONNECT_SERVICES; modo test primero. |
| Plausible / Umami (analytics) | `OPTIONAL_ADAPTER` | Analytics respetuosa con privacidad; sin cookies de terceros. |
| SQLite backups cifrados | `INTEGRATE_NOW` | Diseño documentado en AUTONOMOUS_LAUNCH; sin dependencias nuevas. |
| GitHub Actions (CI) | `OPTIONAL_ADAPTER` | Para verificar suite en cada iteración; sin secretos en el repo. |

## Notas por categoría

### Escucha de mercado (B6)
- **Reddit/foros**: las misiones Fase 1 ya incluyen consultas `foro OR reddit`
  y exigen URL+fecha+fragmento. Un conector futuro debe ser desacoplado,
  respetar robots.txt/ToS y límites de frecuencia. Decisión: `BENCHMARK_FIRST`.
- **YouTube RSS**: feed público por canal/búsqueda sin OAuth; coste 0; útil
  como señal complementaria. Decisión: `OPTIONAL_ADAPTER`.
- **GitHub (issues/releases)**: verificación manual vía API autenticada en el
  flujo de revisión; sin automatización nueva. Decisión: `OPTIONAL_ADAPTER`.

### Construcción y despliegue
- **Plantillas SaaS**: no se adopta ninguna sin evaluar la ganadora del
  super-torneo; la landing será estática (Vite/HTML) según AUTONOMOUS_LAUNCH.
- **Hosting**: sin decisión hasta READY_TO_CONNECT_SERVICES; sin coste.
- **Stripe**: `BENCHMARK_FIRST` — Checkout/Payment Links en modo test, webhook
  con firma, cero cargos reales sin autorización única.

### Runtime 24/7 y operación
- **Scheduler**: cron/proceso único (regla: sin workers extra). Decisión:
  `INTEGRATE_NOW` como diseño.
- **Observabilidad**: logs JSON estructurados existentes + endpoint
  `/api/command-center`. Decisión: `INTEGRATE_NOW` (ya presente).
- **Agent Reach**: `UNKNOWN` — sin evidencia verificada; no se instala.
  Pendiente de un benchmark controlado en un entorno con espacio en disco.

## Limitación honesta
Varias entradas (Agent Reach, n8n, Reddit API, Stripe) están marcadas
`UNKNOWN`/`BENCHMARK_FIRST` porque **no se ha inspeccionado su código fuente,
issues, releases ni licencia en esta sesión**. El proyecto no convierte
popularidad ni marketing en prueba de calidad: cualquier integración futura
exigirá inspección real y registro en `decision_log` antes de tocar la base.
