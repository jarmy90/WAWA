"""Rúbrica determinista del benchmark OX Alpha (iteración 018).

Puntúa respuestas de tareas profundas (reformulación, coherencia, red-team,
comparación de variantes) contra criterios objetivos SIN LLM. Misma respuesta
⇒ misma puntuación. NUNCA usa preferencia estética.

Veredictos posibles (los mismos que exige la macrooperación 018):
- OX_ALPHA_BENCHMARK_PASSED
- OX_ALPHA_BENCHMARK_INCONCLUSIVE
- OX_ALPHA_BENCHMARK_FAILED
- OX_ALPHA_UNVERIFIED  (identidad del modelo no verificada ⇒ no se puntúa)

La puntuación de una respuesta NUNCA es evidencia de mercado: es solo una
medida de utilidad de razonamiento.
"""
from __future__ import annotations

import re
from typing import Any

BENCHMARK_TASKS = (
    "reformulation",      # reformular un concepto abstracto
    "coherence_check",    # analizar coherencia causal
    "red_team",           # ejecutar red-team
    "variation_comparison",  # comparar tres variantes
)

VERDICT_LEVELS = {
    "OX_ALPHA_BENCHMARK_PASSED": 0,
    "OX_ALPHA_BENCHMARK_INCONCLUSIVE": 1,
    "OX_ALPHA_BENCHMARK_FAILED": 2,
    "OX_ALPHA_UNVERIFIED": 3,
}

_GENERIC_BUYER = re.compile(r"\b(empresas|profesionales|emprendedores|usuarios|pymes|personas|negocio)\b", re.IGNORECASE)
_NUMBER = re.compile(r"\d+")
_ACTION_48H = re.compile(r"(correo|email|llamada|formulario|encuesta|whatsapp|linkedin|publicar|plantilla|enviar)", re.IGNORECASE)
_AI_LIMIT = re.compile(r"(contexto|específic|proceso|integraci|memoria|flujo|workflow|normativa|sector)", re.IGNORECASE)
_INVENTION = re.compile(r"(según\smi\sestudio|he\sverificado|demanda\sconfirmada|clientes\sha\ndicho|%)\s*[^\n.]*", re.IGNORECASE)

RUBRIC = {
    "buyer_specificity": "Especificidad del comprador",
    "observable_problem": "Problema observable",
    "deliverable_clarity": "Claridad del entregable",
    "causal_chain": "Conexión causal",
    "first_channel": "Canal inicial",
    "test_48h": "Experimento de 48 horas",
    "ai_resistance": "Resistencia a IA generalista",
    "no_invented_claims": "Ausencia de afirmaciones inventadas",
    "assumptions_quality": "Calidad de supuestos",
    "variant_diversity": "Variantes sustancialmente distintas",
    "practical_utility": "Utilidad práctica",
    "valid_structure": "Formato estructurado válido",
}


def _check(value: Any, pattern: re.Pattern[str]) -> bool:
    return bool(pattern.search(str(value or "")))


def score_reformulation_variant(v: dict[str, Any]) -> dict[str, Any]:
    """Puntúa UNA variante de reformulación (0..2 por criterio)."""
    score = 0
    detail: list[dict[str, Any]] = []

    buyer = str(v.get("buyer") or "")
    specific_buyer = len(buyer) >= 12 and not _GENERIC_BUYER.search(buyer)
    detail.append({"criterion": "buyer_specificity", "score": 2 if specific_buyer else 0})
    score += 2 if specific_buyer else 0

    prob = str(v.get("observable_problem") or "")
    observable = len(prob) >= 20
    detail.append({"criterion": "observable_problem", "score": 2 if observable else 0})
    score += 2 if observable else 0

    deliv = str(v.get("concrete_deliverable") or "")
    clear = len(deliv) >= 12
    detail.append({"criterion": "deliverable_clarity", "score": 2 if clear else 0})
    score += 2 if clear else 0

    causal = len(str(v.get("causal_chain") or "")) >= 20
    detail.append({"criterion": "causal_chain", "score": 2 if causal else 0})
    score += 2 if causal else 0

    channel = str(v.get("first_distribution_channel") or "")
    has_channel = len(channel) >= 8
    detail.append({"criterion": "first_channel", "score": 2 if has_channel else 0})
    score += 2 if has_channel else 0

    test = str(v.get("test_in_48_hours") or "")
    has_test = _ACTION_48H.search(test)
    detail.append({"criterion": "test_48h", "score": 2 if has_test else 0})
    score += 2 if has_test else 0

    lim = str(v.get("generic_ai_limitation") or "")
    resists = _AI_LIMIT.search(lim)
    detail.append({"criterion": "ai_resistance", "score": 2 if resists else 0})
    score += 2 if resists else 0

    invented = _INVENTION.search(f"{buyer} {prob} {str(v.get('measurable_outcome') or '')}")
    detail.append({"criterion": "no_invented_claims", "score": 0 if invented else 2})
    score += 0 if invented else 2

    assumpt = str(v.get("assumptions") or "")
    quality = len(assumpt) >= 15
    detail.append({"criterion": "assumptions_quality", "score": 2 if quality else 0})
    score += 2 if quality else 0

    return {
        "score": score,
        "max": 18,
        "percent": round(score / 18 * 100, 1),
        "detail": detail,
    }


