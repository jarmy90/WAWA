"""Plantillas de misiones de investigación Freebuff-first (iteración 006).

Cada misión define preguntas exactas, consultas sugeridas, fuentes
prioritarias y débiles, criterio de evidencia y el esquema JSON reimportable.
Las misiones las ejecuta Freebuff DENTRO de una sesión; sus conclusiones solo
son demanda verificada si incluyen URL concreta + fecha de consulta +
fragmento breve (regla de no invención).
"""
from __future__ import annotations

from typing import Any

from app.models.campaign import ResearchMissionType

MISSION_TEMPLATES: dict[str, dict[str, Any]] = {
    ResearchMissionType.demand_reality_check.value: {
        "objective": "Comprobar si existe demanda REAL y observable del problema, no solo hipótesis.",
        "questions": [
            "¿Dónde expresa la gente este problema hoy (foros, reviews, tickets, comunidades)?",
            "¿Con qué frecuencia y con qué intensidad emocional/económica lo expresan?",
            "¿Qué hacen hoy para resolverlo (o lo ignoran)?",
            "¿Cuántas personas/organizaciones distintas lo manifiestan de forma independiente?",
        ],
        "suggested_queries": [
            '"{problema}" forum OR reddit OR "help"',
            '"{frase del dolor" how to fix',
            '"{sector}" problem "{síntoma}"',
        ],
        "priority_sources": ["foros sectoriales", "Reddit/Stack Exchange", "reviews de productos alternativos", "tickets de soporte públicos", "grupos de la industria"],
        "weak_or_prohibited_sources": ["listas de ideas generadas por IA", "artículos de contenido genérico", "predicciones de mercado sin fuente"],
        "evidence_criteria": "Mínimo 3 manifestaciones independientes con URL + fecha + fragmento.",
        "required_unknowns": ["volumen total no cuantificado", "intensidad de pago no verificada"],
        "json_schema": {"evidences": [{"source_url": "str", "consulted_at": "iso-date", "fragment": "str", "primary_or_secondary": "str", "confidence": "0-100", "contradictions": "list[str]"}]},
    },
    ResearchMissionType.buyer_budget_check.value: {
        "objective": "Confirmar quién paga y de qué presupuesto saldría el dinero.",
        "questions": [
            "¿Quién es el comprador (no solo el usuario)?",
            "¿De qué línea presupuestaria saldría el pago (discrecional, operativa, proyecto)?",
            "¿Qué dispara la compra (evento, urgencia, hito)?",
            "¿Cuánto paga hoy por la alternativa actual?",
        ],
        "suggested_queries": [
            '"{rol}" budget "{problema}"',
            '"{alternativa actual}" price per month',
            '"{sector}" spend "{categoría}"',
        ],
        "priority_sources": ["entrevistas o encuestas", "ofertas públicas de la alternativa", "tarifas publicadas", "licitaciones/marketplaces"],
        "weak_or_prohibited_sources": ["estimaciones de TAM sin metodología", "supuestos de disposición a pagar sin evidencia"],
        "evidence_criteria": "Precio o presupuesto observado con URL + fecha, o entrevista documentada.",
        "required_unknowns": ["presupuesto real no confirmado", "ciclo de compra no medido"],
        "json_schema": {"buyer": {"role": "str", "budget_source": "str", "trigger_event": "str"}, "observed_price": {"value": "float|null", "currency": "str", "source_url": "str", "consulted_at": "iso-date"}},
    },
    ResearchMissionType.current_alternative_check.value: {
        "objective": "Documentar la alternativa real del cliente hoy (incluida 'no hacer nada').",
        "questions": [
            "¿Qué usa hoy el cliente para resolver el problema?",
            "¿Cuál es el coste (tiempo, dinero, riesgo) de la alternativa?",
            "¿Por qué la alternativa no basta?",
            "¿Cuál es el coste de NO resolverlo?",
        ],
        "suggested_queries": [
            '"{problema}" instead of',
            '"{alternativa}" limitations complaints',
            '"{problema}" "we do it manually"',
        ],
        "priority_sources": ["foros con hilos de comparación", "reviews de la alternativa", "testimonios de clientes"],
        "weak_or_prohibited_sources": ["comparativas patrocinadas", "listas genéricas de herramientas"],
        "evidence_criteria": "Alternativa identificada con 2+ referencias independientes.",
        "required_unknowns": ["coste exacto de la alternativa sin confirmar"],
        "json_schema": {"alternatives": [{"name": "str", "url": "str|null", "observed_cost": "str|null", "weakness": "str", "source_url": "str", "consulted_at": "iso-date"}]},
    },
    ResearchMissionType.general_ai_substitution_check.value: {
        "objective": "Verificar si una IA generalista (ChatGPT/Gemini/Claude/DeepSeek) resuelve el 80% del problema con un prompt.",
        "questions": [
            "¿Qué pasos del workflow del cliente puede hacer una IA generalista hoy, sin integración?",
            "¿Qué partes requieren datos, integración, memoria o ejecución que una IA generalista no tiene?",
            "¿Existe algún prompt público que ya lo resuelva?",
            "¿Qué mejorará o empeorará con la próxima generación de modelos?",
        ],
        "suggested_queries": [
            '"{problema}" chatgpt prompt',
            '"{problema}" "just ask AI" OR "AI can do this"',
            'site:reddit.com "{problema}" AI',
        ],
        "priority_sources": ["pruebas directas (ejecutar el prompt)", "hilos de usuarios usando IA para el problema", "documentación de capacidades de modelos"],
        "weak_or_prohibited_sources": ["opiniones de que 'la IA lo hará todo' sin prueba", "demostraciones editadas"],
        "evidence_criteria": "Resultado de prueba directa o hilo concreto con URL + fecha.",
        "required_unknowns": ["capacidad de modelos futuros no predecible"],
        "json_schema": {"substitution_test": {"generic_prompt_solves_80pct": "bool", "evidence_url": "str", "tested_at": "iso-date", "workflow_steps_ai_cannot_do": "list[str]"}},
    },
    ResearchMissionType.competitor_equivalent_search.value: {
        "objective": "Buscar equivalentes directos e indirectos del producto propuesto.",
        "questions": [
            "¿Quién ofrece ya exactamente lo mismo?",
            "¿Quién ofrece una parte (feature) suelta?",
            "¿Quién lo resuelve de forma manual (freelancers, agencias)?",
            "¿Qué precios publican?",
        ],
        "suggested_queries": [
            '"{solución}" service OR tool OR software',
            '"{problema}" solution price',
            '"{sector}" "{solución}" freelance',
        ],
        "priority_sources": ["marketplaces", "directorios de software", "páginas de precios públicas", "portafolios de freelancers"],
        "weak_or_prohibited_sources": ["listas de 'startups de IA' sin precios", "artículos de prensa sin datos"],
        "evidence_criteria": "3+ equivalentes con URL y, si es posible, precio observado.",
        "required_unknowns": ["cuota de mercado real", "precios con descuento no publicados"],
        "json_schema": {"competitors": [{"name": "str", "url": "str", "offer": "str", "observed_price": "float|null", "strengths": "list[str]", "weaknesses": "list[str]"}]},
    },
    ResearchMissionType.distribution_access_check.value: {
        "objective": "Verificar un canal concreto para llegar a los primeros 20 usuarios sin spam.",
        "questions": [
            "¿Dónde están exactamente los primeros 20 usuarios (comunidad, foro, gremio, evento)?",
            "¿Qué comportamiento existente se puede aprovechar (buscan, preguntan, compran algo)?",
            "¿Cómo descubren soluciones hoy?",
            "¿Es legal y compatible con las condiciones del canal?",
        ],
        "suggested_queries": [
            '"{sector}" community OR association OR group',
            '"{sector}" directory where they list services',
            '"{sector}" forum active "problema"',
        ],
        "priority_sources": ["foros con actividad verificable", "asociaciones/gremios", "eventos", "directorios sectoriales"],
        "weak_or_prohibited_sources": ["comprar listas de contactos", "spam/DDM", "canales que prohíban promoción"],
        "evidence_criteria": "Canal identificado con URL + evidencia de actividad reciente.",
        "required_unknowns": ["coste de adquisición real no medido"],
        "json_schema": {"channels": [{"name": "str", "url": "str", "activity_evidence": "str", "tos_compatible": "bool|null", "estimated_reach": "str"}]},
    },
    ResearchMissionType.moat_reality_check.value: {
        "objective": "Comprobar si la ventaja defendible propuesta es real o inventada.",
        "questions": [
            "¿Qué activo acumula el producto con cada uso (datos, memoria, red)?",
            "¿Puede un clon replicarlo en una tarde?",
            "¿Qué integraciones/costes de cambio existen realmente?",
            "¿Mejora el producto con cada cliente o ejecución?",
        ],
        "suggested_queries": [
            '"{solución}" how to build your own',
            '"{solución}" open source alternative',
            '"{solución}" API integration',
        ],
        "priority_sources": ["repositorios/alternativas open source", "documentación de integraciones", "análisis de productos similares"],
        "weak_or_prohibited_sources": ["afirmaciones de moat sin mecanismo concreto"],
        "evidence_criteria": "Mecanismo de ventaja identificado con fuente concreta o refutado con evidencia.",
        "required_unknowns": ["velocidad real de imitación no medible"],
        "json_schema": {"moat": {"type": "str|null", "evidence_url": "str|null", "clone_cost": "str", "compounding_asset": "str|null"}},
    },
    ResearchMissionType.data_availability_check.value: {
        "objective": "Verificar que los datos necesarios existen, son accesibles y son legales de usar.",
        "questions": [
            "¿Dónde están los datos que alimentarían el producto?",
            "¿Son accesibles (API, export, scraping permitido por ToS)?",
            "¿Está permitido usarlos comercialmente?",
            "¿Qué calidad/cobertura tienen?",
        ],
        "suggested_queries": [
            '"{fuente de datos}" API documentation',
            '"{fuente de datos}" terms of service data usage',
            '"{fuente de datos}" export CSV',
        ],
        "priority_sources": ["documentación oficial de APIs", "términos de servicio", "formatos públicos"],
        "weak_or_prohibited_sources": ["scraping contra robots.txt", "datos personales sin consentimiento", "bases pirata"],
        "evidence_criteria": "Fuente de datos identificada con URL oficial + nota de ToS.",
        "required_unknowns": ["calidad real de datos sin muestra"],
        "json_schema": {"data_sources": [{"name": "str", "url": "str", "access_method": "str", "tos_note": "str", "commercial_use_allowed": "bool|null"}]},
    },
    ResearchMissionType.tos_and_legal_check.value: {
        "objective": "Detectar riesgos legales, de plataforma y de privacidad antes de construir.",
        "questions": [
            "¿Qué términos de servicio afectan a la solución (plataforma, API, mercado)?",
            "¿Prohíben la automatización, la reventa de datos o el uso comercial?",
            "¿Es una actividad regulada (financiera, sanitaria, legal, seguros)?",
            "¿Qué datos personales se tratarían y con qué base legal?",
        ],
        "suggested_queries": [
            '"{plataforma}" terms of service automation',
            '"{plataforma}" prohibited use data scraping',
            '"{sector}" regulated activity requirements',
        ],
        "priority_sources": ["términos de servicio oficiales (URL + fecha)", "documentos regulatorios oficiales", "jurisprudencia/guías de autoridades"],
        "weak_or_prohibited_sources": ["opiniones legales de foros sin cualificación", "resúmenes de IA sin fuente"],
        "evidence_criteria": "Cláusula concreta con URL + fragmento + fecha de consulta.",
        "required_unknowns": ["interpretación legal no resuelta (consultar profesional si avanza)"],
        "json_schema": {"risks": [{"category": "str", "severity": "low|medium|high", "clause_or_rule": "str", "source_url": "str", "consulted_at": "iso-date", "blocker": "bool"}]},
    },
    ResearchMissionType.experiment_feasibility_check.value: {
        "objective": "Diseñar el experimento más barato posible y comprobar que es ejecutable.",
        "questions": [
            "¿Cuál es la versión manual mínima (concierge) que produce la misma señal?",
            "¿Qué se puede medir sin construir nada?",
            "¿Cuál es la métrica de éxito y el umbral?",
            "¿Qué condición objetiva obligaría a abandonar?",
        ],
        "suggested_queries": [
            '"{sector}" concierge validation example',
            '"{problema}" landing page waitlist',
            '"{sector}" pre-order or deposit',
        ],
        "priority_sources": ["ejemplos documentados de validación", "casos de concierge services", "reglas de marketplaces para pre-venta"],
        "weak_or_prohibited_sources": ["experimentos teóricos sin ejecutar"],
        "evidence_criteria": "Test mínimo definido con métrica, umbral y coste máximo.",
        "required_unknowns": ["señal real de compra pendiente de ejecutar"],
        "json_schema": {"experiment": {"hypothesis": "str", "cheapest_test": "str", "maximum_budget_usd": "float", "success_metric": "str", "success_threshold": "str", "failure_threshold": "str", "duration_days": "int"}},
    },
}


def get_mission_template(kind: str) -> dict[str, Any] | None:
    return MISSION_TEMPLATES.get(kind)


def mission_kinds() -> list[str]:
    return list(MISSION_TEMPLATES.keys())
