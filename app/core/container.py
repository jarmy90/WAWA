"""Contenedor de dependencias (DI manual, sin framework).

Conecta configuración, base de datos, repositorios, motor de operación,
economía simulada, proveedores, BudgetGuard y servicios. Los tests construyen
contenedores con configuración temporal.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.providers.manager import ProviderManager
from app.repositories import Repos, build_repos, init_db, connect
from app.repositories.costs import CostRepository
from app.services.budget import BudgetGuard
from app.services.campaign import CampaignService
from app.services.command_center import CommandCenterService
from app.services.cycle import CycleEvaluator
from app.services.discovery import DiscoveryService
from app.services.deep_reasoning import DeepReasoningService
from app.services.engine import EngineService
from app.services.economy import EconomyService
from app.services.import_export import ExportService, ImportService
from app.services.opportunities import OpportunityService
from app.services.orchestrator import CampaignOrchestrator
from app.services.reviews import ReviewService
from app.services.super_tournament import SuperTournamentService
from app.workflows.pipeline import PipelineService


@dataclass
class AppContainer:
    settings: Settings
    conn: sqlite3.Connection
    repos: Repos
    engine: EngineService
    budget: BudgetGuard
    economy: EconomyService
    providers: ProviderManager
    opportunities: OpportunityService
    pipeline: PipelineService
    discovery: DiscoveryService
    exports: ExportService
    imports: ImportService
    reviews: ReviewService
    campaigns: CampaignService
    cycle: CycleEvaluator
    orchestrator: CampaignOrchestrator
    deep_reasoning: DeepReasoningService
    super_tournament: SuperTournamentService
    command_center: CommandCenterService

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass


def build_container(settings: Settings | None = None) -> AppContainer:
    """Construye el contenedor completo (idempotente y aislable por settings)."""
    settings = settings or get_settings()
    init_db(settings)
    conn = connect(settings.database_path)
    repos = build_repos(conn)
    engine = EngineService(settings, repos.engine, ledger=repos.ledger)
    budget = BudgetGuard(settings, CostRepository(conn), engine=engine)
    economy = EconomyService(settings, repos, engine, budget)
    budget.economy = economy  # integración ledger (sin ciclos en el constructor)
    providers = ProviderManager(settings, budget)
    opportunities = OpportunityService(settings, repos)
    pipeline = PipelineService(settings, repos, providers, budget, engine=engine)
    discovery = DiscoveryService(settings, repos, providers, opportunities)
    exports = ExportService(repos)
    imports = ImportService(settings, repos, pipeline)
    reviews = ReviewService(settings, repos, engine=engine, providers=providers)
    pipeline.reviews = reviews  # cola automática de finalistas en el Judge
    campaigns = CampaignService(settings, repos, discovery, reviews, engine=engine)
    orchestrator = CampaignOrchestrator(
        settings, repos, repos.orchestrator, discovery, pipeline, reviews, opportunities
    )
    cycle = CycleEvaluator(settings, conn, repos=repos, orchestrator=orchestrator)
    deep_reasoning = DeepReasoningService(settings, providers, repos.llm_calls)
    super_tournament = SuperTournamentService(settings, repos, repos.decision_log)
    command_center = CommandCenterService(
        AppContainer(
            settings=settings, conn=conn, repos=repos, engine=engine, budget=budget,
            economy=economy, providers=providers, opportunities=opportunities,
            pipeline=pipeline, discovery=discovery, exports=exports, imports=imports,
            reviews=reviews, campaigns=campaigns, cycle=cycle, orchestrator=orchestrator,
            deep_reasoning=deep_reasoning, super_tournament=super_tournament,
            command_center=None,  # type: ignore[arg-type]
        )
    )
    return AppContainer(
        settings=settings,
        conn=conn,
        repos=repos,
        engine=engine,
        budget=budget,
        economy=economy,
        providers=providers,
        opportunities=opportunities,
        pipeline=pipeline,
        discovery=discovery,
        exports=exports,
        imports=imports,
        reviews=reviews,
        campaigns=campaigns,
        cycle=cycle,
        orchestrator=orchestrator,
        deep_reasoning=deep_reasoning,
        super_tournament=super_tournament,
        command_center=command_center,
    )
