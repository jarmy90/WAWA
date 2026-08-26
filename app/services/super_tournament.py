"""Servicio del super-torneo (iteración 018).

Reúne entradas del repositorio de discovery (candidatas actuales en
RESEARCH_PENDING, reformulaciones con brief completo y challengers),
aplica la puerta de brief completo, ejecuta el torneo determinista
(`app/scoring/super_tournament.py`) y registra cada decisión en
``decision_log`` (append-only).

Garantías heredadas de AGENTS.md:
- OX Alpha / modelos NO participan aquí: el torneo es 100 % determinista.
- Las ganadoras son prioridades de investigación; proven_demand y
  evidence_backed_venture_score quedan intactos.
- Cero ganadoras es un resultado válido y se registra como tal.
"""
from __future__ import annotations

from typing import Any

from app.models.decision_log import DecisionLog
from app.scoring.super_tournament import run_super_tournament


class SuperTournamentService:
    def __init__(self, settings: Any, repos: Any, decisions: Any) -> None:
        self.settings = settings
        self.repos = repos          # Repos (discovery)
        self.decisions = decisions  # DecisionLogRepository (append-only)

    # ------------------------------------------------------------------
    def collect_entries(self) -> dict[str, list[dict[str, Any]]]:
        """Clasifica los conceptos de la campaña activa.

        - ``with_brief``: conceptos con Opportunity Brief completo (entradas
          válidas del torneo).
        - ``challengers_without_brief``: resto (rechazados en la puerta con
          motivo explícito; nunca se fabrican campos)."""
        campaign = None
        for c in self.repos.discovery.list_campaigns():
            if c.get("status") == "active":
                campaign = c
                break
        if campaign is None:
            return {"campaign": None, "entries": [], "challengers_without_brief": []}
        concepts = self.repos.discovery.concepts_by_campaign(campaign["id"])
        entries: list[dict[str, Any]] = []
        challengers: list[dict[str, Any]] = []
        for c in concepts:
            brief = c.get("brief")
            if isinstance(brief, dict) and any(str(v or "").strip() for v in brief.values()):
                entries.append({
                    "concept_id": c["id"],
                    "title": c.get("title"),
                    "status": c.get("status"),
                    "concept": c,
                    "brief": brief,
                })
            else:
                challengers.append({
                    "concept_id": c["id"],
                    "title": c.get("title"),
                    "status": c.get("status"),
                })
        return {"campaign": campaign, "entries": entries, "challengers_without_brief": challengers}

    # ------------------------------------------------------------------
    def run(self, *, actor: str = "system") -> dict[str, Any]:
        data = self.collect_entries()
        if data["campaign"] is None:
            return {"ok": False, "reason": "No hay campaña activa.", "result": None}
        result = run_super_tournament(data["entries"])

        for w in result["winners"]:
            self.decisions.add(DecisionLog(
                agent="super_tournament",
                opportunity_id=None,
                input_summary=f"Super-torneo: {w['title']}",
                output_summary=(
                    f"GANADORA prioridad investigación "
                    f"(score={w['super_tournament_score']}); no es evidencia"
                ),
                evidence_used=[],
                decision="SUPER_TOURNAMENT_WINNER",
                model_or_method="determinista_sin_llm",
            ))
        n_rejected = (
            len(result["rejected_incomplete_brief"])
            + len(result["rejected_low_score"])
            + len(result["eliminated_over_slots"])
        )
        self.decisions.add(DecisionLog(
            agent="super_tournament",
            opportunity_id=None,
            input_summary=f"Super-torneo sobre {result['total_entries']} entradas",
            output_summary=(
                f"{len(result['winners'])} ganadoras, {n_rejected} descartes. "
                "Puntuación = prioridad de investigación, NUNCA evidencia."
            ),
            evidence_used=[],
            decision="SUPER_TOURNAMENT_COMPLETED",
            model_or_method="determinista_sin_llm",
        ))

        return {
            "ok": True,
            "campaign_id": data["campaign"]["id"],
            "campaign_title": data["campaign"].get("title"),
            **result,
            "challengers_without_brief_count": len(data["challengers_without_brief"]),
            "note_model_reasoning": (
                "OX Alpha no participó: el torneo es determinista. Toda salida es "
                "prioridad de investigación; ninguna ganadora obtiene demanda "
                "demostrada ni cambia puntuaciones con evidencia."
            ),
        }
