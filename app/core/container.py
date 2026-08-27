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
from app.services.commercial_bootstrap import CommercialBootstrapService
from app.services.connect_services import ConnectServicesService
from app.services.cycle import CycleEvaluator
from app.services.discovery import DiscoveryService
from app.services.deep_reasoning import DeepReasoningService
from app.services.engine import EngineService
from app.services.economy import EconomyService
from app.services.import_export import ExportService, ImportService
from app.services.opportunities import OpportunityService
from app.services.orchestrator import CampaignOrchestrator
from app.services.reviews import ReviewService
from app.services.arena import ArenaService
from app.services.super_tournament import SuperTournamentService
from app.services.scheduler import AutonomousScheduler
from app.services.worker import AutonomousWorker
from app.services.autonomous import AutonomousFlow
from app.services.safe_pause import SafePause
from app.services.preflight import run_preflight
from app.providers.llm_router import LLMRouter, LLMRouterConfig
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
    bootstrap: CommercialBootstrapService
    connect_services: ConnectServicesService
    arena: ArenaService
    scheduler: AutonomousScheduler
    worker: AutonomousWorker
    autonomous_flow: AutonomousFlow
    safe_pause: SafePause
    llm_router: LLMRouter

    def close(self) -> None:
        try:
            self.scheduler.stop()
        except Exception:
            pass
        try:
            self.worker.stop()
        except Exception:
            pass
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
    reviews.discovery = discovery  # iteración 023: misión específica si MORE_RESEARCH
    pipeline.reviews = reviews  # cola automática de finalistas en el Judge
    campaigns = CampaignService(settings, repos, discovery, reviews, engine=engine)
    orchestrator = CampaignOrchestrator(
        settings, repos, repos.orchestrator, discovery, pipeline, reviews, opportunities
    )
    cycle = CycleEvaluator(settings, conn, repos=repos, orchestrator=orchestrator)
    deep_reasoning = DeepReasoningService(settings, providers, repos.llm_calls)
    super_tournament = SuperTournamentService(settings, repos, repos.decision_log)
    # Contenedor final: los servicios que se referencian entre sí (bootstrap,
    # command_center, connect_services) se construyen sobre el MISMO contenedor
    # final para que sus accesos cruzados (p. ej. bootstrap -> command_center)
    # funcionen. AppContainer no es frozen: se reasignan tras crear el objeto.
    container = AppContainer(
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
        command_center=None,  # type: ignore[arg-type]
        bootstrap=None,  # type: ignore[arg-type]
        connect_services=None,  # type: ignore[arg-type]
        arena=None,  # type: ignore[arg-type]
        scheduler=None,  # type: ignore[arg-type]
        worker=None,  # type: ignore[arg-type]
        autonomous_flow=None,  # type: ignore[arg-type]
        safe_pause=None,  # type: ignore[arg-type]
        llm_router=None,  # type: ignore[arg-type]
    )
    container.command_center = CommandCenterService(container)
    container.bootstrap = CommercialBootstrapService(container)
    container.connect_services = ConnectServicesService(settings)
    container.arena = ArenaService(settings, repos.arena, repos.discovery)

    # --- Autonomous 24/7 Runtime (iteración 025) ---
    omniroute = providers.omniroute
    llm_config = LLMRouterConfig(
        max_requests_per_minute=settings.llm_max_requests_per_minute,
        max_requests_per_day=settings.llm_max_requests_per_day,
        max_tokens_per_job=settings.llm_max_tokens_per_job,
        max_tokens_per_day=settings.llm_max_tokens_per_day,
        max_estimated_cost_usd_per_day=settings.llm_max_estimated_cost_usd_per_day,
        hard_budget_enforcement=settings.llm_hard_budget_enforcement,
        max_retries=settings.llm_max_retries,
        circuit_failure_threshold=settings.llm_circuit_failure_threshold,
        circuit_cooldown_seconds=settings.llm_circuit_cooldown_seconds,
        model_allowlist=[s.strip() for s in settings.omniroute_model_allowlist.split(",") if s.strip()],
        discovery_model=settings.omniroute_discovery_model,
        research_model=settings.omniroute_discovery_model,
        critique_model=settings.omniroute_discovery_model,
        default_model=settings.omniroute_default_model,
    )
    llm_router = LLMRouter(conn, omniroute_provider=omniroute, config=llm_config)

    scheduler = AutonomousScheduler(
        conn,
        poll_interval_seconds=settings.autonomous_poll_interval_seconds,
        enabled=settings.autonomous_scheduler_enabled,
    )
    worker = AutonomousWorker(
        conn,
        enabled=settings.autonomous_worker_enabled,
        max_concurrent=settings.autonomous_max_concurrent_jobs,
        lease_seconds=settings.autonomous_job_lease_seconds,
    )
    autonomous_flow = AutonomousFlow(conn)
    autonomous_flow.set_services(
        llm_router=llm_router, arena_service=container.arena,
        discovery_service=discovery, reviews_service=reviews,
        campaigns_service=campaigns, settings=settings,
    )
    worker.register_handlers(autonomous_flow.get_handlers())
    worker.set_services(llm_router=llm_router)

    safe_pause = SafePause(conn)

    container.scheduler = scheduler
    container.worker = worker
    container.autonomous_flow = autonomous_flow
    container.safe_pause = safe_pause
    container.llm_router = llm_router

    return container
