"""Super-torneo determinista (iteración 018).

Evalúa candidatas, reformulaciones y challengers contra 20 criterios de
negocio SIN LLM, SIN aleatoriedad y SIN timestamps en el cálculo: misma
entrada ⇒ misma salida. Propiedades inmutables:

1. BRIEF COMPLETO OBLIGATORIO: una entrada sin Opportunity Brief que supere
   ``validate_opportunity_brief`` se rechaza en la puerta; nunca se puntúa
   una idea incompleta ni se fabrican campos.
2. MÁXIMO 3 GANADORAS; 0 es resultado válido.
3. NUNCA modifica proven_demand, evidence_backed_venture_score, grupos de
   evidencia ni aprobaciones: solo produce prioridades de investigación
   (structural_concept_score queda intacto; este torneo emite su propia
   métrica ``super_tournament_score`` etiquetada como prioridad).
4. Desempate determinista: puntuación descendente, luego concept_id
   ascendente (orden estable entre ejecuciones).
"""
from __future__ import annotations

import re
from typing import Any

from app.scoring.semantic_gate import validate_opportunity_brief

MAX_WINNERS = 3
MIN_SCORE_TO_QUALIFY = 55.0  # sobre 100

# Rango de estado (mayor = más avanzado) para deduplicar duplicados reales.
STATUS_RANK = {
    "FINALIST": 5, "RESEARCH_PENDING": 5, "SHORTLISTED_WITH_EVIDENCE": 4,
    "RESEARCH_CANDIDATE": 4, "STRUCTURAL_FILTER_PASSED": 2,
    "AI_FILTER_PASSED": 2, "NEEDS_REFORMULATION": 1,
    "RECOMBINATION_INCOHERENT": 1, "GENERATED_HYPOTHESIS": 1,
}

# ---------------------------------------------------------------------------
# Utilidades deterministas de análisis textual (sin inventar nada)
# ---------------------------------------------------------------------------

_MONEY_TOKENS = re.compile(r"(€|eur|usd|hora|hombres\shora|coste|gasta|pierde|margen|factura)", re.IGNORECASE)
_TIME_COST = re.compile(r"(\d+\s*(horas|horas?\ssemanales|minutos|días)|cada\s(semana|mes|trimestre|ejercicio))", re.IGNORECASE)
_URGENCY = re.compile(r"(fecha\slímite|plazo|antes\sde|sanción|multa|vence|caduca|cada\s(mes|trimestre|ejercicio|semana)|campaña|temporada|renovación)", re.IGNORECASE)
_RECURRING = re.compile(r"(mensual|mensualidad|suscripción|trimestral|anual|por\scliente\sy\saño|recurrente|renovación)", re.IGNORECASE)
_SERVICE_DELIVERABLE = re.compile(r"(informe|dossier|expediente|checklist|registro|cuaderno|borrador|comparativa|plan\s)", re.IGNORECASE)
_ZERO_COST_TEST = re.compile(r"(correo|email|llamada|formulario|encuesta|sin\scoste|gratis|plantilla|hoja\scálculo|whatsapp)", re.IGNORECASE)
_AUTOMATABLE_CHANNEL = re.compile(r"(correo|email|web|landing|formulario|grupo|foro|colegio|asociación|newsletter|seo|contenido)", re.IGNORECASE)
_GENERIC_BUYER = re.compile(r"\b(empresas|profesionales|emprendedores|usuarios|pymes|personas)\b", re.IGNORECASE)
_HEALTH_SENSITIVE = re.compile(r"(salud|paciente|diagnóstico|clínica|médic)", re.IGNORECASE)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _has_content(value: Any, min_len: int = 12) -> bool:
    return len(_text(value)) >= min_len


def _token_set(*texts: str) -> set[str]:
    stop = {"de", "la", "el", "los", "las", "que", "para", "con", "una", "un", "por", "del", "al", "y", "en", "su", "sus"}
    tokens: set[str] = set()
    for t in texts:
        for w in re.findall(r"[a-záéíóúüñ]{4,}", t.lower()):
            if w not in stop:
                tokens.add(w)
    return tokens


# ---------------------------------------------------------------------------
# Los 20 criterios. Cada uno devuelve (puntos 0..2, motivo breve).
# ---------------------------------------------------------------------------

