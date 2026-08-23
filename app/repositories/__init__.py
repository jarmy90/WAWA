"""Capa de persistencia: SQLite (stdlib) + repositorios tipados.

Se eligió ``sqlite3`` de la stdlib en lugar de SQLAlchemy para el MVP:
menos dependencias, cero setup, transacciones simples y suficiente para el
modelo de datos actual. Si el modelo crece (migraciones, varios nodos),
migrar a SQLAlchemy/Alembic es directo porque los repositorios encapsulan
toda la SQL.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.repositories.competitors import CompetitorRepository
from app.repositories.costs import CostRepository
from app.repositories.db import connect, init_db
from app.repositories.decision_log import DecisionLogRepository
from app.repositories.discovery import DiscoveryRepository
from app.repositories.engine import EngineRepository
from app.repositories.evaluations import EvaluationRepository
from app.repositories.evidence import EvidenceRepository
from app.repositories.experiments import ExperimentRepository
from app.repositories.ledger import LedgerRepository
from app.repositories.opportunities import OpportunityRepository
from app.repositories.reviews import ReviewRepository


@dataclass
class Repos:
    """Namespace con todos los repositorios compartiendo una conexión."""

    opportunities: OpportunityRepository
    evidence: EvidenceRepository
    competitors: CompetitorRepository
    evaluations: EvaluationRepository
    experiments: ExperimentRepository
    decision_log: DecisionLogRepository
    costs: CostRepository
    engine: EngineRepository
    ledger: LedgerRepository
    discovery: DiscoveryRepository
    reviews: ReviewRepository


def build_repos(conn) -> Repos:
    return Repos(
        opportunities=OpportunityRepository(conn),
        evidence=EvidenceRepository(conn),
        competitors=CompetitorRepository(conn),
        evaluations=EvaluationRepository(conn),
        experiments=ExperimentRepository(conn),
        decision_log=DecisionLogRepository(conn),
        costs=CostRepository(conn),
        engine=EngineRepository(conn),
        ledger=LedgerRepository(conn),
        discovery=DiscoveryRepository(conn),
        reviews=ReviewRepository(conn),
    )


__all__ = [
    "init_db",
    "connect",
    "Repos",
    "build_repos",
    "OpportunityRepository",
    "EvidenceRepository",
    "CompetitorRepository",
    "EvaluationRepository",
    "ExperimentRepository",
    "DecisionLogRepository",
    "CostRepository",
    "EngineRepository",
    "LedgerRepository",
    "DiscoveryRepository",
    "ReviewRepository",
]
