"""Reglas de decisión: bandas, bloqueadores duros y condiciones de cambio."""
from __future__ import annotations

import pytest

from app.models.enums import Decision
from app.scoring.engine import ScoreInput, decide

WEIGHTS = {
    "pain": 0.20, "demand": 0.20, "customer_reach": 0.15, "automation": 0.15,
    "margin": 0.10, "build_speed": 0.10, "differentiation": 0.05, "safety": 0.05,
}


def _input(blockers=(), score=90):
    from app.models.evaluation import CriterionScore
    from app.models.enums import Basis

    criteria = {k: CriterionScore(score=score, basis=Basis.evidence) for k in WEIGHTS}
    return ScoreInput(
        criteria=criteria,
        weights=WEIGHTS,
        blockers=list(blockers),
        reliability_values=[0.9],
        total_evidence_count=1,
        verified_evidence_count=1,
        independent_groups={"a"},
    )


def test_every_hard_condition_blocks():
    """Cada condición dura de la especificación debe bloquear por separado."""
    conditions = [
        "No tiene un cliente objetivo concreto.",
        "No contiene evidencias guardadas.",
        "Depende de datos inventados.",
        "Riesgo grave: actividad regulada.",
        "Requiere un gasto inicial elevado.",
        "No existe una forma razonable de llegar a compradores.",
        "Depende de una plataforma externa que puede prohibir la automatización.",
        "Exige una actividad regulada que el sistema no puede cumplir.",
    ]
    for condition in conditions:
        result = decide(_input(blockers=[condition]))
        assert result.decision == Decision.blocked, f"{condition} debería bloquear"
        assert condition in result.rejection_reason


def test_blocked_even_with_perfect_score():
    result = decide(_input(blockers=["Riesgo grave: promesa financiera."], score=100))
    assert result.decision == Decision.blocked


def test_no_blockers_high_score_approved():
    result = decide(_input(blockers=[], score=90))
    assert result.decision == Decision.approved


def test_conditions_to_change_decision_are_visible():
    """La evaluación expone el motivo de rechazo (condición que haría cambiar la decisión)."""
    result = decide(_input(blockers=["No contiene evidencias guardadas."], score=80))
    assert result.decision == Decision.blocked
    assert "No contiene evidencias guardadas" in result.rejection_reason


def test_custom_bands_configurable():
    from app.scoring.engine import decision_from_score

    bands = [
        {"min_score": 90, "decision": "approved"},
        {"min_score": 70, "decision": "needs_more_research"},
        {"min_score": 50, "decision": "deferred"},
        {"min_score": 0, "decision": "rejected"},
    ]
    assert decision_from_score(85, bands) == Decision.needs_more_research
    assert decision_from_score(92, bands) == Decision.approved
