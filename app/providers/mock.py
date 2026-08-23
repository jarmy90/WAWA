"""Proveedor simulado determinista (sin API, gratuito).

Reglas de diseño:
- Misma entrada -> misma salida (reproducible, testeable).
- **Nunca inventa datos externos**: la demanda, los precios, los competidores
  y los perfiles de cliente se marcan como DESCONOCIDO cuando no hay evidencia.
- Solo "echa" hechos explícitamente presentes en el texto de entrada del
  usuario (p. ej. la plataforma mencionada), siempre como no verificados.
- Coste registrado: 0 (modo offline). Método: ``zero (offline)``.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from app.providers.base import BaseLLMProvider, LLMResponse

MQL5_KEYWORDS = ("mql5", "metatrader", "meta trader", "expert advisor", "ea ", " backtest", "set file", "algorítm", "algoritm", "trading")


def _stable_pick(seed: str, items: list[str]) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return items[int(digest[:8], 16) % len(items)]


def _is_mql5(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in MQL5_KEYWORDS)


class MockProvider(BaseLLMProvider):
    name = "mock"

    def available(self) -> bool:
        return True

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        task: str | None = None,
        output_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        handler = getattr(self, f"_task_{task}", None) if task else None
        if handler is None:
            structured: dict[str, Any] = {
                "unknown": True,
                "note": "Sin tarea específica: el proveedor simulado no genera contenido.",
            }
            return LLMResponse(
                text="(mock) Sin tarea específica.",
                structured=structured,
                model="mock-deterministic",
                method="mock (deterministic, offline)",
                cost_estimate_usd=0.0,
                cost_method="zero (offline)",
            )
        return handler(prompt, system=system)

    # ------------------------------------------------------------------
    def _task_scout(self, prompt: str, system: str | None) -> LLMResponse:
        problem = system or prompt
        sector_hint = ""
        m = re.search(r"SECTOR_HINT:\s*(.+)", prompt)
        if m:
            sector_hint = m.group(1).strip()

        if _is_mql5(problem):
            opportunities = [
                {
                    "title": "Auditoría automática de Expert Advisors MQL5",
                    "problem": "Los traders y desarrolladores MQL5 no tienen una forma rápida, barata y sistemática de auditar sus Expert Advisors (lógica, gestión de posiciones, reentradas, archivos SET) antes de publicarlos o ejecutarlos con dinero real.",
                    "proposed_solution": "Servicio de auditoría automática de EAs que revisa el código y la configuración, detecta errores de reentrada, duplicidad y gestión de posiciones, y entrega un informe estructurado con la trazabilidad de cada hallazgo.",
                    "target_customer": "Desarrolladores de EAs MQL5 y traders que compran o heredan EAs y quieren validarlos antes de usarlos.",
                    "sector": sector_hint or "servicios técnicos para trading algorítmico / MQL5",
                },
                {
                    "title": "Diagnóstico de discrepancias entre un EA y su backtest",
                    "problem": "Es habitual que un EA se comporte distinto en backtest que en demo o real; los traders no logran identificar si el problema es de datos, de lógica, de brokers o de ejecución, y pierden tiempo y dinero.",
                    "proposed_solution": "Herramienta de diagnóstico que compara operaciones esperadas vs ejecutadas a partir de los logs de MetaTrader y genera un informe de causas probables con evidencias trazables.",
                    "target_customer": "Traders algorítmicos que ejecutan EAs en MetaTrader y necesitan explicar diferencias entre backtest y real.",
                    "sector": sector_hint or "servicios técnicos para trading algorítmico / MQL5",
                },
                {
                    "title": "Revisión de archivos SET y detección de errores de gestión de posiciones",
                    "problem": "Los archivos SET de MQL5 se configuran a mano, contienen parámetros inconsistentes y no hay forma automática de comprobar reentradas, duplicidad de órdenes ni límites de riesgo antes de ejecutar.",
                    "proposed_solution": "Validador de archivos SET y de lógica de gestión de posiciones que marca parámetros fuera de rango, conflictos y riesgos, con documentación técnica generada automáticamente.",
                    "target_customer": "Usuarios de EAs MQL5 (compradores del Mercado MQL5) y desarrolladores que entregan configuraciones.",
                    "sector": sector_hint or "servicios técnicos para trading algorítmico / MQL5",
                },
            ]
        else:
            t = problem.strip()
            first = t.split(".")[0][:90]
            opportunities = [
                {
                    "title": f"Herramienta para resolver: {first}",
                    "problem": t,
                    "proposed_solution": "Servicio/herramienta digital que automatiza la detección y resolución del problema descrito, con entregables trazables y sin prometer resultados no verificables.",
                    "target_customer": "Por definir (DESCONOCIDO en modo offline; requiere investigación).",
                    "sector": sector_hint or "pendiente de clasificar",
                }
            ]
        return LLMResponse(
            text="Oportunidades candidatas generadas de forma determinista (sin API).",
            structured={"opportunities": opportunities},
            model="mock-deterministic",
            method="mock (deterministic, offline)",
            cost_estimate_usd=0.0,
            cost_method="zero (offline)",
        )

    def _task_research(self, prompt: str, system: str | None) -> LLMResponse:
        problem = (system or prompt).lower()
        unknowns = ["demanda verificable", "precios de mercado", "competidores", "perfil de cliente concreto"]
        evidences: list[dict[str, Any]] = [
            {
                "evidence_type": "demand_signal",
                "source_name": "(modo offline — sin investigación externa)",
                "source_url": None,
                "summary": "DESCONOCIDO: no se ha recopilado evidencia externa verificada de demanda en modo sin API. Este dato debe investigarse manualmente (o con Gemini) antes de aprobar.",
                "raw_excerpt": None,
                "reliability_score": 0.0,
                "independence_group": "none",
                "verified": False,
                "verification_notes": "Entrada generada por el proveedor simulado: marca el dato como desconocido, no lo inventa.",
                "method": "mock",
            }
        ]
        if _is_mql5(problem):
            evidences.insert(
                0,
                {
                    "evidence_type": "technical",
                    "source_name": "Texto aportado por el usuario (no verificado)",
                    "source_url": None,
                    "summary": "El problema menciona la plataforma MQL5/MetaTrader: la oportunidad depende de esa plataforma externa. Revisar sus términos de servicio sobre automatización.",
                    "raw_excerpt": None,
                    "reliability_score": 0.4,
                    "independence_group": "user-input",
                    "verified": False,
                    "verification_notes": "Hecho extraído literalmente del texto de entrada; sin verificación externa.",
                    "method": "mock",
                },
            )
        return LLMResponse(
            text="Investigación simulada: los datos externos quedan marcados como desconocidos.",
            structured={"evidences": evidences, "competitors": [], "target_customer": None, "unknowns": unknowns},
            model="mock-deterministic",
            method="mock (deterministic, offline)",
            cost_estimate_usd=0.0,
            cost_method="zero (offline)",
        )

    def _task_skeptic(self, prompt: str, system: str | None) -> LLMResponse:
        ctx = system or prompt
        verified_m = re.findall(r"VERIFIED_(\d+)", ctx)
        unknown_m = re.findall(r"UNKNOWN_(\d+)", ctx)
        n_verified = int(verified_m[0]) if verified_m else 0
        n_unknown = int(unknown_m[0]) if unknown_m else 0

        if n_verified == 0:
            critique = (
                "No hay ninguna evidencia verificada. La demanda, los precios, los competidores y el perfil "
                "de cliente son desconocidos: no se puede afirmar que exista un mercado real. Una idea bien "
                "redactada no es una oportunidad demostrada."
            )
            objections = [
                "No existe demanda verificada: el dato está marcado como desconocido.",
                "No hay precio de mercado observado: el margen es pura especulación.",
                "Sin competidores identificados no se puede calcular diferenciación.",
            ]
        else:
            critique = (
                "Existe algo de evidencia, pero la mayoría de los datos clave siguen siendo estimaciones o "
                "desconocidos. El plan debe reducir las incógnitas antes de gastar dinero."
            )
            objections = ["La evidencia existente es limitada o de fiabilidad media.", "Las estimaciones económicas no están verificadas."]

        return LLMResponse(
            text=critique,
            structured={
                "critique": critique,
                "objections": objections,
                "weakest_assumptions": [f"Supuesto sin verificar: {u}" for u in range(n_unknown)] or ["Sin suposiciones declaradas."],
                "counterpoints": [],
            },
            model="mock-deterministic",
            method="mock (deterministic, offline)",
            cost_estimate_usd=0.0,
            cost_method="zero (offline)",
        )

    def _task_economist(self, prompt: str, system: str | None) -> LLMResponse:
        prices = [float(x) for x in re.findall(r"PRICE_([\d.]+)", prompt)]
        if prices:
            median = sorted(prices)[len(prices) // 2]
            if median > 0:
                price_low, price_high = round(median * 0.8, 2), round(median * 1.5, 2)
                price_note = "estimación basada en precios observados de competidores"
            else:
                price_low = price_high = None
                price_note = "DESCONOCIDO: solo hay alternativas gratuitas; sin precio de mercado observado"
        else:
            price_low = price_high = None
            price_note = "DESCONOCIDO: no hay precios observados guardados"

        margin = {"low": 55, "high": 85} if price_low else {"low": None, "high": None}

        return LLMResponse(
            text="Estimaciones económicas deterministas (todas marcadas como estimación).",
            structured={
                "estimates": {
                    "price_low_usd": price_low,
                    "price_high_usd": price_high,
                    "margin_low_pct": margin["low"],
                    "margin_high_pct": margin["high"],
                    "recurrence": "uno a uno (servicio puntual); posible retención con informes recurrentes",
                    "time_to_first_sale_days": 30,
                    "initial_spend_level": "bajo",
                    "reachability": "DESCONOCIDO: no hay canales verificados para llegar a compradores en modo offline",
                },
                "assumptions": [
                    f"Precio: {price_note}.",
                    "Margen estimado para servicios digitales (55-85%) si el precio se confirma; sin confirmar es desconocido.",
                ],
            },
            model="mock-deterministic",
            method="mock (deterministic, offline)",
            cost_estimate_usd=0.0,
            cost_method="zero (offline)",
        )

    def _task_builder(self, prompt: str, system: str | None) -> LLMResponse:
        ctx = (system or prompt).lower()
        if _is_mql5(ctx):
            complexity, days_lo, days_hi = "media", 5, 15
            deps = ["python", "parseo de logs de MetaTrader (formato a validar)", "plantillas de informe"]
        else:
            complexity, days_lo, days_hi = "baja", 2, 7
            deps = ["python"]
        rate = 50.0  # tasa diaria asumida (estimación)
        return LLMResponse(
            text="Estimación de construcción determinista (estimación).",
            structured={
                "estimates": {
                    "complexity": complexity,
                    "build_days_low": days_lo,
                    "build_days_high": days_hi,
                    "build_cost_low_usd": round(days_lo * rate, 2),
                    "build_cost_high_usd": round(days_hi * rate, 2),
                    "dependencies": deps,
                    "automation_degree": 80 if _is_mql5(ctx) else 70,
                    "automatable_steps": ["análisis de logs", "generación de informes", "validación de parámetros", "detección de errores de reentrada"],
                    "platform_dependencies": ["MetaTrader / MQL5"] if _is_mql5(ctx) else [],
                },
                "assumptions": ["Tasa diaria asumida de 50 USD/día (estimación).", "Complejidad estimada por heurística de sector."],
            },
            model="mock-deterministic",
            method="mock (deterministic, offline)",
            cost_estimate_usd=0.0,
            cost_method="zero (offline)",
        )

    def _task_compliance(self, prompt: str, system: str | None) -> LLMResponse:
        ctx = (system or prompt).lower()
        risks: list[dict[str, Any]] = [
            {
                "category": "asesoramiento_financiero",
                "severity": "medium",
                "description": "El sector trading/MQL5 roza el asesoramiento financiero. El servicio debe analizar software y calidad de backtest, nunca prometer rentabilidad ni dar consejos de inversión.",
                "mitigation": "Aviso legal en la interfaz: 'análisis de software, no asesoramiento financiero'. Prohibir promesas de rentabilidad en textos y ejemplos.",
                "blocker": False,
            },
            {
                "category": "tos_plataforma",
                "severity": "medium",
                "description": "La solución depende de MetaTrader/MQL5; hay que verificar que la automatización del análisis de logs no viole sus términos de servicio.",
                "mitigation": "Revisar los términos de MQL5/MetaTrader antes de escalar; documentar la conformidad.",
                "blocker": False,
            },
            {
                "category": "privacidad",
                "severity": "low",
                "description": "Los logs pueden contener datos de cuenta. Minimizar retención y permitir borrado.",
                "mitigation": "Procesar localmente; no almacenar más de lo necesario; anonimizar.",
                "blocker": False,
            },
        ]
        if re.search(
            r"rentabilidad garantizada|rentabilidad asegurada|ganancia garantizada|ganancias garantizadas|ganar dinero fácil|ingresos garantizados|promete rentabilidad|rentabilidad del \d+%|beneficios garantizados",
            ctx,
        ):
            risks.append(
                {
                    "category": "promesa_financiera",
                    "severity": "high",
                    "description": "La propuesta promete resultados económicos. Riesgo grave de fraude/regulación financiera.",
                    "mitigation": "Eliminar cualquier promesa de rentabilidad; si persiste, bloquear la oportunidad.",
                    "blocker": True,
                }
            )
        return LLMResponse(
            text="Riesgos de cumplimiento detectados (heurística determinista).",
            structured={"risks": risks, "blockers": [r["description"] for r in risks if r["blocker"]]},
            model="mock-deterministic",
            method="mock (deterministic, offline)",
            cost_estimate_usd=0.0,
            cost_method="zero (offline)",
        )

    def health(self) -> dict[str, Any]:
        return {"name": self.name, "available": True, "mode": "deterministic offline, coste 0"}
