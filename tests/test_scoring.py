"""Pruebas del motor de puntuación (funciones puras)."""
from __future__ import annotations

import pytest

from app.models.enums import Basis, Decision
from app.models.evaluation import CriterionScore
from app.scoring.engine import (
    ScoreInput,
    compute_final_score,
    confidence_score,
    decide,
    decision_from_score,
    evidence_quality_score,
)

WEIGHTS = {
    "pain": 0.20,
    "demand": 0.20,
    "customer_reach": 0.15,
    "automation": 0.15,
    "margin": 0.10,
    "build_speed": 0.10,
    "differentiation": 0.05,
    "safety": 0.05,
}


def criteria(**scores) -> dict[str, CriterionScore]:
    return {k: CriterionScore(score=float(v), basis=Basis.estimate) for k, v in scores.items()}


def test_weighted_score_matches_hand_calculation():
    c = criteria(pain=100, demand=100, customer_reach=100, automation=100, margin=100, build_speed=100, differentiation=100, safety=100)
    assert compute_final_score(c, WEIGHTS) == 100.0

    c = criteria(pain=50, demand=50, customer_reach=50, automation=50, margin=50, build_speed=50, differentiation=50, safety=50)
    assert compute_final_score(c, WEIGHTS) == 50.0

    c = criteria(pain=100, demand=0, customer_reach=0, automation=0, margin=0, build_speed=0, differentiation=0, safety=0)
    assert compute_final_score(c, WEIGHTS) == 20.0  # solo el peso de pain


def test_missing_criterion_counts_zero():
    c = {"pain": CriterionScore(score=100, basis=Basis.evidence)}
    assert compute_final_score(c, WEIGHTS) == 20.0


def test_decision_bands_boundaries():
    assert decision_from_score(75) == Decision.approved
    assert decision_from_score(74.99) == Decision.needs_more_research
    assert decision_from_score(60) == Decision.needs_more_research
    assert decision_from_score(59.99) == Decision.deferred
    assert decision_from_score(40) == Decision.deferred
    assert decision_from_score(39.99) == Decision.rejected
    assert decision_from_score(0) == Decision.rejected


def test_evidence_quality_no_evidence_is_zero():
    assert evidence_quality_score(reliability_values=[], verified_evidence_count=0, total_evidence_count=0, independent_groups=set()) == 0.0


def test_evidence_quality_full_marks():
    q = evidence_quality_score(
        reliability_values=[1.0, 1.0, 1.0],
        verified_evidence_count=3,
        total_evidence_count=3,
        independent_groups={"a", "b", "c"},
    )
    assert q == 100.0


def test_evidence_quality_penalizes_unverified():
    unverified = evidence_quality_score(
        reliability_values=[0.8, 0.8],
        verified_evidence_count=0,
        total_evidence_count=2,
        independent_groups={"a", "b"},
    )
    verified = evidence_quality_score(
        reliability_values=[0.8, 0.8],
        verified_evidence_count=2,
        total_evidence_count=2,
        independent_groups={"a", "b"},
    )
    assert unverified < verified


def test_evidence_quality_penalizes_low_reliability():
    low = evidence_quality_score(
        reliability_values=[0.2, 0.2],
        verified_evidence_count=2,
        total_evidence_count=2,
        independent_groups={"a", "b"},
    )
    high = evidence_quality_score(
        reliability_values=[0.9, 0.9],
        verified_evidence_count=2,
        total_evidence_count=2,
        independent_groups={"a", "b"},
    )
    assert low < high


def test_evidence_quality_rewards_independence():
    one_group = evidence_quality_score(
        reliability_values=[0.9, 0.9],
        verified_evidence_count=2,
        total_evidence_count=2,
        independent_groups={"a"},
    )
    three_groups = evidence_quality_score(
        reliability_values=[0.9, 0.9],
        verified_evidence_count=2,
        total_evidence_count=2,
        independent_groups={"a", "b", "c"},
    )
    assert three_groups > one_group


def test_confidence_reflects_basis():
    all_evidence = {k: CriterionScore(score=80, basis=Basis.evidence) for k in WEIGHTS}
    all_unknown = {k: CriterionScore(score=80, basis=Basis.unknown) for k in WEIGHTS}
    c_ev = confidence_score(criteria=all_evidence, weights=WEIGHTS, evidence_quality=100)
    c_unk = confidence_score(criteria=all_unknown, weights=WEIGHTS, evidence_quality=0)
    assert c_ev > c_unk
    assert c_ev == 100.0
    assert c_unk == 0.0


def test_decide_blocks_when_blockers_present():
    c = criteria(pain=90, demand=90, customer_reach=90, automation=90, margin=90, build_speed=90, differentiation=90, safety=90)
    result = decide(
        ScoreInput(
            criteria=c,
            weights=WEIGHTS,
            blockers=["No tiene un cliente objetivo concreto."],
            reliability_values=[0.9],
            total_evidence_count=1,
            verified_evidence_count=1,
            independent_groups={"a"},
        )
    )
    assert result.final_score == 90.0
    assert result.decision == Decision.blocked
    assert "cliente objetivo" in result.rejection_reason


def test_decide_approved_reason():
    c = criteria(pain=90, demand=90, customer_reach=90, automation=90, margin=90, build_speed=90, differentiation=90, safety=90)
    result = decide(
        ScoreInput(
            criteria=c,
            weights=WEIGHTS,
            blockers=[],
            reliability_values=[0.9],
            total_evidence_count=1,
            verified_evidence_count=1,
            independent_groups={"a"},
        )
    )
    assert result.decision == Decision.approved
    assert result.approval_reason


def test_reproducible_same_inputs_same_output():
    c = criteria(pain=70, demand=60, customer_reach=50, automation=80, margin=40, build_speed=60, differentiation=30, safety=85)
    inputs = dict(
        criteria=c,
        weights=WEIGHTS,
        blockers=[],
        reliability_values=[0.7, 0.6],
        total_evidence_count=2,
        verified_evidence_count=1,
        independent_groups={"a", "b"},
    )
    r1 = decide(ScoreInput(**inputs))
    r2 = decide(ScoreInput(**inputs))
    assert r1.final_score == r2.final_score
    assert r1.decision == r2.decision
    assert r1.evidence_quality_score == r2.evidence_quality_score
    assert r1.confidence_score == r2.confidence_score


@pytest.mark.parametrize(
    "score,expected",
    [(95, Decision.approved), (75, Decision.approved), (70, Decision.needs_more_research), (45, Decision.deferred), (10, Decision.rejected)],
)
def test_decision_from_score_parametrized(score, expected):
    assert decision_from_score(score) == expected
