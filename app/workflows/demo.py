"""Carga de datos de demostración (MQL5).

Los datos de muestra se marcan explícitamente como NO verificados
(``verified=false``, ``method=demo``): el sistema los puntúa con fiabilidad
reducida y baja confianza. Es una demostración honesta del pipeline, no
evidencia real de mercado.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import Settings
from app.core.errors import AppError
from app.models.decision_log import DecisionLog
from app.models.enums import AgentName, OpportunityStatus
from app.models.evidence import Competitor, Evidence
from app.models.opportunity import Opportunity
from app.repositories import Repos

DEMO_FILE = Path(__file__).resolve().parents[2] / "data" / "demo" / "demo_opportunities.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DemoSeeder:
    def __init__(self, settings: Settings, repos: Repos, pipeline) -> None:
        self.settings = settings
        self.repos = repos
        self.pipeline = pipeline

    def seed(self, *, evaluate: bool = True) -> dict:
        """Carga las oportunidades de demostración (idempotente por título)."""
        if not DEMO_FILE.exists():
            raise AppError(f"Archivo de demo no encontrado: {DEMO_FILE}")

        payload = json.loads(DEMO_FILE.read_text(encoding="utf-8"))
        summary = {"created": 0, "skipped": 0, "evaluated": 0, "results": []}

        for item in payload.get("opportunities", []):
            data = item["opportunity"]
            if self.repos.opportunities.find_similar_title(data["title"]):
                summary["skipped"] += 1
                continue
            opportunity = Opportunity(
                title=data["title"],
                problem=data["problem"],
                proposed_solution=data.get("proposed_solution"),
                target_customer=data.get("target_customer"),
                sector=data.get("sector"),
                source="demo",
                status=OpportunityStatus.draft,
            )
            self.repos.opportunities.create(opportunity)

            for raw in item.get("evidences", []):
                evidence = Evidence(
                    opportunity_id=opportunity.id,
                    captured_at=_now(),
                    collected_by="demo",
                    **raw,
                )
                self.repos.evidence.create(evidence)

            for raw in item.get("competitors", []):
                self.repos.competitors.create(Competitor(opportunity_id=opportunity.id, **raw))

            self.repos.decision_log.add(
                DecisionLog(
                    agent=AgentName.system.value,
                    opportunity_id=opportunity.id,
                    input_summary="Carga de datos de demostración (MQL5).",
                    output_summary=f"Oportunidad demo creada: {opportunity.title}",
                    model_or_method="demo-data",
                )
            )
            summary["created"] += 1

            if evaluate:
                evaluation = self.pipeline.evaluate(opportunity.id, clear_existing=False)
                summary["evaluated"] += 1
                summary["results"].append(
                    {
                        "id": opportunity.id,
                        "title": opportunity.title,
                        "final_score": evaluation.final_score,
                        "decision": evaluation.decision.value,
                        "confidence": evaluation.confidence_score,
                    }
                )
        return summary
