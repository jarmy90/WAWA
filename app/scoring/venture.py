"""Venture Quality Score y General AI Substitution Test (iteración 004).

Funciones puras, deterministas y sin efectos. No usan LLM: las puntuaciones
se derivan de respuestas estructuradas (que pueden venir de un proveedor, de
una misión Freebuff o de datos manuales) y de bloqueadores duros.

Regla central: una idea clasificada como COMMODITY_WRAPPER **no puede
aprobarse** aunque tenga demanda aparente.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from app.models.discovery import (
    VENTURE_HARD_BLOCKERS,
    SubstitutionAnswers,
    SubstitutionTest,
    VentureEvaluation,
)

# ---------------------------------------------------------------------------
# Pesos del Venture Quality Score (total 100)
# ---------------------------------------------------------------------------
VENTURE_WEIGHTS: dict[str, float] = {
    "economic_pain": 12.0,
    "proven_demand": 10.0,
    "general_ai_resistance": 15.0,
    "defensibility": 15.0,
    "distribution": 12.0,
    "originality": 10.0,
    "validation_speed": 8.0,
    "gross_margin": 6.0,
    "recurrence": 5.0,
    "demonstrability": 4.0,
    "operational_simplicity": 3.0,
}

SCORE_KEYS: tuple[str, ...] = tuple(VENTURE_WEIGHTS.keys())

# Bloqueadores duros estandarizados (los textos exactos viven en el modelo;
# aquí se comprueban con prefijos para no depender de la redacción exacta).
_BLOCKER_PREFIXES = (
    "COMMODITY_WRAPPER",
    "Sin comprador identificable",
    "Sin camino creíble",
    "Sin resultado medible",
    "Sin vía de validación barata",
    "Riesgo legal",
    "Requiere capital elevado",
    "Marketplace sin cuña",
    "Depende de spam",
    "Sin ventaja defendible",
    "solo una feature",
    "evidencia inventada",
)


def _stable_int(seed: str) -> int:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16)


# ---------------------------------------------------------------------------
# General AI Substitution Test
# ---------------------------------------------------------------------------
def substitution_resistance(answers: SubstitutionAnswers) -> float:
    """Resistencia a ser sustituido por una IA generalista (0-100).

    - Vulnerabilidad: qué parte del problema resuelve una IA genérica con
      salida genérica (texto/código/recomendaciones).
    - Defensa: trabajo operativo, integración, memoria, resultado verificable,
      acción posterior, coste de cambio, mejora con el uso.
    - Bonos: datos, red, distribución.
    """
    vulnerability = 0.5 * answers.generic_ai_can_solve + 0.5 * answers.output_is_generic
    defense = (
        0.25 * answers.has_operational_workflow
        + 0.2 * answers.has_data_integration
        + 0.2 * answers.has_accumulative_memory
        + 0.15 * answers.has_verifiable_outcome
        + 0.1 * answers.has_followup_action
        + 0.1 * answers.has_switching_cost
    )
    compounding = 0.5 * answers.improves_with_use + 0.5 * answers.survives_model_improvement
    bonus = max(
        0.15 * answers.network_effect,
        0.12 * answers.distribution_loop,
        0.12 * answers.data_advantage,
    )
    resistance = 0.6 * (100 - vulnerability) + 0.4 * defense + bonus
    return round(max(0.0, min(100.0, resistance)), 2)


def classify_substitution(answers: SubstitutionAnswers) -> str:
    """Clasificación determinista (orden de comprobación = prioridad)."""
    a = answers
    # COMMODITY_WRAPPER: la IA genérica resuelve casi todo y no hay defensa.
    if a.generic_ai_can_solve >= 70 and a.output_is_generic >= 60:
        if a.has_operational_workflow < 45 and a.has_data_integration < 45 and a.has_accumulative_memory < 45:
            return "COMMODITY_WRAPPER"
    if a.data_advantage >= 70:
        return "DATA_ADVANTAGE"
    if a.network_effect >= 70:
        return "NETWORK_ADVANTAGE"
    if a.distribution_loop >= 70:
        return "DISTRIBUTION_ADVANTAGE"
    if (a.improves_with_use >= 60 or a.has_accumulative_memory >= 60) and a.survives_model_improvement >= 50:
        return "COMPOUNDING_SYSTEM"
    if a.has_operational_workflow >= 55 and a.has_verifiable_outcome >= 50:
        return "DEFENSIBLE_WORKFLOW"
    if substitution_resistance(a) >= 55:
        return "DEFENSIBLE_WORKFLOW"
    return "WEAK_DIFFERENTIATION"


def run_substitution_test(answers: SubstitutionAnswers) -> SubstitutionTest:
    """Ejecuta el test y decide si la idea queda bloqueada (verdict=blocked)."""
    a = answers
    resistance = substitution_resistance(answers)
    classification = classify_substitution(answers)
    reasons: list[str] = []

    if classification == "COMMODITY_WRAPPER":
        reasons.append(
            "Una IA generalista (ChatGPT/Gemini/Claude/DeepSeek) resuelve el 70%+ del problema con "
            "salida genérica y sin workflow operativo, integración ni memoria: es un prompt envuelto."
        )
    if a.generic_ai_can_solve >= 70:
        reasons.append("El cliente puede resolver gran parte del problema pegando su información en una IA generalista.")
    if a.output_is_generic >= 60:
        reasons.append("La salida principal es texto, código o recomendaciones genéricas sin resultado verificable propio.")
    if a.has_operational_workflow < 40 and a.has_data_integration < 40 and a.has_accumulative_memory < 40:
        reasons.append("Sin workflow operativo, integración con datos ni memoria acumulativa: nada sobrevive a la mejora de los modelos base.")
    elif classification not in ("COMMODITY_WRAPPER", "WEAK_DIFFERENTIATION"):
        reasons.append(f"Existe defensa estructural ({classification}): la sustitución por IA genérica es parcial.")

    verdict = "blocked" if classification == "COMMODITY_WRAPPER" else "ok"
    return SubstitutionTest(
        answers=answers,
        classification=classification,
        general_ai_resistance=resistance,
        verdict=verdict,
        reasons=reasons or ["El test no encontró vulnerabilidad de comoditización evidente."],
    )


# ---------------------------------------------------------------------------
# Originalidad con utilidad
# ---------------------------------------------------------------------------
def originality_score(novelty_score: float, utility_score: float) -> float:
    """Originalidad con utilidad: la utilidad tope, la novedad modula.

    - Novedosa pero inútil -> baja (la utilidad capa el resultado).
    - Útil pero copiada -> baja en originalidad (novedad baja).
    """
    utility = max(0.0, min(100.0, utility_score))
    novelty = max(0.0, min(100.0, novelty_score))
    return round(utility * (0.4 + 0.6 * novelty / 100.0), 2)


# ---------------------------------------------------------------------------
# Etiquetas
# ---------------------------------------------------------------------------
def apply_labels(eval_scores: dict[str, float], blockers: list[str]) -> list[str]:
    """Etiquetas deterministas basadas en puntuaciones y bloqueadores."""
    labels: list[str] = []
    if blockers:
        if "COMMODITY_WRAPPER" in blockers or any(b.startswith("COMMODITY_WRAPPER") for b in blockers):
            labels.append("COMMODITY")
        if any("comprador" in b for b in blockers):
            labels.append("SERVICE_FIRST")
    if eval_scores["originality"] >= 75 and eval_scores["economic_pain"] < 50:
        labels.append("NOVEL_BUT_WEAK")
    if eval_scores["economic_pain"] >= 70 and eval_scores["general_ai_resistance"] < 40:
        labels.append("BORING_BUT_STRONG")
    if eval_scores["demonstrability"] >= 75 and eval_scores["defensibility"] < 45:
        labels.append("VIRAL_BUT_FRAGILE")
    if eval_scores["defensibility"] >= 70:
        labels.append("DATA_COMPOUNDING" if eval_scores.get("originality") else "NETWORK_POTENTIAL")
    if eval_scores["distribution"] >= 70:
        labels.append("DISTRIBUTION_FIRST")
    if eval_scores["validation_speed"] >= 70 and not blockers:
        labels.append("EXPERIMENT_READY")
    if eval_scores["gross_margin"] >= 75:
        labels.append("PRODUCT_POTENTIAL")
    if not labels:
        labels.append("CATEGORY_CREATION_CANDIDATE" if eval_scores["originality"] >= 60 else "PRODUCT_POTENTIAL")
    return labels


# ---------------------------------------------------------------------------
# Venture Quality Score
# ---------------------------------------------------------------------------
def venture_score(
    *,
    scores: dict[str, float],
    novelty_score: float = 0.0,
    utility_score: float = 0.0,
    blockers: list[str] | None = None,
    has_verified_evidence: bool = False,
    verified_evidence_groups: int = 0,
) -> VentureEvaluation:
    """Calcula el Venture Quality Score (0-100) con bloqueadores duros y la
    separación honesta de la iteración 013:

    - ``structural_concept_score``: calidad interna de la formulación ANTES de
      investigación (proven_demand/distribution a 0 sin evidencia).
    - ``evidence_backed_venture_score``: viabilidad empresarial SOLO con
      evidencia verificable; sin evidencia = 0; con evidencia insuficiente
      (<3 grupos independientes) tope 40; con ≥3 grupos, score real.
    """
    blockers = list(blockers or [])
    scored: dict[str, float] = {}
    for key in SCORE_KEYS:
        scored[key] = round(max(0.0, min(100.0, float(scores.get(key, 0.0)))), 2)

    # Sin evidencia verificable, la demanda y la distribución NO pueden puntuar.
    if not has_verified_evidence:
        scored["proven_demand"] = 0.0
        scored["distribution"] = 0.0

    scored["originality"] = originality_score(novelty_score, utility_score)

    total_weight = sum(VENTURE_WEIGHTS.values())
    final = round(sum(scored[k] * w for k, w in VENTURE_WEIGHTS.items()) / total_weight, 2)

    blocked = any(b.startswith(prefix) for prefix in _BLOCKER_PREFIXES for b in blockers)
    if blocked:
        final = min(final, 39.0)  # ningún bloqueado puede parecer aprobable

    structural = final
    from app.scoring.semantic_gate import split_scores

    _, evidence_backed_score = split_scores(
        structural, has_verified_evidence=has_verified_evidence, verified_groups=verified_evidence_groups
    )

    labels = apply_labels(scored, blockers)
    return VentureEvaluation(
        economic_pain=scored["economic_pain"],
        proven_demand=scored["proven_demand"],
        general_ai_resistance=scored["general_ai_resistance"],
        defensibility=scored["defensibility"],
        distribution=scored["distribution"],
        originality=scored["originality"],
        validation_speed=scored["validation_speed"],
        gross_margin=scored["gross_margin"],
        recurrence=scored["recurrence"],
        demonstrability=scored["demonstrability"],
        operational_simplicity=scored["operational_simplicity"],
        final_score=final,
        structural_concept_score=structural,
        evidence_backed_venture_score=evidence_backed_score,
        has_verified_evidence=has_verified_evidence,
        novelty_score=round(max(0.0, min(100.0, novelty_score)), 2),
        utility_score=round(max(0.0, min(100.0, utility_score)), 2),
        blockers=blockers,
        labels=labels,
        rationale={
            "final_score": (
                f"Media ponderada de {len(SCORE_KEYS)} criterios (pesos {VENTURE_WEIGHTS}); "
                f"{'BLOQUEADA: ' + ' | '.join(blockers[:3]) if blocked else 'sin bloqueadores duros.'}"
            ),
            "evidence_backed_venture_score": (
                "0 sin evidencia verificable; tope 40 con evidencia insuficiente; score real solo con ≥3 grupos independientes."
            ),
        },
    )


# ---------------------------------------------------------------------------
# Fingerprint de concepto y detección de clones conceptuales
# ---------------------------------------------------------------------------
_STOPWORDS = {
    "de", "la", "el", "los", "las", "un", "una", "unos", "unas", "que", "y", "o", "a", "en",
    "para", "con", "por", "del", "al", "se", "su", "sus", "como", "más", "mas", "ya", "ser",
    "hacer", "poder", "tener", "entre", "sobre", "sin", "no", "es", "son", "esta", "este",
    "app", "plataforma", "herramienta", "servicio", "producto", "sistema", "software",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-záéíóúñü0-9]{3,}", (text or "").lower())
    return {w for w in words if w not in _STOPWORDS}


def concept_fingerprint(concept: dict[str, Any]) -> dict[str, Any]:
    """Huella estructural de un concepto (para diversidad y clones).

    Entrada: dict con claves de ConceptCreate. Salida: campos normalizados.
    """
    mechanism = _tokens(concept.get("mechanism", ""))
    problem = _tokens(concept.get("problem_hypothesis", ""))
    buyer = _tokens(concept.get("buyer_hypothesis", ""))
    outcome = _tokens(concept.get("outcome_hypothesis", ""))
    return {
        "archetype": concept.get("archetype_key"),
        "territory": concept.get("territory_key"),
        "lenses": sorted(concept.get("lens_keys") or []),
        "mechanism_tokens": sorted(mechanism),
        "problem_tokens": sorted(problem),
        "buyer_tokens": sorted(buyer),
        "outcome_tokens": sorted(outcome),
    }


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def semantic_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    """Distancia semántico-estructural (0 = idéntico, 1 = totalmente distinto)."""
    dims = {
        "archetype": 0.2,
        "territory": 0.1,
        "lenses": 0.15,
        "mechanism_tokens": 0.25,
        "problem_tokens": 0.15,
        "buyer_tokens": 0.1,
        "outcome_tokens": 0.05,
    }
    total = 0.0
    weight_sum = 0.0
    for key, weight in dims.items():
        va, vb = a.get(key), b.get(key)
        if isinstance(va, list):
            same = _jaccard(set(va), set(vb or []))
        elif key == "archetype" or key == "territory":
            same = 1.0 if va == vb else 0.0
        else:
            same = _jaccard(set(va or []), set(vb or []))
        total += weight * (1.0 - same)
        weight_sum += weight
    return round(total / weight_sum, 3)


def is_conceptual_clone(a: dict[str, Any], b: dict[str, Any], threshold: float = 0.55) -> tuple[bool, str]:
    """Detección de clones conceptuales.

    Se considera clon si comparte arquetipo y el mecanismo de valor es casi
    idéntico, o si la distancia global es muy baja.
    """
    same_archetype = a.get("archetype") is not None and a.get("archetype") == b.get("archetype")
    mech_sim = 1.0 - _jaccard(set(a.get("mechanism_tokens") or []), set(b.get("mechanism_tokens") or []))
    dist = semantic_distance(a, b)
    if same_archetype and mech_sim <= 0.35 and dist <= 0.45:
        return True, "mismo arquetipo y mecanismo de valor casi idéntico"
    if dist <= 0.22:
        return True, f"distancia estructural muy baja ({dist:.2f})"
    return False, ""


def diversity_metric(fingerprints: list[dict[str, Any]]) -> float:
    """Diversidad media de una cartera (0-1). 1 = todo distinto, 0 = todo clon."""
    if len(fingerprints) < 2:
        return 1.0
    pairs = 0
    acc = 0.0
    for i in range(len(fingerprints)):
        for j in range(i + 1, len(fingerprints)):
            acc += semantic_distance(fingerprints[i], fingerprints[j])
            pairs += 1
    return round(acc / pairs, 3)


def stable_seed(text: str) -> int:
    return _stable_int(text)


# ---------------------------------------------------------------------------
# Estimación estructural offline (sin evidencia de mercado)
# ---------------------------------------------------------------------------
# Perfiles de sustitución por arquetipo: son HIPÓTESIS estructurales, no
# evidencia. En modo offline determinan el test; las misiones de investigación
# pueden aportar respuestas reales que las sustituyan.
ARCHETYPE_SUBSTITUTION_PROFILES: dict[str, dict[str, float]] = {
    "VERTICAL_SAAS": {"generic_ai_can_solve": 45, "output_is_generic": 35, "has_operational_workflow": 75, "has_data_integration": 65, "has_accumulative_memory": 55, "has_verifiable_outcome": 65, "has_followup_action": 75, "has_switching_cost": 65, "improves_with_use": 55, "survives_model_improvement": 55, "network_effect": 20, "distribution_loop": 35, "data_advantage": 45},
    "SOFTWARE_ENABLED_SERVICE": {"generic_ai_can_solve": 45, "output_is_generic": 40, "has_operational_workflow": 80, "has_data_integration": 50, "has_accumulative_memory": 50, "has_verifiable_outcome": 70, "has_followup_action": 65, "has_switching_cost": 50, "improves_with_use": 45, "survives_model_improvement": 50, "network_effect": 15, "distribution_loop": 30, "data_advantage": 35},
    "MARKETPLACE": {"generic_ai_can_solve": 15, "output_is_generic": 20, "has_operational_workflow": 60, "has_data_integration": 55, "has_accumulative_memory": 60, "has_verifiable_outcome": 55, "has_followup_action": 55, "has_switching_cost": 70, "improves_with_use": 70, "survives_model_improvement": 65, "network_effect": 85, "distribution_loop": 50, "data_advantage": 50},
    "REVERSE_MARKETPLACE": {"generic_ai_can_solve": 20, "output_is_generic": 25, "has_operational_workflow": 55, "has_data_integration": 50, "has_accumulative_memory": 55, "has_verifiable_outcome": 55, "has_followup_action": 55, "has_switching_cost": 65, "improves_with_use": 65, "survives_model_improvement": 60, "network_effect": 80, "distribution_loop": 45, "data_advantage": 45},
    "DATA_PRODUCT": {"generic_ai_can_solve": 40, "output_is_generic": 45, "has_operational_workflow": 55, "has_data_integration": 70, "has_accumulative_memory": 75, "has_verifiable_outcome": 70, "has_followup_action": 55, "has_switching_cost": 55, "improves_with_use": 75, "survives_model_improvement": 70, "network_effect": 20, "distribution_loop": 30, "data_advantage": 85},
    "API": {"generic_ai_can_solve": 35, "output_is_generic": 30, "has_operational_workflow": 70, "has_data_integration": 80, "has_accumulative_memory": 50, "has_verifiable_outcome": 65, "has_followup_action": 70, "has_switching_cost": 70, "improves_with_use": 50, "survives_model_improvement": 55, "network_effect": 25, "distribution_loop": 30, "data_advantage": 50},
    "VERIFICATION_TOOL": {"generic_ai_can_solve": 45, "output_is_generic": 40, "has_operational_workflow": 65, "has_data_integration": 60, "has_accumulative_memory": 60, "has_verifiable_outcome": 85, "has_followup_action": 60, "has_switching_cost": 55, "improves_with_use": 60, "survives_model_improvement": 60, "network_effect": 20, "distribution_loop": 30, "data_advantage": 55},
    "TRUST_PRODUCT": {"generic_ai_can_solve": 30, "output_is_generic": 30, "has_operational_workflow": 60, "has_data_integration": 55, "has_accumulative_memory": 70, "has_verifiable_outcome": 75, "has_followup_action": 55, "has_switching_cost": 75, "improves_with_use": 75, "survives_model_improvement": 70, "network_effect": 60, "distribution_loop": 35, "data_advantage": 55},
    "SAVINGS_PRODUCT": {"generic_ai_can_solve": 45, "output_is_generic": 40, "has_operational_workflow": 60, "has_data_integration": 60, "has_accumulative_memory": 65, "has_verifiable_outcome": 80, "has_followup_action": 65, "has_switching_cost": 55, "improves_with_use": 65, "survives_model_improvement": 55, "network_effect": 15, "distribution_loop": 35, "data_advantage": 50},
    "COMMUNITY_PLATFORM": {"generic_ai_can_solve": 25, "output_is_generic": 25, "has_operational_workflow": 55, "has_data_integration": 45, "has_accumulative_memory": 70, "has_verifiable_outcome": 55, "has_followup_action": 50, "has_switching_cost": 75, "improves_with_use": 75, "survives_model_improvement": 70, "network_effect": 90, "distribution_loop": 60, "data_advantage": 50},
    "AGENT_INFRASTRUCTURE": {"generic_ai_can_solve": 35, "output_is_generic": 30, "has_operational_workflow": 75, "has_data_integration": 80, "has_accumulative_memory": 55, "has_verifiable_outcome": 65, "has_followup_action": 75, "has_switching_cost": 70, "improves_with_use": 55, "survives_model_improvement": 55, "network_effect": 50, "distribution_loop": 40, "data_advantage": 55},
    "VALIDABLE_CONCIERGE": {"generic_ai_can_solve": 55, "output_is_generic": 50, "has_operational_workflow": 70, "has_data_integration": 35, "has_accumulative_memory": 40, "has_verifiable_outcome": 65, "has_followup_action": 60, "has_switching_cost": 40, "improves_with_use": 40, "survives_model_improvement": 45, "network_effect": 10, "distribution_loop": 35, "data_advantage": 30},
    "LOCAL_PRODUCT": {"generic_ai_can_solve": 35, "output_is_generic": 35, "has_operational_workflow": 65, "has_data_integration": 50, "has_accumulative_memory": 55, "has_verifiable_outcome": 60, "has_followup_action": 60, "has_switching_cost": 60, "improves_with_use": 55, "survives_model_improvement": 55, "network_effect": 40, "distribution_loop": 60, "data_advantage": 40},
    "SUBSCRIPTION": {"generic_ai_can_solve": 45, "output_is_generic": 40, "has_operational_workflow": 60, "has_data_integration": 55, "has_accumulative_memory": 60, "has_verifiable_outcome": 60, "has_followup_action": 70, "has_switching_cost": 60, "improves_with_use": 60, "survives_model_improvement": 55, "network_effect": 20, "distribution_loop": 35, "data_advantage": 45},
    "PAY_FOR_RESULT": {"generic_ai_can_solve": 35, "output_is_generic": 35, "has_operational_workflow": 75, "has_data_integration": 55, "has_accumulative_memory": 55, "has_verifiable_outcome": 85, "has_followup_action": 65, "has_switching_cost": 55, "improves_with_use": 55, "survives_model_improvement": 55, "network_effect": 15, "distribution_loop": 35, "data_advantage": 45},
    "TRANSACTIONAL_PRODUCT": {"generic_ai_can_solve": 50, "output_is_generic": 45, "has_operational_workflow": 55, "has_data_integration": 55, "has_accumulative_memory": 45, "has_verifiable_outcome": 60, "has_followup_action": 60, "has_switching_cost": 50, "improves_with_use": 50, "survives_model_improvement": 50, "network_effect": 20, "distribution_loop": 40, "data_advantage": 40},
    "MICROINSURANCE_PATTERN": {"generic_ai_can_solve": 30, "output_is_generic": 30, "has_operational_workflow": 70, "has_data_integration": 60, "has_accumulative_memory": 65, "has_verifiable_outcome": 75, "has_followup_action": 65, "has_switching_cost": 70, "improves_with_use": 65, "survives_model_improvement": 60, "network_effect": 55, "distribution_loop": 40, "data_advantage": 50},
    "PRO_TOOL": {"generic_ai_can_solve": 40, "output_is_generic": 35, "has_operational_workflow": 75, "has_data_integration": 65, "has_accumulative_memory": 60, "has_verifiable_outcome": 65, "has_followup_action": 70, "has_switching_cost": 60, "improves_with_use": 55, "survives_model_improvement": 55, "network_effect": 25, "distribution_loop": 35, "data_advantage": 45},
    "PROSUMER_PRODUCT": {"generic_ai_can_solve": 55, "output_is_generic": 50, "has_operational_workflow": 55, "has_data_integration": 50, "has_accumulative_memory": 45, "has_verifiable_outcome": 55, "has_followup_action": 55, "has_switching_cost": 45, "improves_with_use": 50, "survives_model_improvement": 50, "network_effect": 20, "distribution_loop": 40, "data_advantage": 40},
    "B2B_LICENSE": {"generic_ai_can_solve": 40, "output_is_generic": 35, "has_operational_workflow": 65, "has_data_integration": 60, "has_accumulative_memory": 55, "has_verifiable_outcome": 60, "has_followup_action": 60, "has_switching_cost": 65, "improves_with_use": 55, "survives_model_improvement": 55, "network_effect": 20, "distribution_loop": 30, "data_advantage": 45},
    "WHITE_LABEL": {"generic_ai_can_solve": 45, "output_is_generic": 40, "has_operational_workflow": 60, "has_data_integration": 55, "has_accumulative_memory": 50, "has_verifiable_outcome": 55, "has_followup_action": 55, "has_switching_cost": 50, "improves_with_use": 50, "survives_model_improvement": 50, "network_effect": 15, "distribution_loop": 45, "data_advantage": 40},
    "ACCUMULATIVE_DATASET": {"generic_ai_can_solve": 35, "output_is_generic": 40, "has_operational_workflow": 60, "has_data_integration": 75, "has_accumulative_memory": 85, "has_verifiable_outcome": 70, "has_followup_action": 55, "has_switching_cost": 60, "improves_with_use": 85, "survives_model_improvement": 75, "network_effect": 25, "distribution_loop": 30, "data_advantage": 90},
    "BENCHMARKING_NETWORK": {"generic_ai_can_solve": 25, "output_is_generic": 25, "has_operational_workflow": 60, "has_data_integration": 65, "has_accumulative_memory": 75, "has_verifiable_outcome": 70, "has_followup_action": 55, "has_switching_cost": 70, "improves_with_use": 80, "survives_model_improvement": 75, "network_effect": 85, "distribution_loop": 45, "data_advantage": 70},
    "COLLABORATIVE_TOOL": {"generic_ai_can_solve": 35, "output_is_generic": 35, "has_operational_workflow": 65, "has_data_integration": 60, "has_accumulative_memory": 60, "has_verifiable_outcome": 55, "has_followup_action": 55, "has_switching_cost": 65, "improves_with_use": 70, "survives_model_improvement": 60, "network_effect": 70, "distribution_loop": 45, "data_advantage": 45},
    "IDLE_ASSET_INCOME": {"generic_ai_can_solve": 30, "output_is_generic": 30, "has_operational_workflow": 65, "has_data_integration": 55, "has_accumulative_memory": 50, "has_verifiable_outcome": 65, "has_followup_action": 60, "has_switching_cost": 55, "improves_with_use": 55, "survives_model_improvement": 55, "network_effect": 45, "distribution_loop": 50, "data_advantage": 45},
    "FRAGMENTED_DEMAND_BUNDLER": {"generic_ai_can_solve": 30, "output_is_generic": 30, "has_operational_workflow": 60, "has_data_integration": 55, "has_accumulative_memory": 55, "has_verifiable_outcome": 60, "has_followup_action": 55, "has_switching_cost": 55, "improves_with_use": 60, "survives_model_improvement": 55, "network_effect": 60, "distribution_loop": 50, "data_advantage": 45},
    "AGENT_SERVICE_PROVIDER": {"generic_ai_can_solve": 35, "output_is_generic": 30, "has_operational_workflow": 75, "has_data_integration": 80, "has_accumulative_memory": 55, "has_verifiable_outcome": 65, "has_followup_action": 75, "has_switching_cost": 70, "improves_with_use": 55, "survives_model_improvement": 55, "network_effect": 55, "distribution_loop": 45, "data_advantage": 55},
}

# Ajustes por palabras en el mecanismo/problema del concepto.
_TEXT_ADJUSTMENTS = (
    (("informe", "reporte", "documento", "contenido", "artículo", "resumen"), ("output_is_generic", +25), ("generic_ai_can_solve", +15)),
    (("chat", "chatbot", "asistente", "conversación"), ("generic_ai_can_solve", +25), ("output_is_generic", +15), ("has_operational_workflow", -25), ("has_data_integration", -20), ("has_accumulative_memory", -15)),
    (("integración", "integracion", "api", "conexión", "conexion", "sincroniza"), ("has_data_integration", +20)),
    (("memoria", "historial", "acumula", "histórico", "historico"), ("has_accumulative_memory", +20)),
    (("verific", "auditoría", "auditoria", "trazab"), ("has_verifiable_outcome", +20)),
    (("automatiza", "programa", "ejecuta", "script"), ("has_followup_action", +15), ("has_operational_workflow", +10)),
    (("comunidad", "red", "grupo", "colectivo"), ("network_effect", +25)),
    (("comparte", "referir", "invita", "bucle"), ("distribution_loop", +25)),
    (("datos", "dataset", "base de datos"), ("data_advantage", +20)),
)


def derive_substitution_answers(concept: dict[str, Any]) -> SubstitutionAnswers:
    """Respuestas del test derivadas de la estructura del concepto (offline).

    Es una estimación estructural, no evidencia: la etiqueta de método lo
    deja claro. Las misiones de investigación pueden sustituir estas
    respuestas por otras fundamentadas.
    """
    default = {
        "generic_ai_can_solve": 45.0,
        "output_is_generic": 40.0,
        "has_operational_workflow": 55.0,
        "has_data_integration": 45.0,
        "has_accumulative_memory": 40.0,
        "has_verifiable_outcome": 50.0,
        "has_followup_action": 50.0,
        "has_switching_cost": 45.0,
        "improves_with_use": 45.0,
        "survives_model_improvement": 45.0,
        "network_effect": 20.0,
        "distribution_loop": 30.0,
        "data_advantage": 35.0,
    }
    profile = dict(ARCHETYPE_SUBSTITUTION_PROFILES.get(concept.get("archetype_key") or "", {})) or default
    text = " ".join(
        str(concept.get(k) or "") for k in ("title", "problem_hypothesis", "mechanism", "outcome_hypothesis")
    ).lower()
    for words, *adjustments in _TEXT_ADJUSTMENTS:
        if any(w in text for w in words):
            for key, delta in adjustments:
                profile[key] = min(100.0, profile.get(key, 50.0) + delta)
    return SubstitutionAnswers(**{k: round(v, 2) for k, v in profile.items()})


# Perfiles económicos estructurales por arquetipo (estimaciones, no evidencia).
ARCHETYPE_ECONOMIC_PROFILES: dict[str, dict[str, float]] = {
    "VERTICAL_SAAS": {"validation_speed": 55, "gross_margin": 80, "operational_simplicity": 45, "recurrence": 85, "distribution": 35},
    "SOFTWARE_ENABLED_SERVICE": {"validation_speed": 70, "gross_margin": 60, "operational_simplicity": 60, "recurrence": 40, "distribution": 45},
    "MARKETPLACE": {"validation_speed": 40, "gross_margin": 55, "operational_simplicity": 50, "recurrence": 65, "distribution": 55},
    "REVERSE_MARKETPLACE": {"validation_speed": 45, "gross_margin": 55, "operational_simplicity": 50, "recurrence": 60, "distribution": 50},
    "DATA_PRODUCT": {"validation_speed": 55, "gross_margin": 85, "operational_simplicity": 55, "recurrence": 75, "distribution": 40},
    "API": {"validation_speed": 60, "gross_margin": 85, "operational_simplicity": 60, "recurrence": 70, "distribution": 40},
    "VERIFICATION_TOOL": {"validation_speed": 65, "gross_margin": 80, "operational_simplicity": 65, "recurrence": 60, "distribution": 45},
    "TRUST_PRODUCT": {"validation_speed": 40, "gross_margin": 70, "operational_simplicity": 55, "recurrence": 75, "distribution": 45},
    "SAVINGS_PRODUCT": {"validation_speed": 65, "gross_margin": 75, "operational_simplicity": 65, "recurrence": 60, "distribution": 45},
    "COMMUNITY_PLATFORM": {"validation_speed": 45, "gross_margin": 75, "operational_simplicity": 50, "recurrence": 85, "distribution": 60},
    "AGENT_INFRASTRUCTURE": {"validation_speed": 55, "gross_margin": 85, "operational_simplicity": 55, "recurrence": 70, "distribution": 40},
    "VALIDABLE_CONCIERGE": {"validation_speed": 85, "gross_margin": 65, "operational_simplicity": 80, "recurrence": 35, "distribution": 50},
    "LOCAL_PRODUCT": {"validation_speed": 70, "gross_margin": 65, "operational_simplicity": 75, "recurrence": 55, "distribution": 70},
    "SUBSCRIPTION": {"validation_speed": 60, "gross_margin": 80, "operational_simplicity": 60, "recurrence": 90, "distribution": 40},
    "PAY_FOR_RESULT": {"validation_speed": 70, "gross_margin": 70, "operational_simplicity": 65, "recurrence": 55, "distribution": 45},
    "TRANSACTIONAL_PRODUCT": {"validation_speed": 65, "gross_margin": 75, "operational_simplicity": 70, "recurrence": 40, "distribution": 45},
    "MICROINSURANCE_PATTERN": {"validation_speed": 50, "gross_margin": 65, "operational_simplicity": 55, "recurrence": 80, "distribution": 40},
    "PRO_TOOL": {"validation_speed": 65, "gross_margin": 75, "operational_simplicity": 65, "recurrence": 60, "distribution": 40},
    "PROSUMER_PRODUCT": {"validation_speed": 70, "gross_margin": 75, "operational_simplicity": 70, "recurrence": 55, "distribution": 45},
    "B2B_LICENSE": {"validation_speed": 55, "gross_margin": 85, "operational_simplicity": 60, "recurrence": 75, "distribution": 35},
    "WHITE_LABEL": {"validation_speed": 55, "gross_margin": 80, "operational_simplicity": 65, "recurrence": 65, "distribution": 50},
    "ACCUMULATIVE_DATASET": {"validation_speed": 55, "gross_margin": 85, "operational_simplicity": 55, "recurrence": 80, "distribution": 40},
    "BENCHMARKING_NETWORK": {"validation_speed": 50, "gross_margin": 75, "operational_simplicity": 50, "recurrence": 80, "distribution": 50},
    "COLLABORATIVE_TOOL": {"validation_speed": 55, "gross_margin": 75, "operational_simplicity": 55, "recurrence": 70, "distribution": 50},
    "IDLE_ASSET_INCOME": {"validation_speed": 65, "gross_margin": 70, "operational_simplicity": 65, "recurrence": 50, "distribution": 55},
    "FRAGMENTED_DEMAND_BUNDLER": {"validation_speed": 55, "gross_margin": 60, "operational_simplicity": 55, "recurrence": 55, "distribution": 60},
    "AGENT_SERVICE_PROVIDER": {"validation_speed": 60, "gross_margin": 85, "operational_simplicity": 60, "recurrence": 70, "distribution": 45},
}

# Perfil de dolor económico por territorio (estimación estructural).
TERRITORY_PAIN_PROFILES: dict[str, float] = {
    "expensive_slow_services": 80,
    "opaque_intermediaries": 78,
    "hard_to_verify_info": 75,
    "high_uncertainty_decisions": 75,
    "fraud_verification": 72,
    "regulatory_change": 72,
    "invisible_admin_work": 70,
    "app_misalignment": 68,
    "small_businesses": 68,
    "pay_for_outcome_markets": 65,
    "underused_assets": 65,
    "machine_economy": 62,
    "agent_services": 62,
    "ai_proliferation_problems": 62,
    "digital_trust": 62,
    "fragmented_markets": 60,
    "loneliness_social_coordination": 58,
    "untapped_public_data": 58,
    "aging": 58,
    "local_logistics": 55,
    "sustainability_with_incentive": 55,
    "freelancers": 55,
    "real_estate": 55,
    "tourism": 50,
    "creators": 50,
    "amateur_sports": 48,
    "home": 48,
    "education": 48,
    "new_ai_interfaces": 45,
    "strong_identity_communities": 45,
    "new_human_behaviors": 40,
}


def estimate_venture_scores(
    concept: dict[str, Any],
    substitution: SubstitutionTest,
    *,
    demand_evidence: bool = False,
) -> dict[str, float]:
    """Estima los 11 criterios del Venture Quality Score (0-100 cada uno).

    Determinista y sin LLM. Combina el resultado del substitution test con
    perfiles estructurales de arquetipo y territorio. ``demand_evidence``
    solo es True cuando una misión de investigación aportó evidencia real;
    en offline, proven_demand queda en 0 (no se inventa demanda).
    """
    archetype = concept.get("archetype_key") or ""
    econ = ARCHETYPE_ECONOMIC_PROFILES.get(archetype, ARCHETYPE_ECONOMIC_PROFILES["VERTICAL_SAAS"])
    pain = TERRITORY_PAIN_PROFILES.get(concept.get("territory_key") or "", 50.0)

    # Dolor económico: perfil de territorio ajustado por claridad del comprador.
    economic_pain = pain
    if concept.get("buyer_hypothesis"):
        economic_pain = min(100.0, economic_pain + 8)
    if not concept.get("outcome_hypothesis"):
        economic_pain = max(0.0, economic_pain - 10)  # sin resultado concreto el dolor es menos creíble

    a = substitution.answers
    defensibility = {
        "COMMODITY_WRAPPER": 5.0,
        "WEAK_DIFFERENTIATION": 25.0,
        "DEFENSIBLE_WORKFLOW": 55.0,
        "DATA_ADVANTAGE": 75.0,
        "DISTRIBUTION_ADVANTAGE": 78.0,
        "NETWORK_ADVANTAGE": 82.0,
        "COMPOUNDING_SYSTEM": 88.0,
    }[substitution.classification]
    defensibility = min(100.0, defensibility + 0.15 * a.has_accumulative_memory + 0.1 * a.data_advantage)

    demonstrability = 50.0
    outcome = str(concept.get("outcome_hypothesis") or "").lower()
    if any(w in outcome for w in ("%", "eur", "usd", "€", "$", "horas", "días", "dias", "reducir", "aumentar")):
        demonstrability += 25
    if substitution.classification in ("VERIFICATION_TOOL", "PAY_FOR_RESULT") or a.has_verifiable_outcome >= 70:
        demonstrability = min(100.0, demonstrability + 15)

    scores = {
        "economic_pain": round(min(100.0, economic_pain), 2),
        "proven_demand": 0.0 if not demand_evidence else 70.0,  # desconocido en offline; nunca se inventa
        "general_ai_resistance": substitution.general_ai_resistance,
        "defensibility": round(min(100.0, defensibility), 2),
        "distribution": round(min(100.0, econ["distribution"] + 0.25 * a.distribution_loop), 2),
        "originality": 0.0,  # se recalcula en venture_score con novelty/utility
        "validation_speed": econ["validation_speed"],
        "gross_margin": econ["gross_margin"],
        "recurrence": round(min(100.0, econ["recurrence"] + 0.1 * a.has_followup_action), 2),
        "demonstrability": round(min(100.0, demonstrability), 2),
        "operational_simplicity": econ["operational_simplicity"],
    }
    return {k: round(max(0.0, min(100.0, v)), 2) for k, v in scores.items()}
