"""Motor de puntuación determinista (ver docs/SCORING.md)."""
from app.scoring.engine import (
    ScoreResult,
    compute_final_score,
    confidence_score,
    decide,
    decision_from_score,
    evidence_quality_score,
    independent_evidence_count,
)

__all__ = [
    "ScoreResult",
    "compute_final_score",
    "confidence_score",
    "decide",
    "decision_from_score",
    "evidence_quality_score",
    "independent_evidence_count",
]
