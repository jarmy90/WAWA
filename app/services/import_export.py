"""Importación y exportación de oportunidades.

- Exportación: paquete JSON completo (oportunidad, evidencias, competidores,
  evaluación, experimento, log de decisiones) o documento Markdown legible.
- Importación: paquete de investigación (JSON) que puede adjuntar evidencias
  a una oportunidad existente o crear una nueva. Las evidencias importadas
  solo se consideran verificadas si el payload lo declara explícitamente.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationError
from app.models.decision_log import DecisionLog
from app.models.evidence import Competitor, Evidence, EvidenceCreate
from app.models.opportunity import Opportunity, OpportunityCreate
from app.models.enums import EvidenceType
from app.repositories import Repos

# Tipos de evidencia permitidos en importaciones.
ALLOWED_TYPES = {t.value for t in EvidenceType}


class ResearchEvidenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_type: str = EvidenceType.other.value
    source_name: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=2_000)
    summary: str = Field(min_length=3, max_length=5_000)
    raw_excerpt: str | None = Field(default=None, max_length=20_000)
    reliability_score: float = Field(default=0.5, ge=0, le=1)
    independence_group: str | None = Field(default=None, max_length=200)
    verified: bool = False
    verification_notes: str | None = Field(default=None, max_length=2_000)


class ResearchCompetitorIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=300)
    url: str | None = Field(default=None, max_length=2_000)
    offer: str | None = Field(default=None, max_length=5_000)
    observed_price: float | None = Field(default=None, ge=0)
    strengths: str | None = Field(default=None, max_length=2_000)
    weaknesses: str | None = Field(default=None, max_length=2_000)


class ResearchPackageIn(BaseModel):
    """Paquete de investigación importable (JSON)."""

    model_config = ConfigDict(extra="forbid")

    opportunity_id: str | None = None
    opportunity: OpportunityCreate | None = None
    evidences: list[ResearchEvidenceIn] = Field(default_factory=list)
    competitors: list[ResearchCompetitorIn] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=5_000)


class ExportService:
    def __init__(self, repos: Repos) -> None:
        self.repos = repos

    def export_json(self, opportunity_id: str) -> dict:
        opportunity = self.repos.opportunities.get(opportunity_id)
        if opportunity is None:
            raise NotFoundError("Oportunidad no encontrada.")
        return {
            "schema_version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "opportunity": opportunity.model_dump(),
            "evidences": [e.model_dump() for e in self.repos.evidence.list_for(opportunity_id)],
            "competitors": [c.model_dump() for c in self.repos.competitors.list_for(opportunity_id)],
            "evaluation": (
                self.repos.evaluations.get(opportunity_id).model_dump() if self.repos.evaluations.get(opportunity_id) else None
            ),
            "experiment": (
                self.repos.experiments.get_for(opportunity_id).model_dump() if self.repos.experiments.get_for(opportunity_id) else None
            ),
            "decision_log": [d.model_dump() for d in self.repos.decision_log.list_for(opportunity_id)],
        }

    def export_markdown(self, opportunity_id: str) -> str:
        data = self.export_json(opportunity_id)
        opp = data["opportunity"]
        ev = data["evaluation"]
        lines: list[str] = []
        lines.append(f"# {opp['title']}")
        lines.append("")
        lines.append(f"- **Estado**: {opp['status']}")
        lines.append(f"- **Sector**: {opp.get('sector') or '—'}")
        lines.append(f"- **Creada**: {opp['created_at']}")
        lines.append("")
        lines.append("## Problema")
        lines.append(opp["problem"])
        lines.append("")
        lines.append("## Solución propuesta")
        lines.append(opp.get("proposed_solution") or "—")
        lines.append("")
        lines.append("## Cliente objetivo")
        lines.append(opp.get("target_customer") or "DESCONOCIDO")
        lines.append("")
        if ev:
            lines.append("## Puntuación")
            lines.append("")
            lines.append(f"- **Puntuación final**: {ev['final_score']}/100")
            lines.append(f"- **Calidad de evidencia**: {ev['evidence_quality_score']}/100")
            lines.append(f"- **Confianza**: {ev['confidence_score']}/100")
            lines.append(f"- **Evidencias independientes**: {ev['independent_evidence_count']}")
            lines.append(f"- **Suposiciones sin verificar**: {ev['unverified_assumptions_count']}")
            lines.append(f"- **Decisión**: {ev['decision']}")
            lines.append("")
            lines.append("### Desglose")
            for key in ("pain", "demand", "customer_reach", "automation", "margin", "build_speed", "differentiation", "safety"):
                crit = ev.get("per_criterion", {}).get(key)
                if crit:
                    lines.append(f"- **{key}**: {crit['score']}/100 (base: {crit['basis']})")
            if ev.get("blockers"):
                lines.append("")
                lines.append("### Bloqueadores")
                for b in ev["blockers"]:
                    lines.append(f"- {b}")
            lines.append("")
            if ev.get("approval_reason"):
                lines.append(f"**Motivo aprobación**: {ev['approval_reason']}")
            if ev.get("rejection_reason"):
                lines.append(f"**Motivo rechazo**: {ev['rejection_reason']}")
            if ev.get("skeptic_critique"):
                lines.append("")
                lines.append("## Crítica del Skeptic")
                lines.append(ev["skeptic_critique"])
        lines.append("")
        lines.append("## Evidencias")
        for e in data["evidences"]:
            lines.append(f"- [{e['evidence_type']}] {e['summary']}")
            lines.append(f"  - Fuente: {e.get('source_name') or '—'} {e.get('source_url') or ''}")
            lines.append(f"  - Fiabilidad: {e['reliability_score']} | Verificada: {e['verified']} | Método: {e['method']}")
        lines.append("")
        lines.append("## Competidores")
        if data["competitors"]:
            for c in data["competitors"]:
                lines.append(f"- **{c['name']}** — {c.get('offer') or ''} (precio observado: {c.get('observed_price') or 'desconocido'})")
        else:
            lines.append("—")
        lines.append("")
        if data.get("experiment"):
            exp = data["experiment"]
            lines.append("## Experimento propuesto")
            lines.append(f"- **Hipótesis**: {exp.get('hypothesis')}")
            lines.append(f"- **Test más barato**: {exp.get('cheapest_test')}")
            lines.append(f"- **Presupuesto máximo**: {exp.get('maximum_budget')} USD")
            lines.append(f"- **Métrica de éxito**: {exp.get('success_metric')} ({exp.get('success_threshold')})")
            lines.append(f"- **Criterio de fracaso**: {exp.get('failure_threshold')}")
            lines.append(f"- **Duración**: {exp.get('duration')}")
        return "\n".join(lines)


class ImportService:
    def __init__(self, settings: Settings, repos: Repos, pipeline) -> None:
        self.settings = settings
        self.repos = repos
        self.pipeline = pipeline

    def import_research(self, payload: ResearchPackageIn) -> dict:
        """Importa un paquete de investigación. Devuelve resumen de lo creado."""
        if payload.opportunity_id and payload.opportunity:
            raise ValidationError("Indica opportunity_id O opportunity (nueva), no ambos.")

        created_opportunity: Opportunity | None = None
        opportunity_id = payload.opportunity_id
        if opportunity_id is None:
            if payload.opportunity is None:
                raise ValidationError("El paquete debe incluir opportunity_id o una opportunity nueva.")
            created_opportunity = Opportunity(
                title=payload.opportunity.title,
                problem=payload.opportunity.problem,
                proposed_solution=payload.opportunity.proposed_solution,
                target_customer=payload.opportunity.target_customer,
                sector=payload.opportunity.sector,
                source=f"import:{payload.opportunity.source}",
            )
            self.repos.opportunities.create(created_opportunity)
            opportunity_id = created_opportunity.id
        else:
            if self.repos.opportunities.get(opportunity_id) is None:
                raise NotFoundError("Oportunidad destino no encontrada.")

        n_ev, n_comp = 0, 0
        for raw in payload.evidences:
            evidence = Evidence(
                **EvidenceCreate(**raw.model_dump()).model_dump(exclude={"method"}),
                opportunity_id=opportunity_id,
                captured_at=datetime.now(timezone.utc).isoformat(),
                collected_by="import",
                method="import",
            )
            if self.repos.evidence.is_duplicate(evidence):
                continue
            self.repos.evidence.create(evidence)
            n_ev += 1

        for raw in payload.competitors:
            self.repos.competitors.create(
                Competitor(**raw.model_dump(), opportunity_id=opportunity_id)
            )
            n_comp += 1

        self.repos.decision_log.add(
            DecisionLog(
                agent="import",
                opportunity_id=opportunity_id,
                input_summary=f"Importación de investigación (evidencias={n_ev}, competidores={n_comp}). {payload.notes or ''}",
                output_summary="Paquete de investigación importado.",
                model_or_method="manual (importación JSON)",
            )
        )

        reevaluate = bool(payload.opportunity is None)  # solo reevaluar oportunidades existentes
        evaluation = None
        if reevaluate and (n_ev > 0 or n_comp > 0):
            evaluation = self.pipeline.evaluate(opportunity_id, clear_existing=False)

        return {
            "opportunity_id": opportunity_id,
            "created": bool(created_opportunity),
            "evidences_imported": n_ev,
            "competitors_imported": n_comp,
            "reevaluated": reevaluate,
            "evaluation": evaluation.model_dump() if evaluation else None,
        }

