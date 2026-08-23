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
import json
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


# Lente -> arquetipos compatibles (para el generador de conceptos offline).
LENS_ARCHETYPE_MAP: dict[str, list[str]] = {
    "REMOVE_THE_MIDDLEMAN": ["MARKETPLACE", "REVERSE_MARKETPLACE", "FRAGMENTED_DEMAND_BUNDLER"],
    "PAY_FOR_OUTCOME": ["PAY_FOR_RESULT", "SOFTWARE_ENABLED_SERVICE"],
    "REVERSE_MARKETPLACE": ["REVERSE_MARKETPLACE", "MARKETPLACE"],
    "LIVE_DIGITAL_TWIN": ["VERTICAL_SAAS", "PRO_TOOL"],
    "TRUST_LAYER": ["TRUST_PRODUCT", "VERIFICATION_TOOL"],
    "PROOF_BEFORE_PAYMENT": ["VALIDABLE_CONCIERGE", "SOFTWARE_ENABLED_SERVICE"],
    "UNUSED_ASSET_TO_INCOME": ["IDLE_ASSET_INCOME", "LOCAL_PRODUCT"],
    "HUMAN_PLUS_AI_SERVICE": ["SOFTWARE_ENABLED_SERVICE", "VALIDABLE_CONCIERGE"],
    "AI_AGENT_INFRASTRUCTURE": ["AGENT_INFRASTRUCTURE", "AGENT_SERVICE_PROVIDER", "API"],
    "COMMUNITY_AS_PRODUCT": ["COMMUNITY_PLATFORM", "BENCHMARKING_NETWORK"],
    "DATA_COOPERATIVE": ["DATA_PRODUCT", "ACCUMULATIVE_DATASET"],
    "AUTOMATE_THE_HANDOFF": ["VERTICAL_SAAS", "PRO_TOOL", "API"],
    "TURN_COMPLIANCE_INTO_PRODUCT": ["SOFTWARE_ENABLED_SERVICE", "VERTICAL_SAAS"],
    "PERSONAL_MEMORY_ASSET": ["ACCUMULATIVE_DATASET", "SUBSCRIPTION"],
    "MARKETPLACE_WITHOUT_LISTINGS": ["MARKETPLACE", "REVERSE_MARKETPLACE"],
    "PREDICT_BEFORE_PROBLEM": ["VERTICAL_SAAS", "SAVINGS_PRODUCT"],
    "BUNDLE_FRAGMENTED_DEMAND": ["FRAGMENTED_DEMAND_BUNDLER", "MARKETPLACE"],
    "UNBUNDLE_EXPENSIVE_SERVICE": ["SOFTWARE_ENABLED_SERVICE", "VALIDABLE_CONCIERGE"],
    "SELL_SAVED_TIME": ["PROSUMER_PRODUCT", "SUBSCRIPTION", "LOCAL_PRODUCT"],
    "SELL_REDUCED_RISK": ["TRUST_PRODUCT", "SAVINGS_PRODUCT"],
    "VERIFY_THE_OUTPUT": ["VERIFICATION_TOOL", "API"],
    "CREATE_A_NEW_RITUAL": ["SUBSCRIPTION", "COMMUNITY_PLATFORM"],
    "ENTERTAINMENT_PLUS_UTILITY": ["PROSUMER_PRODUCT", "TRANSACTIONAL_PRODUCT"],
    "PUBLIC_PROGRESS_LOOP": ["COLLABORATIVE_TOOL", "COMMUNITY_PLATFORM"],
    "CUSTOMER_BECOMES_DISTRIBUTION": ["COLLABORATIVE_TOOL", "COMMUNITY_PLATFORM"],
    "PRODUCT_IMPROVES_WITH_USE": ["ACCUMULATIVE_DATASET", "DATA_PRODUCT"],
    "SERVICE_TO_SOFTWARE_PATH": ["VALIDABLE_CONCIERGE", "SOFTWARE_ENABLED_SERVICE"],
    "MACHINE_TO_MACHINE_SERVICE": ["API", "AGENT_SERVICE_PROVIDER"],
    "LOCAL_FIRST_ADVANTAGE": ["LOCAL_PRODUCT"],
    "TEMPORARY_MICRO_MARKET": ["TRANSACTIONAL_PRODUCT", "FRAGMENTED_DEMAND_BUNDLER"],
}


