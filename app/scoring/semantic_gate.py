"""Puerta de calidad semántica (iteración 013).

Determinista, sin LLM. Sustituye etiquetas ambiguas por estados inequívocos,
bloquea expresiones genéricas, detecta recombinaciones incoherentes y separa
la puntuación estructural (pre-evidencia) de la puntuación de viabilidad con
evidencia.
"""
from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Estados inequívocos (en español, sin ambigüedad)
# ---------------------------------------------------------------------------
CONCEPT_STATUSES = (
    "GENERATED_HYPOTHESIS",           # Concepto generado mecánicamente. No evaluado.
    "DEDUP_PASSED",                   # Superó únicamente deduplicación.
    "AI_FILTER_PASSED",               # No fue bloqueado como commodity. No significa oportunidad válida.
    "STRUCTURAL_FILTER_PASSED",       # Cumple estructura mínima interna. No tiene evidencia.
    "RECOMBINATION_INCOHERENT",       # La recombinación no produce una propuesta comercial coherente.
    "DIVERSITY_ELIMINATED",           # Eliminada para conservar diversidad.
    "CONCEPTUAL_CLONE",               # Clon conceptual de otra idea.
    "COMMODITY_BLOCKED",              # Una IA generalista puede resolver la mayor parte.
    "NEEDS_REFORMULATION",            # Dirección interesante, pero no define negocio concreto.
    "RESEARCH_CANDIDATE",             # Idea concreta preparada para investigar.
    "RESEARCH_PENDING",               # Investigación externa pendiente.
    "EVIDENCE_INSUFFICIENT",          # Investigada, pero sin evidencia suficiente.
    "SHORTLISTED_WITH_EVIDENCE",      # Shortlist respaldada por evidencia real.
    "FINALIST",                       # Finalista después de investigación y reevaluación.
    "EXPERIMENT_READY",               # Preparada para experimento.
)

STATUS_MEANINGS: dict[str, str] = {
    "GENERATED_HYPOTHESIS": "Concepto generado mecánicamente. No evaluado.",
    "DEDUP_PASSED": "Superó únicamente deduplicación.",
    "AI_FILTER_PASSED": "No fue bloqueado como commodity. No significa oportunidad válida.",
    "STRUCTURAL_FILTER_PASSED": "Cumple estructura mínima interna. No tiene evidencia.",
    "RECOMBINATION_INCOHERENT": "La recombinación no produce una propuesta comercial coherente.",
    "DIVERSITY_ELIMINATED": "Eliminada para conservar diversidad.",
    "CONCEPTUAL_CLONE": "Clon conceptual de otra idea.",
    "COMMODITY_BLOCKED": "Una IA generalista puede resolver la mayor parte.",
    "NEEDS_REFORMULATION": "Dirección interesante, pero todavía no es una oportunidad concreta.",
    "RESEARCH_CANDIDATE": "Idea concreta preparada para investigar.",
    "RESEARCH_PENDING": "Investigación externa pendiente.",
    "EVIDENCE_INSUFFICIENT": "Investigada, pero sin evidencia suficiente.",
    "SHORTLISTED_WITH_EVIDENCE": "Shortlist respaldada por evidencia real.",
    "FINALIST": "Finalista después de investigación y reevaluación.",
    "EXPERIMENT_READY": "Preparada para experimento.",
}

# Estados que NUNCA deben mostrarse (eliminados en la iteración 013).
FORBIDDEN_STATUSES = ("passed", "promoted", "blocked", "eliminated", "shortlisted", "finalist", "clone", "draft", "recombined")

_OLD_TO_NEW: dict[str, str] = {
    "draft": "GENERATED_HYPOTHESIS",
    "passed": "AI_FILTER_PASSED",
    "recombined": "STRUCTURAL_FILTER_PASSED",
    "clone": "CONCEPTUAL_CLONE",
}

# ---------------------------------------------------------------------------
# Marcadores genéricos (bloquean la reformulación concreta)
# ---------------------------------------------------------------------------
GENERIC_MARKERS: tuple[str, ...] = (
    "profesional o pequeña organización",
    "persona interesada",
    "sufre el territorio",
    "resultado medible pendiente",
    "mecanismo aplicado al territorio",
    "comprador hipotético en el territorio",
    "servicio o activo basado en el arquetipo",
    "tensión hipotética",
    "valor para el colectivo",
    "solución innovadora",
    "adaptado a logística local",
    "adaptado a confianza digital",
    "adaptado a soledad y coordinación",
    "para el colectivo",
    "colectivo afectado",
    "los afectados",
    "usuarios en general",
    "cualquier negocio",
    "todo tipo de empresa",
    "empresas en general",
    "pymes y autónomos",
    "generar ingresos adicionales",
    "mejorar la eficiencia",
    "optimizar procesos",
    "digitalizar procesos",
    "plataforma integral",
    "solución integral",
    "ecosistema completo",
)


