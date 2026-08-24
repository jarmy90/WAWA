"""Ventana prioritaria "OX Alpha" (iteración 015).

El propietario dispone de acceso gratuito TEMPORAL (hasta 2026-08-27,
inclusive) a un modelo que denomina "OX Alpha" a través del gateway local
OmniRoute. Este módulo implementa la PUERTA determinista que decide si una
tarea profunda puede usarlo, SIN inventar nada:

Reglas inmutables:
1. IDENTIFICACIÓN: el slug exacto SOLO se acepta si el propietario lo fija en
   ``OX_ALPHA_SLUG`` tras verificarlo contra el catálogo real del gateway
   (GET {base_url}/models). Vacío => identidad ``OX_ALPHA_UNVERIFIED`` y
   NUNCA se declara que se ha usado OX Alpha. ``auto`` NO cuenta como
   OX Alpha (regla de la iteración 008).
2. EXPIRACIÓN: pasado ``ox_alpha_expires_at`` (2026-08-27 inclusive) la
   puerta se cierra sola. Ningún flujo depende obligatoriamente de OX Alpha.
3. NO ES EVIDENCIA: toda salida se etiqueta MODEL_REASONING /
   MODEL_HYPOTHESIS / MODEL_CRITIQUE / MODEL_REFORMULATION. Jamás puede
   subir proven_demand, confirmar comprador/precio/canal, crear grupo
   independiente de evidencia, aprobar finalistas, iniciar PRE_CYCLE,
   autorizar gasto o sustituir misiones web con fuentes reales.
4. FALLO = AUSENCIA NEUTRAL: si OX Alpha falla no se fabrica salida ni se
   sustituye silenciosamente por mock; el fallo queda registrado en
   llm_call_log y la interfaz muestra qué modelo respondió realmente.

Tareas reservadas (P0) — nunca tareas mecánicas/deterministas:
- reformulation: convertir concepto abstracto en Opportunity Brief concreto.
- coherence_check: detectar combinaciones territorio+lente+arquetipo sin
  relación causal comercial.
- red_team: intentar destruir la propuesta (10 preguntas fijas).
- variation_comparison: comparación por pares; puede recomendar 0 candidatas.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

OX_ALPHA_UNVERIFIED = "OX_ALPHA_UNVERIFIED"

# Etiquetas HONESTAS permitidas en la interfaz (iteración 015, sección 7).
ALLOWED_OUTPUT_LABELS = (
    "REFORMULACIÓN DE MODELO",
    "CRÍTICA DE MODELO",
    "HIPÓTESIS SIN VERIFICAR",
)
# Etiquetas PROHIBIDAS: nunca se muestran (se testean).
FORBIDDEN_OUTPUT_LABELS = (
    "VALIDADA POR OX ALPHA",
    "DEMANDA CONFIRMADA POR OX ALPHA",
    "APROBADA POR OMNIROUTE",
)

# Tareas profundas P0 que pueden usar la ventana (nada mecánico entra aquí).
DEEP_TASKS = ("reformulation", "coherence_check", "red_team", "variation_comparison")

TASK_LABEL: dict[str, str] = {
    "reformulation": "REFORMULACIÓN DE MODELO",
    "coherence_check": "CRÍTICA DE MODELO",
    "red_team": "CRÍTICA DE MODELO",
    "variation_comparison": "CRÍTICA DE MODELO",
}


def _parse_expires(value: str) -> date | None:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return None


def ox_alpha_status(settings: Any, *, today: date | None = None) -> dict[str, Any]:
    """Estado determinista de la puerta OX Alpha (sin llamadas de red).

    Devuelve siempre: identity, state, can_use, reason, expires_at, slug,
    is_evidence=False. La identidad SOLO es el slug verificado; en cualquier
    otro caso es OX_ALPHA_UNVERIFIED y can_use=False.
    """
    today = today or date.today()
    expires = _parse_expires(getattr(settings, "ox_alpha_expires_at", "") or "")
    slug = (getattr(settings, "ox_alpha_slug", "") or "").strip()
    enabled = bool(getattr(settings, "omniroute_enabled", False))

    identity = slug if slug and slug.lower() != "auto" else OX_ALPHA_UNVERIFIED

    if not enabled:
        state = "GATEWAY_DISABLED"
        reason = "OMNIROUTE_ENABLED=false: el gateway local no está activado."
    elif expires is None:
        state = "CONFIG_INVALID"
        reason = "ox_alpha_expires_at no es una fecha AAAA-MM-DD válida."
    elif today > expires:
        state = "WINDOW_EXPIRED"
        reason = f"La ventana gratuita terminó el {expires.isoformat()}; OmniRoute vuelve a su routing habitual."
    elif not slug or slug.lower() == "auto":
        state = "SLUG_UNVERIFIED"
        reason = (
            "Sin slug verificado contra el catálogo del gateway: identidad "
            f"{OX_ALPHA_UNVERIFIED}. No se declara uso de OX Alpha."
        )
    else:
        state = "AVAILABLE"
        days_left = max(0, (expires - today).days)
        reason = f"Ventana activa hasta {expires.isoformat()} ({days_left} días restantes)."

    return {
        "identity": identity,
        "state": state,
        "can_use": state == "AVAILABLE",
        "reason": reason,
        "expires_at": getattr(settings, "ox_alpha_expires_at", None),
        "slug_configured": bool(slug),
        "is_evidence": False,
        "output_labels_allowed": list(ALLOWED_OUTPUT_LABELS),
        "output_labels_forbidden": list(FORBIDDEN_OUTPUT_LABELS),
    }


def deep_task_gate(settings: Any, task: str, *, today: date | None = None) -> dict[str, Any]:
    """Puerta por tarea: solo tareas P0 registradas pueden usar la ventana."""
    status = ox_alpha_status(settings, today=today)
    if task not in DEEP_TASKS:
        return {
            **status,
            "task": task,
            "can_use": False,
            "reason": f"Tarea '{task}' no está reservada para razonamiento profundo "
                      f"(permitidas: {', '.join(DEEP_TASKS)}). Usar filtros deterministas.",
        }
    return {**status, "task": task}


# ----------------------------------------------------------------------
# Constructores de prompt (expediente mínimo, sin secretos ni datos personales)
# ----------------------------------------------------------------------
_BRIEF_FIELDS = [
    "specific_name", "user", "buyer", "situation", "observable_problem",
    "current_alternative", "economic_or_time_cost", "concrete_deliverable",
    "measurable_outcome", "revenue_model", "expected_price_hypothesis",
    "first_distribution_channel", "first_20_buyers_location", "test_in_48_hours",
    "generic_ai_limitation", "compounding_asset", "primary_risk",
    "assumptions", "prohibited_claims",
]

_RED_TEAM_QUESTIONS = [
    "¿Es solo una frase atractiva sin producto detrás?",
    "¿Es una simple función que cualquiera copia?",
    "¿Una IA generalista resuelve el 80% con un prompt?",
    "¿Existe comprador identificable (no solo usuario)?",
    "¿Existe motivo URGENTE y recurrente para pagar?",
    "¿La distribución inicial es plausible sin spam?",
    "¿La supuesta ventaja es real o decorativa?",
    "¿Puede probarse por menos de 10 USD?",
    "¿Puede entregarse primero como servicio manual?",
    "¿Qué dato objetivo obligaría a descartarla?",
]

_SYSTEM_BASE = (
    "Eres un crítico de negocio riguroso. Tu salida es RAZONAMIENTO DE MODELO: "
    "hipótesis y crítica, NUNCA evidencia de mercado. Prohibido inventar demanda, "
    "precios observados, clientes, estadísticas o fuentes. Todo precio/canal/comprador "
    "que propongas debe marcarse como HIPÓTESIS SIN VERIFICAR. Responde SOLO con JSON válido."
)


def build_reformulation_prompt(concept: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Convierte un concepto abstracto en brief concreto (3-5 variantes)."""
    payload = {
        "title": concept.get("title") or "",
        "problem_hypothesis": concept.get("problem_hypothesis") or "",
        "buyer_hypothesis": concept.get("buyer_hypothesis") or "",
        "outcome_hypothesis": concept.get("outcome_hypothesis") or "",
        "mechanism_hypothesis": concept.get("mechanism_hypothesis") or "",
    }
    instructions = (
        "Genera entre 3 y 5 REFORMULACIONES REALMENTE DIFERENTES de este concepto abstracto. "
        "Cada variante debe cambiar SUSTANCIALMENTE segmento, comprador, problema observable, "
        "entrega concreta, canal y modelo de cobro (no vale cambiar el título). "
        "Campos obligatorios por variante: " + ", ".join(_BRIEF_FIELDS) + ".\n"
        "Devuelve JSON: {\"variants\": [ {" + ", ".join(_BRIEF_FIELDS) +
        ", \"causal_chain\": \"str\", \"why_someone_pays\": \"str\"} ], \"discard_reason\": \"str|null\"}"
    )
    return f"{instructions}\n\nCONCEPTO:\n{payload}", {"type": "object", "required": ["variants"]}