def _c1_pain(c, b):
    t = f"{b.get('economic_or_time_cost','')} {b.get('observable_problem','')}"
    pts = (1 if _MONEY_TOKENS.search(t) else 0) + (1 if _TIME_COST.search(t) else 0)
    return pts, "Coste económico/temporal cuantificado" if pts == 2 else "Dolor poco cuantificado"

def _c2_buyer(c, b):
    buyer = _text(b.get("buyer"))
    generic = _GENERIC_BUYER.search(buyer)
    specific = bool(re.search(r"\d|\d+-\d+|titular|gerente|socio|responsable|junta|encargad", buyer))
    pts = 0 if generic else (2 if specific else 1)
    return pts, "Comprador genérico" if pts == 0 else "Comprador identificable"

def _c3_urgency(c, b):
    t = f"{b.get('situation','')} {b.get('observable_problem','')}"
    return (2, "Evento o plazo de compra detectable") if _URGENCY.search(t) else (0, "Sin urgencia detectable")

def _c4_first20(c, b):
    loc = _text(b.get("first_20_buyers_location"))
    ok = _has_content(loc) and not _GENERIC_BUYER.search(loc) and len(loc.split()) >= 4
    return (2, "Ubicación concreta de los primeros compradores") if ok else (0, "Primeros compradores imprecisos")

def _c5_test48h(c, b):
    t = _text(b.get("test_in_48_hours"))
    ok = _has_content(t) and _ZERO_COST_TEST.search(t)
    return (2, "Test 48 h concreto y barato") if ok else (0, "Test 48 h no definido o costoso")

def _c6_pay10d(c, b):
    price = _text(b.get("expected_price_hypothesis"))
    rev = _text(b.get("revenue_model"))
    has_price = bool(re.search(r"\d+", price))
    direct = bool(re.search(r"(pago|cobro|transferencia|stripe|link|checkout|anticipado|directo)", rev + " " + b.get("first_distribution_channel",""), re.I))
    return ((2, "Cobrable directamente con precio hipotético") if has_price and direct else (1, "Precio sin vía de cobro directa") if has_price else (0, "Sin precio definido"))

def _c7_launch_cost(c, b):
    d = _SERVICE_DELIVERABLE.search(_text(b.get("concrete_deliverable")))
    return (2, "Entregable ligero tipo documento/servicio") if d else (1, "Entregable pesado de lanzar")

def _c8_concierge(c, b):
    d = _text(b.get("concrete_deliverable"))
    return (2, "Entregable prestable manualmente") if d and _SERVICE_DELIVERABLE.search(d) else (0, "No prestable como concierge")

def _c9_automation(c, b):
    m = _text(b.get("mechanism") or c.get("mechanism"))
    return (2, "Mecanismo plantillable/automatizable") if m and re.search(r"(plantilla|checklist|genera|registro|cruce|comparativ)", m, re.I) else (0, "Automatización poco clara")

def _c10_ai_resistance(c, b):
    lim = _text(b.get("generic_ai_limitation"))
    return (2, "Límite de IA generalista argumentado") if _has_content(lim, 20) else (0, "Una IA generalista podría sustituirlo")

def _c11_legal(c, b):
    claims = _text(b.get("prohibited_claims"))
    sensitive = bool(_HEALTH_SENSITIVE.search(f"{b.get('buyer','')} {b.get('user','')}"))
    if not _has_content(claims, 8):
        return 0, "Sin afirmaciones prohibidas definidas"
    return (1, "Dominio sensible: revisión de cumplimiento previa") if sensitive else (2, "Riesgo legal bajo y acotado")

def _c12_data(c, b):
    assumpt = _text(b.get("assumptions"))
    risky = bool(re.search(r"(datos\sprivados|acceso\sa\sdatos|scrapping|scraping|confidenciales)", assumpt + " " + _text(b.get("mechanism")), re.I))
    return (0, "Depende de datos difíciles de obtener") if risky else (2, "Datos obtenibles por medios legítimos")