def has_generic_markers(*texts: str | None) -> list[str]:
    """Devuelve los marcadores genéricos encontrados en los textos."""
    hits: list[str] = []
    for text in texts:
        t = (text or "").lower()
        for marker in GENERIC_MARKERS:
            if marker in t and marker not in hits:
                hits.append(marker)
    return hits


# ---------------------------------------------------------------------------
# Coherencia semántica (determinista)
# ---------------------------------------------------------------------------
# Frases incoherentes reales detectadas en la campaña (deben fallar siempre).
INCOHERENT_EXAMPLES: tuple[str, ...] = (
    "capa de confianza para soledad y coordinación social no romántica adaptado a logística local",
    "prueba antes del pago para deporte amateur adaptado a confianza digital",
    "entretenimiento + utilidad para fraude y verificación adaptado a soledad y coordinación social no romántica",
)

_STOP = {
    "de", "la", "el", "los", "las", "un", "una", "unos", "unas", "que", "y", "o", "a", "en", "para", "con",
    "por", "del", "al", "se", "su", "sus", "como", "más", "mas", "ya", "ser", "hacer", "poder", "tener",
    "entre", "sobre", "sin", "no", "es", "son", "esta", "este", "app", "plataforma", "herramienta",
    "servicio", "producto", "sistema", "software", "adaptado", "adaptada", "aplicado", "aplicada",
    "basado", "basada", "orientado", "orientada", "para", "de", "la", "el", "los",
}


def _tokens(text: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-záéíóúñü0-9]+", (text or "").lower()) if w not in _STOP and len(w) > 2}


def _has_adaptado_pattern(title: str) -> tuple[bool, str]:
    """Detecta el patrón 'X para <contextoA> adaptado a <contextoB>' con A != B."""
    t = (title or "").lower()
    for ex in INCOHERENT_EXAMPLES:
        if ex in t:
            return True, "patrón de recombinación incoherente (ejemplo detectado)"
    m = re.search(r"(.+?)\s+adaptad[oa]\s+(?:a|para)\s+(.+)$", t)
    if not m:
        return False, ""
    left, right = m.group(1).strip(), m.group(2).strip()
    if not left or not right:
        return True, "patrón 'adaptado a' sin contexto"
    # Si las dos partes nombran territorios distintos, la recombinación es incoherente.
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if left_tokens and right_tokens and not (left_tokens & right_tokens):
        return True, f"combina contextos no relacionados: '{left[:40]}' vs '{right[:40]}'"
    return False, ""


def semantic_coherence(concept: dict[str, Any]) -> tuple[bool, str]:
    """Evalúa si un concepto conecta causalmente sus partes.

    Reglas deterministas:
    1. Frases incoherentes reales detectadas en la campaña → siempre incoherente.
    2. Patrón 'X para A adaptado a B' con A y B sin solapamiento → incoherente.
    3. El mecanismo debe compartir términos con el problema/comprador/entrega
       (conexión causal mínima); si no comparte nada y es genérico → incoherente.
    """
    title = str(concept.get("title") or "").strip()
    problem = str(concept.get("problem_hypothesis") or "").strip()
    mechanism = str(concept.get("mechanism") or "").strip()
    buyer = str(concept.get("buyer_hypothesis") or "").strip()
    outcome = str(concept.get("outcome_hypothesis") or "").strip()

    if not title or not mechanism:
        return False, "falta título o mecanismo"

    bad, reason = _has_adaptado_pattern(title)
    if bad:
        return False, reason

    mech_tokens = _tokens(mechanism)
    context = _tokens(f"{problem} {buyer} {outcome} {title}")
    if not mech_tokens:
        return False, "mecanismo sin contenido semántico"
    if not (mech_tokens & context):
        return False, "el mecanismo no conecta causalmente con el problema, comprador o entrega"
    return True, "conexión causal mínima entre mecanismo, problema y entrega"


# ---------------------------------------------------------------------------
# Etiquetas de ventaja como HIPÓTESIS hasta tener evidencia verificable
# ---------------------------------------------------------------------------
_HYPOTHESIS_MAP = {
    "DEFENSIBLE_WORKFLOW": ("HYPOTHESIS_DEFENSIBLE_WORKFLOW", "Hipótesis: posible workflow defendible"),
    "DATA_ADVANTAGE": ("HYPOTHESIS_DATA_ADVANTAGE", "Hipótesis: posible ventaja de datos"),
    "NETWORK_ADVANTAGE": ("HYPOTHESIS_NETWORK_ADVANTAGE", "Hipótesis: posible efecto de red"),
    "COMPOUNDING_SYSTEM": ("HYPOTHESIS_COMPOUNDING_SYSTEM", "Hipótesis: posible sistema acumulativo"),
    "WEAK_DIFFERENTIATION": ("WEAK_DIFFERENTIATION", "Diferenciación débil"),
    "COMMODITY_WRAPPER": ("COMMODITY_WRAPPER", "Commodity: IA generalista lo resuelve"),
}