def build_coherence_prompt(concept: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Detecta combinaciones territorio+lente+arquetipo sin relación causal."""
    payload = {
        "title": concept.get("title") or "",
        "problem_hypothesis": concept.get("problem_hypothesis") or "",
        "mechanism_hypothesis": concept.get("mechanism_hypothesis") or "",
        "territory": concept.get("territory_key") or concept.get("territory") or "",
        "lens": concept.get("lens_key") or concept.get("lens") or "",
        "archetype": concept.get("archetype_key") or concept.get("archetype") or "",
    }
    instructions = (
        "Analiza si existe una RELACIÓN CAUSAL Y COMERCIAL comprensible entre territorio, "
        "lente y arquetipo (no una yuxtaposición artificial tipo 'X adaptado a Y'). "
        "Explica: relación causal (o su ausencia), producto concreto que surgiría, "
        "por qué alguien pagaría (hipótesis), o por qué debe descartarse.\n"
        "Devuelve JSON: {\"coherent\": \"bool\", \"causal_relation\": \"str|null\", "
        "\"concrete_product\": \"str|null\", \"why_pay\": \"str|null\", \"discard_reason\": \"str|null\"}"
    )
    return f"{instructions}\n\nCONCEPTO:\n{payload}", {"type": "object", "required": ["coherent"]}


def build_red_team_prompt(concept: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Intenta demostrar que la propuesta no vale (10 preguntas fijas)."""
    payload = {
        "title": concept.get("title") or "",
        "problem_hypothesis": concept.get("problem_hypothesis") or "",
        "buyer_hypothesis": concept.get("buyer_hypothesis") or "",
        "outcome_hypothesis": concept.get("outcome_hypothesis") or "",
        "brief": concept.get("brief") or {},
    }
    questions = "\n".join(f"{i+1}. {q}" for i, q in enumerate(_RED_TEAM_QUESTIONS))
    instructions = (
        "Actúa como red-team: intenta DESTRUIR esta propuesta respondiendo a cada pregunta "
        "con verdict (fatal|weak|ok) y justificación breve basada SOLO en lo proporcionado.\n"
        f"{questions}\n"
        "Devuelve JSON: {\"answers\": [{\"question\": \"str\", \"verdict\": \"fatal|weak|ok\", "
        "\"justification\": \"str\"}], \"overall\": \"kill|needs_reformulation|proceed\", "
        "\"cheapest_test\": \"str|null\", \"discarding_data\": \"str|null\"}"
    )
    return f"{instructions}\n\nPROPUESTA:\n{payload}", {"type": "object", "required": ["answers", "overall"]}


def build_variation_comparison_prompt(concepts: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    """Compara reformulaciones por pares; 0 candidatas es respuesta válida."""
    slim = [
        {"id": c.get("concept_id") or c.get("id"), "title": c.get("title"),
         "buyer": (c.get("brief") or {}).get("buyer") or c.get("buyer_hypothesis"),
         "deliverable": (c.get("brief") or {}).get("concrete_deliverable")}
        for c in concepts[:15]  # tope defensivo: nunca las 66 combinaciones completas
    ]
    instructions = (
        "Compara estas reformulaciones y selecciona como máximo 3 merecedoras de "
        "investigación limitada (0 es una respuesta válida). Justifica cada selección y "
        "cada descarte. Criterios: especificidad del comprador, concreción del problema, "
        "coherencia causal, prueba de 48h definible, resistencia frente a IA generalista.\n"
        "Devuelve JSON: {\"selected\": [\"id\"], \"rejected\": [{\"id\": \"str\", "
        "\"reason\": \"str\"}], \"max_selected\": 3}"
    )
    return f"{instructions}\n\nCANDIDATAS:\n{slim}", {"type": "object", "required": ["selected"]}