def _c13_margin(c, b):
    price = re.search(r"(\d+)", _text(b.get("expected_price_hypothesis")))
    if not price:
        return 0, "Margen indeterminado (sin precio)"
    value = int(price.group(1))
    return (2, "Precio con margen plausible") if value >= 30 else (1, "Precio bajo: margen ajustado")

def _c14_recurrence(c, b):
    return (2, "Ingreso potencialmente recurrente") if _RECURRING.search(_text(b.get("revenue_model"))) else (0, "Ingreso único puntual")

def _c15_asset(c, b):
    return (2, "Activo acumulativo definido") if _has_content(b.get("compounding_asset"), 12) else (0, "Sin activo acumulativo")

CRITERIA = [
    ("pain_quantified", "Dolor económico observable y cuantificado", _c1_pain),
    ("buyer_with_budget", "Comprador específico con presupuesto", _c2_buyer),
    ("urgency_or_event", "Urgencia o evento de compra", _c3_urgency),
    ("first_20_access", "Acceso a los primeros 20 compradores", _c4_first20),
    ("valid_48h", "Validable en 48 horas", _c5_test48h),
    ("payment_10_days", "Primer pago posible en ≤10 días", _c6_pay10d),
    ("low_launch_cost", "Coste de lanzamiento bajo", _c7_launch_cost),
    ("concierge_delivery", "Entrega inicial concierge posible", _c8_concierge),
    ("automation_path", "Camino claro a automatización", _c9_automation),
    ("ai_resistance", "Resistencia a IA generalista", _c10_ai_resistance),
    ("legal_risk_low", "Riesgo legal bajo/acotado", _c11_legal),
    ("data_obtainable", "Datos obtenibles legítimamente", _c12_data),
    ("margin_plausible", "Margen plausible", _c13_margin),
    ("recurrence", "Recurrencia potencial", _c14_recurrence),
    ("compounding_asset", "Activo acumulativo", _c15_asset),
]


def _c16_coherence(c, b):
    overlap = _token_set(b.get("observable_problem",""), c.get("problem_hypothesis","")) & \
              _token_set(b.get("specific_name",""), _text(b.get("mechanism")), _text(c.get("mechanism")))
    return (2, "Cadena causal problema→entrega coherente") if overlap else (0, "Problema y entrega desconectados")

def _c17_simplicity(c, b):
    name = _text(b.get("specific_name"))
    words = len(name.split())
    return (2, "Explicable en una frase") if 3 <= words <= 16 else (1, "Nombre confuso o excesivo")

def _c18_fit247(c, b):
    ch = _text(b.get("first_distribution_channel"))
    return (2, "Canal operable sin intervención continua") if _AUTOMATABLE_CHANNEL.search(ch) else (0, "Canal dependiente de presencia humana constante")

def _c19_limited_budget(c, b):
    t = f"{b.get('test_in_48_hours','')} {b.get('economic_or_time_cost','')}"
    return (2, "Ejecutable con presupuesto mínimo") if _ZERO_COST_TEST.search(t) else (1, "Requiere algo de presupuesto inicial")

def _c20_deserves_next(c, b):
    # Compuesto determinista: combinación de dolor+comprador+cobro+activo.
    pts = sum([
        1 if _MONEY_TOKENS.search(_text(b.get('economic_or_time_cost'))) else 0,
        1 if not _GENERIC_BUYER.search(_text(b.get('buyer'))) else 0,
        1 if bool(re.search(r"\d+", _text(b.get("expected_price_hypothesis")))) else 0,
        1 if _has_content(b.get("compounding_asset"), 12) else 0,
    ])
    return pts, "Prioridad de siguiente euro/hora" if pts >= 3 else "Aún no merece el siguiente euro"


EXTRA_CRITERIA = [
    ("causal_coherence", "Coherencia causal problema→producto", _c16_coherence),
    ("simplicity", "Simplicidad de explicación", _c17_simplicity),
    ("fit_autonomous_247", "Encaje con operación autónoma", _c18_fit247),
    ("limited_budget_ok", "Viable con presupuesto limitado", _c19_limited_budget),
    ("deserves_next_resource", "Merece el siguiente euro/hora", _c20_deserves_next),
]

ALL_CRITERIA = CRITERIA + EXTRA_CRITERIA  # exactamente 20
assert len(ALL_CRITERIA) == 20