def hypothesis_classification(classification: str | None, has_verified_evidence: bool = False) -> tuple[str, str]:
    """Devuelve (etiqueta, significado). Sin evidencia verificable, las ventajas
    estructurales se muestran como HIPÓTESIS, nunca como hechos."""
    cls = classification or "UNKNOWN"
    if cls in ("DEFENSIBLE_WORKFLOW", "DATA_ADVANTAGE", "NETWORK_ADVANTAGE", "COMPOUNDING_SYSTEM"):
        if not has_verified_evidence:
            label, meaning = _HYPOTHESIS_MAP[cls]
            return label, meaning
        return cls, {"DEFENSIBLE_WORKFLOW": "Workflow defendible con evidencia",
                     "DATA_ADVANTAGE": "Ventaja de datos con evidencia",
                     "NETWORK_ADVANTAGE": "Efecto de red con evidencia",
                     "COMPOUNDING_SYSTEM": "Sistema acumulativo con evidencia"}[cls]
    if cls in _HYPOTHESIS_MAP:
        return _HYPOTHESIS_MAP[cls]
    return cls, "Sin clasificación de sustitución"


# ---------------------------------------------------------------------------
# Puntuación estructural vs puntuación con evidencia
# ---------------------------------------------------------------------------
def split_scores(structural_final: float, *, has_verified_evidence: bool, verified_groups: int = 0) -> tuple[float, float]:
    """Devuelve (structural_concept_score, evidence_backed_venture_score).

    - structural_concept_score: calidad interna de la formulación (pre-evidencia).
    - evidence_backed_venture_score: viabilidad empresarial SOLO con evidencia
      verificable. Sin evidencia: 0. Con evidencia insuficiente (<3 grupos
      independientes): tope 40. Con ≥3 grupos independientes: score real.
    """
    structural = round(max(0.0, min(100.0, structural_final)), 2)
    if not has_verified_evidence:
        return structural, 0.0
    if verified_groups >= 3:
        return structural, structural
    return structural, round(min(structural, 40.0), 2)


# ---------------------------------------------------------------------------
# Opportunity Brief (calidad del concepto antes de investigar)
# ---------------------------------------------------------------------------
BRIEF_FIELDS: tuple[str, ...] = (
    "specific_name", "user", "buyer", "situation", "observable_problem",
    "current_alternative", "economic_or_time_cost", "concrete_deliverable",
    "measurable_outcome", "revenue_model", "expected_price_hypothesis",
    "first_distribution_channel", "first_20_buyers_location", "test_in_48_hours",
    "generic_ai_limitation", "compounding_asset", "primary_risk", "assumptions",
    "prohibited_claims",
)

BRIEF_LABELS: dict[str, str] = {
    "specific_name": "Nombre específico",
    "user": "Usuario",
    "buyer": "Comprador",
    "situation": "Situación",
    "observable_problem": "Problema observable",
    "current_alternative": "Alternativa actual",
    "economic_or_time_cost": "Coste económico o de tiempo",
    "concrete_deliverable": "Entrega concreta",
    "measurable_outcome": "Resultado medible",
    "revenue_model": "Modelo de ingresos",
    "expected_price_hypothesis": "Precio esperado (hipótesis)",
    "first_distribution_channel": "Primer canal",
    "first_20_buyers_location": "Dónde están los primeros 20 compradores",
    "test_in_48_hours": "Test en 48 horas",
    "generic_ai_limitation": "Limitación de una IA generalista",
    "compounding_asset": "Activo acumulativo",
    "primary_risk": "Riesgo principal",
    "assumptions": "Suposiciones",
    "prohibited_claims": "Afirmaciones prohibidas",
}

MIN_BRIEF_LENGTH = 8  # caracteres mínimos por campo para no ser genérico


def validate_opportunity_brief(fields: dict[str, Any]) -> dict[str, Any]:
    """Valida el Opportunity Brief. Devuelve {ok, missing, generic_hits, reasons}."""
    missing: list[str] = []
    generic_hits: list[str] = []
    for field in BRIEF_FIELDS:
        value = str(fields.get(field) or "").strip()
        if len(value) < MIN_BRIEF_LENGTH:
            missing.append(field)
            continue
        hits = has_generic_markers(value)
        generic_hits.extend(hits)
    reasons = [f"falta {BRIEF_LABELS.get(m, m)}" for m in missing]
    if generic_hits:
        reasons.append("marcadores genéricos: " + ", ".join(sorted(set(generic_hits))))
    return {
        "ok": not missing and not generic_hits,
        "missing": missing,
        "generic_hits": sorted(set(generic_hits)),
        "reasons": reasons,
    }