def score_task_response(task: str, response: Any) -> dict[str, Any]:
    """Puntúa una respuesta estructurada según la tarea. No usa timestamps."""
    if response is None:
        return {"score": 0, "max": 0, "percent": 0.0, "detail": [], "note": "respuesta ausente"}
    if not isinstance(response, dict):
        return {"score": 0, "max": 0, "percent": 0.0, "detail": [], "note": "formato no estructurado"}

    detail: list[dict[str, Any]] = []

    if task == "reformulation":
        variants = response.get("variants")
        if not isinstance(variants, list) or not variants:
            return {"score": 0, "max": 20, "percent": 0.0,
                    "detail": [{"criterion": "valid_structure", "score": 0}],
                    "note": "sin variantes"}
        per = [score_reformulation_variant(v) if isinstance(v, dict) else {"score": 0} for v in variants]
        avg = sum(p["score"] for p in per) / len(per) / 18 * 100
        diversity = len({str(v.get("buyer") or "")[:30] for v in variants if isinstance(v, dict)})
        total = avg + (15 if diversity >= 2 else 0)
        detail = [{"criterion": "variant_diversity", "score": 2 if diversity >= 2 else 0},
                  {"criterion": "practical_utility", "score": 2 if avg >= 50 else 0},
                  {"criterion": "valid_structure", "score": 2}]
        return {"score": round(total, 1), "max": 100, "percent": round(total, 1),
                "detail": detail, "variants_scored": len(per)}

    if task == "coherence_check":
        coherent = bool(response.get("coherent"))
        product = str(response.get("concrete_product") or "")
        causal = str(response.get("causal_relation") or "")
        total = (20 if coherent else 0) + (20 if len(product) >= 15 else 0) + (15 if len(causal) >= 15 else 0)
        return {"score": total, "max": 100, "percent": total,
                "detail": [{"criterion": "causal_chain", "score": 2 if len(causal) >= 15 else 0},
                           {"criterion": "practical_utility", "score": 2 if len(product) >= 15 else 0}]}

    if task == "red_team":
        answers = response.get("answers")
        if not isinstance(answers, list):
            return {"score": 0, "max": 100, "percent": 0.0, "detail": [], "note": "sin answers"}
        n_fatal = sum(1 for a in answers if isinstance(a, dict) and a.get("verdict") == "fatal")
        n_ok = sum(1 for a in answers if isinstance(a, dict) and a.get("verdict") == "ok")
        total = min(100, 30 + n_fatal * 10 + n_ok * 4)
        return {"score": total, "max": 100, "percent": total,
                "detail": [{"criterion": "practical_utility", "score": 2 if n_fatal >= 3 else 0}]}

    if task == "variation_comparison":
        selected = response.get("selected")
        rejected = response.get("rejected")
        valid_sel = isinstance(selected, list) and len(selected) <= 3
        has_reasons = isinstance(rejected, list) and all(isinstance(r, dict) and r.get("reason") for r in rejected)
        total = (50 if valid_sel else 0) + (30 if has_reasons else 0)
        return {"score": total, "max": 100, "percent": total,
                "detail": [{"criterion": "valid_structure", "score": 2 if valid_sel else 0}]}

    return {"score": 0, "max": 100, "percent": 0.0, "detail": [], "note": f"tarea desconocida: {task}"}


def benchmark_verdict(identity: str, arms: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Veredicto global del benchmark.

    - Identidad no verificada ⇒ OX_ALPHA_UNVERIFIED (no se compara nada).
    - Si el brazo del modelo no respondió ⇒ INCONCLUSIVE.
    - Si respondió: PASSED si supera o iguala el mejor criterio de utilidad
      frente al brazo determinista; FAILED en caso contrario."""
    if identity == "OX_ALPHA_UNVERIFIED":
        return {
            "verdict": "OX_ALPHA_UNVERIFIED",
            "reason": "Identidad del modelo no verificada contra el catálogo: sin benchmark de modelo.",
            "compare": None,
        }
    arm_a = arms.get("A") or {}
    arm_c = arms.get("C") or {}
    if arm_c.get("status") != "ok":
        return {
            "verdict": "OX_ALPHA_BENCHMARK_INCONCLUSIVE",
            "reason": arm_c.get("reason") or "El brazo del modelo no respondió; no se puede comparar.",
            "compare": None,
        }
    a_score = arm_a.get("total_percent") or 0
    c_score = arm_c.get("total_percent") or 0
    verdict = "OX_ALPHA_BENCHMARK_PASSED" if c_score >= a_score else "OX_ALPHA_BENCHMARK_FAILED"
    return {"verdict": verdict, "reason": f"A={a_score} vs C={c_score}", "compare": {"a": a_score, "c": c_score}}
