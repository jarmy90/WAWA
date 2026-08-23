"""Motor de puntuación: funciones puras, deterministas y sin efectos.

Una oportunidad no puede aprobarse si:
- no hay cliente objetivo concreto,
- no contiene evidencias guardadas,
- depende de datos inventados,
- presenta un riesgo grave,
- requiere un gasto inicial elevado,
- no existe forma razonable de llegar a compradores,
- depende enteramente de una plataforma externa que prohíba la automatización,
- exige una actividad regulada que el sistema no pueda cumplir.

Estas condiciones llegan como ``blockers`` (listas de texto). Si hay algún
blocker, la decisión es ``blocked`` aunque la puntuación sea alta.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Basis, Decision
from app.models.evaluation import CriterionScore, CRITERIA_KEYS

DECISION_BANDS_DEFAULT = [
    {"min_score": 75, "decision": Decision.approved},
    {"min_score": 60, "decision": Decision.needs_more_research},
    {"min_score": 40, "decision": Decision.deferred},
    {"min_score": 0, "decision": Decision.rejected},
]


class ScoreInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criteria: dict[str, CriterionScore] = Field(default_factory=dict)
    weights: dict[str, float] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    verified_evidence_count: int = 0
    total_evidence_count: int = 0
    reliability_values: list[float] = Field(default_factory=list)
    independent_groups: set[str] = Field(default_factory=set)
    bands: list[dict] = Field(default_factory=lambda: DECISION_BANDS_DEFAULT)


class ScoreResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_score: float = Field(ge=0, le=100)
    evidence_quality_score: float = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=100)
    independent_evidence_count: int = 0
    unverified_assumptions_count: int = 0
    per_criterion: dict[str, CriterionScore] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    decision: Decision = Decision.deferred
    approval_reason: str | None = None
    rejection_reason: str | None = None


# ---------------------------------------------------------------------------
# Funciones puras
# ---------------------------------------------------------------------------
def compute_final_score(criteria: dict[str, CriterionScore], weights: dict[str, float]) -> float:
    """Media ponderada de los criterios (0-100). Los criterios ausentes cuentan 0."""
    total_weight = sum(weights.values()) or 1.0
    acc = 0.0
    for key, weight in weights.items():
        score = criteria.get(key).score if criteria.get(key) else 0.0
        acc += score * weight
    return round(acc / total_weight, 2)


def evidence_quality_score(
    *,
    reliability_values: list[float],
    verified_evidence_count: int,
    total_evidence_count: int,
    independent_groups: set[str],
) -> float:
    """Calidad de la evidencia (0-100).

    - Sin evidencia -> 0.
    - Base: fiabilidad media ponderada por verificación (verificada x1.0,
      no verificada x0.5).
    - Multiplicador de independencia: hasta 3 grupos independientes.
    """
    if not total_evidence_count or not reliability_values:
        return 0.0
    avg_rel = sum(reliability_values) / len(reliability_values)
    verified_ratio = verified_evidence_count / total_evidence_count
    verification_factor = 0.5 + 0.5 * verified_ratio
    independence_factor = min(len(independent_groups), 3) / 3.0
    raw = avg_rel * verification_factor * (0.4 + 0.6 * independence_factor)
    return round(min(100.0, raw * 100), 2)


def confidence_score(
    *,
    criteria: dict[str, CriterionScore],
    weights: dict[str, float],
    evidence_quality: float,
) -> float:
    """Confianza (0-100): cobertura ponderada por base + calidad de evidencia.

    - base ``evidence`` -> 1.0
    - base ``estimate`` -> 0.5
    - base ``unknown``  -> 0.0
    """
    total_weight = sum(weights.values()) or 1.0
    coverage = 0.0
    for key, weight in weights.items():
        criterion = criteria.get(key)
        if not criterion:
            continue
        factor = {Basis.evidence: 1.0, Basis.estimate: 0.5, Basis.unknown: 0.0}[criterion.basis]
        coverage += weight * factor
    coverage /= total_weight
    raw = 0.7 * coverage * 100 + 0.3 * evidence_quality
    return round(max(0.0, min(100.0, raw)), 2)


def independent_evidence_count(groups: set[str]) -> int:
    """Número de grupos de independencia distintos (sin contar 'none'/vacío)."""
    return len({g for g in groups if g and g != "none"})


def decision_from_score(score: float, bands: list[dict] | None = None) -> Decision:
    """Banda de decisión según puntuación (sin blockers)."""
    bands = bands or DECISION_BANDS_DEFAULT
    for band in sorted(bands, key=lambda b: -b["min_score"]):
        if score >= band["min_score"]:
            return Decision(band["decision"])
    return Decision.rejected


def blockers_reason(blockers: list[str]) -> str | None:
    if not blockers:
        return None
    return " | ".join(blockers[:5])


def decide(score_input: ScoreInput) -> ScoreResult:
    """Calcula la puntuación final y la decisión aplicando blockers."""
    criteria = score_input.criteria
    weights = score_input.weights
    final = compute_final_score(criteria, weights)

    eql = evidence_quality_score(
        reliability_values=score_input.reliability_values,
        verified_evidence_count=score_input.verified_evidence_count,
        total_evidence_count=score_input.total_evidence_count,
        independent_groups=score_input.independent_groups,
    )
    conf = confidence_score(criteria=criteria, weights=weights, evidence_quality=eql)
    n_independent = independent_evidence_count(score_input.independent_groups)
    n_assumptions = len(score_input.assumptions)

    blocked = bool(score_input.blockers)
    decision = Decision.blocked if blocked else decision_from_score(final, score_input.bands)

    approval_reason = None
    rejection_reason = None
    if decision == Decision.approved:
        approval_reason = (
            f"Puntuación {final:.1f} >= 75, sin blockers, con {n_independent} grupo(s) de evidencia "
            f"independiente(s) y confianza {conf:.0f}%. El experimento propuesto es barato y medible."
        )
    elif decision == Decision.blocked:
        rejection_reason = f"Bloqueada por condiciones duras: {blockers_reason(score_input.blockers)}"
    elif decision == Decision.rejected:
        rejection_reason = (
            f"Puntuación {final:.1f} < 40. Sin evidencia suficiente o criterios demasiado débiles "
            "para justificar cualquier gasto."
        )
    elif decision == Decision.needs_more_research:
        rejection_reason = (
            f"Puntuación {final:.1f} (60-74): prometedora pero con incógnitas clave. "
            "Investigar demanda, precios y competencia antes de decidir."
        )
    elif decision == Decision.deferred:
        rejection_reason = f"Puntuación {final:.1f} (40-59): se aplaza hasta que mejore la evidencia o el coste de prueba baje."

    return ScoreResult(
        final_score=final,
        evidence_quality_score=eql,
        confidence_score=conf,
        independent_evidence_count=n_independent,
        unverified_assumptions_count=n_assumptions,
        per_criterion=criteria,
        blockers=list(score_input.blockers),
        decision=decision,
        approval_reason=approval_reason,
        rejection_reason=rejection_reason,
    )


def criteria_keys() -> tuple[str, ...]:
    return CRITERIA_KEYS