def _pick_archetype_for_lens(lens_key: str, seed: str) -> Any:
    from app.core import libraries

    candidates = LENS_ARCHETYPE_MAP.get(lens_key, ["VERTICAL_SAAS", "SOFTWARE_ENABLED_SERVICE"])
    pick = _stable_pick(seed, candidates)
    return libraries.get_archetype(pick) or libraries.ARCHETYPES[0]


def _compose_concept(territory: Any, lens: Any, archetype: Any) -> dict[str, Any]:
    """Compone un concepto breve (hipótesis) a partir de la biblioteca."""
    mechanism = (
        f"{lens.mechanism} aplicado al territorio '{territory.name}': un servicio/activo basado en "
        f"el arquetipo {archetype.name.lower()} que resuelve la tensión concreto sin prometer resultados no verificables."
    )
    problem = (
        f"En '{territory.name}' ({territory.description}) existe una tensión hipotética: {territory.why_now} "
        "La hipótesis de problema debe validarse con una misión de investigación; no se asume demanda."
    )
    return {
        "title": f"{lens.name} para {territory.name.lower()}",
        "territory_key": territory.key,
        "lens_keys": [lens.key],
        "archetype_key": archetype.key,
        "problem_hypothesis": problem,
        "mechanism": mechanism,
        "buyer_hypothesis": (
            f"HIPÓTESIS (no evidencia): profesional o pequeña organización que sufre '{territory.name.lower()}' "
            f"({territory.description.lower()}) y ya dedica tiempo o dinero a resolverlo a mano. "
            "PENDIENTE de investigación con misión para confirmar comprador real."
        ),
        "outcome_hypothesis": (
            "HIPÓTESIS (no evidencia): resultado medible en tiempo, coste o riesgo dentro del territorio. "
            "PENDIENTE de definir métrica y umbral con datos reales."
        ),
        "why_now": territory.why_now,
        "general_ai_risk": "Pendiente de evaluación por el General AI Substitution Test (no se asume defensa).",
        "asset_potential": "Hipótesis de activo acumulativo a confirmar (datos, workflow o red del territorio).",
    }


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

    # ------------------------------------------------------------------
    # Business Discovery Engine (iteración 004)
    # ------------------------------------------------------------------
    def _task_discover_phase1(self, prompt: str, system: str | None) -> LLMResponse:
        """Genera conceptos breves combinando territorio x lente x arquetipo.

        Los conceptos son HIPÓTESIS: el proveedor simulado no inventa demanda,
        precios ni competidores (esos campos se dejan en None o se marcan
        como pendientes de investigación).
        """
        from app.core import libraries
        from app.scoring.venture import stable_seed

        config = json.loads(system or "{}")
        territories = [
            t
            for t in libraries.TERRITORIES
            if not config.get("territories") or t.key in config["territories"]
        ]
        lenses = [
            l
            for l in libraries.LENSES
            if not config.get("lenses") or l.key in config["lenses"]
        ]
        target = int(config.get("target", 60))
        n_wrappers = min(3, max(1, target // 10))
        concepts: list[dict[str, Any]] = []
        # Controles de comoditización primero (reservan hueco): wrappers obvios
        # para que el filtro demuestre que bloquea prompt-wrappers (una IA
        # generalista resuelve el problema sin workflow, integración ni memoria).
        for i in range(n_wrappers):
            territory = territories[stable_seed(f"wrapper:{i}") % len(territories)]
            archetype = libraries.get_archetype("PROSUMER_PRODUCT") or libraries.ARCHETYPES[0]
            concepts.append(
                {
                    "title": f"Chat genérico que genera contenido para {territory.name.lower()}",
                    "territory_key": territory.key,
                    "lens_keys": ["ENTERTAINMENT_PLUS_UTILITY"],
                    "archetype_key": archetype.key,
                    "problem_hypothesis": f"HIPÓTESIS: la gente en '{territory.name}' necesita contenido o respuestas genéricas sobre el tema ({territory.description}).",
                    "mechanism": "Un chat que genera contenido e informes genéricos a partir de la información que el cliente pega: el cliente podría obtener el mismo resultado pegando su información en ChatGPT, Gemini o Claude directamente.",
                    "buyer_hypothesis": f"HIPÓTESIS (no evidencia): persona interesada en '{territory.name}' que hoy usa una IA generalista gratuita. PENDIENTE de investigación.",
                    "outcome_hypothesis": None,
                    "why_now": "La proliferación de IA generalista hace trivial generar contenido genérico.",
                    "general_ai_risk": "ALTO: esto es un prompt envuelto; una IA generalista resuelve el problema.",
                    "asset_potential": "Ninguno: sin datos, sin workflow, sin memoria acumulativa.",
                }
            )
        remaining = target - n_wrappers
        for territory in territories:
            # Dos lentes distintas por territorio, elegidas de forma determinista.
            pick_idx = [stable_seed(f"{territory.key}:{i}") % len(lenses) for i in range(2)]
            if len(lenses) > 1 and pick_idx[0] == pick_idx[1]:
                pick_idx[1] = (pick_idx[1] + 1) % len(lenses)
            picks = [lenses[i] for i in pick_idx]
            for lens in picks:
                archetype = _pick_archetype_for_lens(lens.key, f"{territory.key}:{lens.key}")
                concepts.append(_compose_concept(territory, lens, archetype))
                if len(concepts) >= target:
                    break
            if len(concepts) >= target:
                break
        return LLMResponse(
            text=f"{len(concepts)} conceptos hipotéticos generados de forma determinista (sin API).",
            structured={"concepts": concepts[:target]},
            model="mock-deterministic",
            method="mock (deterministic, offline)",
            cost_estimate_usd=0.0,
            cost_method="zero (offline)",
        )

    def _task_discover_recombine(self, prompt: str, system: str | None) -> LLMResponse:
        """Cruza mecanismos de conceptos que pasaron el filtro (fase 3)."""
        from app.core import libraries
        from app.scoring.venture import stable_seed

        base = json.loads(system or "[]")
        concepts: list[dict[str, Any]] = []
        if len(base) >= 2:
            for i in range(min(6, len(base) // 2)):
                a = base[stable_seed(f"a:{i}") % len(base)]
                b = base[stable_seed(f"b:{i}:{a['id']}") % len(base)]
                if a["id"] == b["id"]:
                    b = base[(stable_seed(f"b:{i}:{a['id']}") + 1) % len(base)]
                territory = libraries.get_territory(a.get("territory_key") or "") or libraries.TERRITORIES[0]
                lens = libraries.get_lens("REMOVE_THE_MIDDLEMAN") or libraries.LENSES[0]
                archetype = _pick_archetype_for_lens("UNBUNDLE_EXPENSIVE_SERVICE", f"recombine:{i}")
                concepts.append(
                    {
                        "title": f"{b.get('title', 'Mecanismo')} adaptado a {territory.name}",
                        "territory_key": territory.key,
                        "lens_keys": [lens.key],
                        "archetype_key": archetype.key,
                        "problem_hypothesis": f"El mecanismo de '{b.get('title', 'la idea origen')}' aplicado al territorio '{territory.name}': {territory.description} {territory.why_now}",
                        "mechanism": f"{b.get('mechanism', '')} — adaptado al territorio '{territory.name}' usando el arquetipo {archetype.name.lower()} para eliminar el coste de coordinación.",
                        "buyer_hypothesis": f"Comprador hipotético en el territorio '{territory.name}' (PENDIENTE de investigación con misión).",
                        "outcome_hypothesis": "Resultado hipotético: tiempo o coste reducido medible en el territorio (PENDIENTE de definir umbral).",
                        "why_now": territory.why_now,
                        "general_ai_risk": "Riesgo de comoditización por IA generalista: depende del arquetipo; evaluado por el General AI Substitution Test.",
                        "asset_potential": "Activo hipotético: proceso o dato acumulado del territorio (PENDIENTE de verificar).",
                    }
                )
        return LLMResponse(
            text=f"{len(concepts)} conceptos recombinados (determinista, sin API).",
            structured={"concepts": concepts},
            model="mock-deterministic",
            method="mock (deterministic, offline)",
            cost_estimate_usd=0.0,
            cost_method="zero (offline)",
        )

    def health(self) -> dict[str, Any]:
        return {"name": self.name, "available": True, "mode": "deterministic offline, coste 0"}