def score_entry(concept: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    """Puntúa una entrada (0..100) con detalle por criterio."""
    detail = []
    total = 0
    for key, label, fn in ALL_CRITERIA:
        pts, reason = fn(concept, brief)
        total += pts
        detail.append({"criterion": key, "label": label, "score": pts, "max": 2, "reason": reason})
    return {
        "super_tournament_score": round(total / (20 * 2) * 100, 1),
        "criteria_detail": detail,
        "is_priority_metric": True,
        "is_not_evidence": True,
    }


def _normalize_title(title: Any) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", str(title or "").strip().lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def dedup_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Elimina duplicados reales (mismo título normalizado) conservando la
    entrada con el estado más avanzado (desempate: concept_id).

    Nunca elimina el concepto de la base: solo evita que el MISMO negocio
    ocupe dos plazas del torneo."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        key = _normalize_title(e.get("title")) or str(e.get("concept_id"))
        grouped.setdefault(key, []).append(e)
    unique: list[dict[str, Any]] = []
    deduped: list[dict[str, Any]] = []
    for key, group in grouped.items():
        group.sort(key=lambda e: (-STATUS_RANK.get(e.get("status"), 0), str(e.get("concept_id"))))
        unique.append(group[0])
        for extra in group[1:]:
            deduped.append({
                "concept_id": extra.get("concept_id"),
                "title": extra.get("title"),
                "status": extra.get("status"),
                "reason": f"Duplicado de '{group[0].get('title')}' (se conserva el estado más avanzado).",
            })
    return {"unique": unique, "deduped": deduped}


def run_super_tournament(entries: list[dict[str, Any]], *, max_winners: int = MAX_WINNERS,
                         min_score: float = MIN_SCORE_TO_QUALIFY) -> dict[str, Any]:
    """Ejecuta el torneo. ``entries``: [{concept_id, title, concept, brief}].

    Deduplica primero (mismo negocio, una plaza), exige brief completo, y
    devuelve ganadoras (máx. ``max_winners``, solo si superan ``min_score``),
    rechazos por brief incompleto y descartes por puntuación, todo ordenado
    de forma determinista."""
    dedup = dedup_entries(entries)
    entries = dedup["unique"]
    qualified: list[dict[str, Any]] = []
    rejected_brief: list[dict[str, Any]] = []
    rejected_score: list[dict[str, Any]] = []

    for entry in sorted(entries, key=lambda e: str(e.get("concept_id"))):
        check = validate_opportunity_brief(entry.get("brief") or {})
        if not check["ok"]:
            rejected_brief.append({
                "concept_id": entry.get("concept_id"),
                "title": entry.get("title"),
                "status": entry.get("status"),
                "reason": "; ".join(check["reasons"]) or "Brief incompleto",
            })
            continue
        result = score_entry(entry["concept"], entry["brief"])
        row = {
            "concept_id": entry.get("concept_id"),
            "title": entry.get("title"),
            "status": entry.get("status"),
            **result,
        }
        if result["super_tournament_score"] >= min_score:
            qualified.append(row)
        else:
            rejected_score.append(row)

    qualified.sort(key=lambda r: (-r["super_tournament_score"], str(r["concept_id"])))
    rejected_score.sort(key=lambda r: (-r["super_tournament_score"], str(r["concept_id"])))

    winners = qualified[:max_winners]
    eliminated = qualified[max_winners:]
    for w in winners:
        w["tournament_result"] = "WINNER"
    for e in eliminated:
        e["tournament_result"] = "ELIMINATED_MAX_SLOTS"
    for r in rejected_score:
        r["tournament_result"] = "ELIMINATED_LOW_SCORE"

    return {
        "winners": winners,
        "eliminated_over_slots": eliminated,
        "rejected_incomplete_brief": rejected_brief,
        "rejected_low_score": rejected_score,
        "deduped_duplicates": dedup["deduped"],
        "entries_after_dedup": len(entries),
        "total_entries": len(dedup["unique"]) + len(dedup["deduped"]),
        "max_winners": max_winners,
        "min_score_to_qualify": min_score,
        "zero_winners_is_valid": True,
        "score_semantics": "prioridad_de_investigacion_no_evidencia",
    }
