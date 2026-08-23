"""CampaignRunner Freebuff-first (iteración 006).

Orquesta campañas de descubrimiento/investigación mediante SESIONES de
trabajo de 2-6 h con Freebuff, reanudables y con checkpoints persistentes
(SESSION_PLAN.md, SESSION_STATE.json, SESSION_OUTPUT.json, SESSION_REPORT.md,
NEXT_SESSION.md). Política permanente: api_budget_usd=0 durante el
descubrimiento; Freebuff NO es un runtime 24/7 ni tiene API runtime estable;
ninguna campaña está obligada a producir una finalista; los límites del embudo
nunca aumentan silenciosamente; el consenso de modelos no es evidencia.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.campaign import (
    APIReadinessGate,
    APIReadinessState,
    Campaign,
    CampaignCreate,
    CampaignStage,
    CampaignStatus,
    CampaignTransition,
    DEFAULT_FUNNEL_LIMITS,
    FreebuffSession,
    ReasoningLevel,
    SessionOutputIn,
    SessionPrepareIn,
    new_id,
)
from app.models.external_review import ReviewImportIn
from app.repositories import Repos

STAGE_ORDER = [s.value for s in CampaignStage]

# Entregables obligatorios por etapa (deterministas; se validan al transicionar).
def _funnel(campaign: dict[str, Any]) -> dict[str, int]:
    limits = dict(DEFAULT_FUNNEL_LIMITS)
    limits.update(campaign.get("funnel_limits") or {})
    return limits


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CampaignService:
    def __init__(self, settings: Settings, repos: Repos, discovery, reviews, engine=None) -> None:
        self.settings = settings
        self.repos = repos
        self.discovery = discovery
        self.reviews = reviews
        self.engine = engine
        self.log = get_logger("campaign")
        self._sessions_dir: Path = settings.freebuff_sessions_dir

    # ==================================================================
    # Campañas
    # ==================================================================
    def create_campaign(self, data: CampaignCreate | dict) -> dict[str, Any]:
        payload = data.model_dump() if isinstance(data, CampaignCreate) else data
        hours = int(payload.get("time_budget_hours", 3))
        if not 2 <= hours <= 6:
            raise ValidationError("time_budget_hours debe estar entre 2 y 6.")

        limits = dict(DEFAULT_FUNNEL_LIMITS)
        max_finalists = int(payload.get("maximum_finalists", 3))
        if not 0 <= max_finalists <= 5:
            raise ValidationError("maximum_finalists debe estar entre 0 y 5.")
        limits["maximum_finalists"] = max_finalists

        campaign = Campaign(
            title=payload["title"],
            territory_keys=list(payload.get("territory_keys") or []),
            lens_keys=list(payload.get("lens_keys") or []),
            archetype_keys=list(payload.get("archetype_keys") or []),
            time_budget_hours=hours,
            external_review_slots=int(payload.get("external_review_slots", 3)),
            maximum_deep_research_candidates=int(payload.get("maximum_deep_research_candidates", 10)),
            funnel_limits=limits,
            api_budget_usd=0.0,  # política permanente: 0 durante el descubrimiento
            experiment_budget_usd=0.0,
        )
        saved = self.repos.campaigns.create_campaign(campaign)
        self._transition(
            saved,
            CampaignStage.territory_selection,
            actor="system",
            reason="Campaña creada; territorios/lentes/arquetipos resueltos (vacío = biblioteca completa).",
        )
        return self.campaign_detail(campaign.id)

    def list_campaigns(self) -> dict[str, Any]:
        items = self.repos.campaigns.list_campaigns()
        out = []
        for c in items:
            sessions = self.repos.campaigns.sessions_for(c["id"])
            out.append({**c, "last_session": sessions[0] if sessions else None, "sessions_count": len(sessions)})
        return {"items": out, "count": len(out)}

    def campaign_detail(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.repos.campaigns.get_campaign(campaign_id)
        if campaign is None:
            raise NotFoundError("Campaña no encontrada.")
        sessions = self.repos.campaigns.sessions_for(campaign_id)
        transitions = self.repos.campaigns.transitions_for(campaign_id)
        discovery_detail = None
        if campaign.get("discovery_campaign_id"):
            try:
                discovery_detail = self.discovery.campaign_detail(campaign["discovery_campaign_id"])
            except Exception:
                discovery_detail = None
        return {
            "campaign": campaign,
            "sessions": sessions,
            "transitions": transitions,
            "discovery": discovery_detail,
            "reasoning_log": self.repos.campaigns.reasoning_for(campaign_id),
            "stage_order": STAGE_ORDER,
        }

    # ==================================================================
    # Máquina de estados (sin LLM)
    # ==================================================================
    def transition(
        self,
        campaign_id: str,
        to_stage: CampaignStage,
        *,
        actor: str = "human",
        reason: str | None = None,
        next_action: str | None = None,
        demo_override: bool = False,
    ) -> dict[str, Any]:
        campaign = self.repos.campaigns.get_campaign(campaign_id)
        if campaign is None:
            raise NotFoundError("Campaña no encontrada.")
        if campaign["status"] != CampaignStatus.active.value:
            raise ConflictError(f"Campaña no activa (estado: {campaign['status']}).")

        current = campaign["stage"]
        target = to_stage.value
        if target not in STAGE_ORDER:
            raise ValidationError(f"Etapa desconocida: {target}.")
        if STAGE_ORDER.index(target) <= STAGE_ORDER.index(current):
            raise ValidationError(f"No se puede retroceder: {current} -> {target}.")

        stages_to_check = [s for s in STAGE_ORDER if STAGE_ORDER.index(current) < STAGE_ORDER.index(s) <= STAGE_ORDER.index(target)]
        missing = self._missing_deliverables(campaign, stages_to_check)
        if missing and not (demo_override and campaign["is_synthetic"]):
            raise ValidationError(
                "Entregables obligatorios pendientes antes de avanzar: " + "; ".join(missing),
                details={"missing": missing, "stage": target},
            )

        updated = self.repos.campaigns.update_campaign(
            campaign_id, stage=target, next_recommended_action=next_action
        )
        self._transition(
            updated or campaign, CampaignStage(target), actor=actor, reason=reason,
            next_action=next_action, rejected=0,
        )
        return self.campaign_detail(campaign_id)

    def _missing_deliverables(self, campaign: dict[str, Any], stages: list[str]) -> list[str]:
        """Comprueba entregables obligatorios para las etapas dadas (determinista)."""
        missing: list[str] = []
        detail = None
        if campaign.get("discovery_campaign_id"):
            try:
                detail = self.discovery.campaign_detail(campaign["discovery_campaign_id"])
            except Exception:
                detail = None
        concepts = (detail or {}).get("concepts") or []
        comparisons = (detail or {}).get("comparisons") or []

        def has_concepts_with(pred) -> bool:
            return any(pred(c) for c in concepts)

        for stage in stages:
            if stage == CampaignStage.territory_selection.value:
                if not campaign.get("territory_keys"):
                    missing.append("TERRITORY_SELECTION: seleccionar territorios (o usar la biblioteca completa).")
            elif stage == CampaignStage.signal_collection.value:
                if campaign.get("signals_count", 0) < 1:
                    missing.append("SIGNAL_COLLECTION: recoger al menos 1 señal de mercado.")
            elif stage == CampaignStage.wide_ideation.value:
                if campaign.get("concepts_count", 0) < 5:
                    missing.append("WIDE_IDEATION: generar al menos 5 conceptos.")
            elif stage == CampaignStage.commodity_filter.value:
                if not has_concepts_with(lambda c: c.get("status") in ("passed", "blocked")):
                    missing.append("COMMODITY_FILTER: ejecutar el filtro de comoditización (marcar conceptos).")
            elif stage == CampaignStage.recombination.value:
                if not has_concepts_with(lambda c: c.get("source") == "recombined"):
                    missing.append("RECOMBINATION: crear al menos 1 concepto recombinado.")
            elif stage == CampaignStage.structural_analysis.value:
                analyzed = [c for c in concepts if c.get("substitution") and c.get("venture")]
                if len(analyzed) < 3:
                    missing.append("STRUCTURAL_ANALYSIS: analizar al menos 3 conceptos (substitution + venture).")
            elif stage == CampaignStage.shortlist.value:
                shortlisted = [c for c in concepts if c.get("status") in ("shortlisted", "finalist")]
                if len(shortlisted) < 3:
                    missing.append("SHORTLIST: seleccionar al menos 3 conceptos al shortlist.")
            elif stage == CampaignStage.internal_tournament.value:
                if not comparisons and campaign.get("finalists_count", 0) == 0:
                    missing.append("INTERNAL_TOURNAMENT: ejecutar el torneo por pares (o seleccionar finalistas).")
            elif stage == CampaignStage.finalists.value:
                if campaign.get("finalists_count", 0) == 0:
                    missing.append("FINALISTS: seleccionar al menos 1 finalista (0 permitido solo con decisión explícita de cierre).")
            elif stage == CampaignStage.research_missions.value:
                if campaign.get("missions_count", 0) < max(1, campaign.get("finalists_count", 0)):
                    missing.append("RESEARCH_MISSIONS: crear misiones de investigación para cada finalista.")
            elif stage == CampaignStage.external_review_ready.value:
                if campaign.get("finalists_count", 0) > 0 and not self._packets_ready(campaign):
                    missing.append("EXTERNAL_REVIEW_READY: generar el review_packet de cada finalista.")
            elif stage == CampaignStage.external_review_pending.value:
                if not self._reviews_started(campaign):
                    missing.append("EXTERNAL_REVIEW_PENDING: importar ≥1 revisión o continuar sin revisión (neutral).")
            elif stage == CampaignStage.synthesis.value:
                if not self._synthesis_exists(campaign):
                    missing.append("SYNTHESIS: generar la síntesis del comité para la(s) finalista(s).")
            elif stage == CampaignStage.experiment_design.value:
                if not self._experiment_defined(campaign):
                    missing.append("EXPERIMENT_DESIGN: definir el experimento de la prioritaria (o cerrar sin experimento).")
            elif stage == CampaignStage.owner_review.value:
                if campaign.get("closed_reason") is None:
                    missing.append("OWNER_REVIEW: registrar la decisión del propietario (avanzar o cerrar).")
            elif stage == CampaignStage.completed.value:
                if campaign.get("closed_reason") is None:
                    missing.append("COMPLETED: la campaña solo se cierra con una decisión registrada.")
        return missing

    def _transition(self, campaign: dict[str, Any], to_stage: CampaignStage, *, actor: str, reason: str | None, next_action: str | None = None, rejected: int = 0) -> None:
        self.repos.campaigns.add_transition(
            CampaignTransition(
                campaign_id=campaign["id"],
                from_stage=campaign["stage"],
                to_stage=to_stage.value,
                actor=actor,
                reason=reason,
                concepts_considered=campaign.get("concepts_count", 0),
                concepts_rejected=rejected or campaign.get("concepts_rejected", 0),
                costs_recorded={"api_budget_usd": campaign.get("api_budget_usd", 0.0)},
                unknowns=[],
                next_recommended_action=next_action,
            ).model_dump()
        )
        if self.engine is not None:
            try:
                self.engine.record_event(
                    event_type="campaign:stage",
                    summary=f"Campaña {campaign['title'][:40]} → {to_stage.value} (por {actor}).",
                )
            except Exception:
                pass

    def set_campaign_status(self, campaign_id: str, status: CampaignStatus, *, reason: str) -> dict[str, Any]:
        campaign = self.repos.campaigns.get_campaign(campaign_id)
        if campaign is None:
            raise NotFoundError("Campaña no encontrada.")
        updated = self.repos.campaigns.update_campaign(campaign_id, status=status.value, closed_reason=reason)
        if status in (CampaignStatus.failed, CampaignStatus.cancelled, CampaignStatus.completed):
            # Conservar aprendizajes: registrar el motivo de cierre como patrón.
            self.repos.discovery.add_learning_record(
                kind="campaign_outcome",
                pattern=f"Campaña {status.value}: {reason}",
                source=f"campaign:{campaign_id}",
                notes=f"Campaña: {campaign['title']}",
            )
        return self.campaign_detail(campaign_id)

    # ==================================================================
    # Sesiones Freebuff (protocolo reanudable)
    # ==================================================================
    def prepare_session(self, campaign_id: str, hours: int, *, actor: str = "human") -> dict[str, Any]:
        campaign = self.repos.campaigns.get_campaign(campaign_id)
        if campaign is None:
            raise NotFoundError("Campaña no encontrada.")
        if campaign["status"] != CampaignStatus.active.value:
            raise ConflictError(f"Campaña no activa (estado: {campaign['status']}).")
        if not 2 <= hours <= 6:
            raise ValidationError("La sesión debe durar entre 2 y 6 horas.")

        previous = self.repos.campaigns.sessions_for(campaign_id)
        next_session_hint = previous[0].get("next_session_path") if previous else None

        tasks = self._tasks_for_stage(campaign, previous)
        session = FreebuffSession(
            campaign_id=campaign_id,
            time_budget_hours=hours,
            stage_start=campaign["stage"],
            tasks_planned=tasks,
            tasks_pending=list(tasks),
            is_synthetic=campaign["is_synthetic"],
        )
        saved = self.repos.campaigns.create_session(session)
        self.repos.campaigns.update_campaign(campaign_id, sessions_count=campaign.get("sessions_count", 0) + 1)

        plan = self._build_session_plan(campaign, saved, tasks)
        state = self._build_session_state(campaign, saved)
        prompt = self.short_prompt(campaign_id)
        session_dir = self._session_dir(campaign_id, saved["session_id"])
        session_dir.mkdir(parents=True, exist_ok=True)
        plan_path = session_dir / "SESSION_PLAN.md"
        state_path = session_dir / "SESSION_STATE.json"
        prompt_path = session_dir / "SESSION_PROMPT.md"
        plan_path.write_text(plan, encoding="utf-8")
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        prompt_path.write_text(prompt + "\n", encoding="utf-8")

        self.repos.campaigns.update_session(
            saved["session_id"],
            plan_path=str(plan_path),
            state_path=str(state_path),
            short_prompt=prompt,
        )
        return {
            **self.repos.campaigns.get_session(saved["session_id"]),
            "plan": plan,
            "state": state,
            "short_prompt": prompt,
            "next_session_hint": next_session_hint,
        }

    def _session_dir(self, campaign_id: str, session_id: str) -> Path:
        return self._sessions_dir / campaign_id / session_id

    def _tasks_for_stage(self, campaign: dict[str, Any], previous: list[dict[str, Any]]) -> list[str]:
        done = set()
        for s in previous:
            done.update(s.get("tasks_completed") or [])
        tasks_by_stage: dict[str, list[str]] = {
            CampaignStage.signal_collection.value: [
                "Recoger 3-5 señales de mercado (tensiones, costes ocultos, cambios) con URL + fecha + fragmento.",
                "Descartar señales obvias o sin fuente.",
            ],
            CampaignStage.wide_ideation.value: [
                "Generar 10-30 conceptos breves (2-3 frases) cruzando territorios × lentes × arquetipos.",
                "Etiquetar cada concepto: territorio, lentes, arquetipo, comprador hipotético, resultado hipotético.",
            ],
            CampaignStage.commodity_filter.value: [
                "Ejecutar el General AI Substitution Test sobre cada concepto.",
                "Eliminar prompt wrappers, features sueltas, directorios sin distribución y marketplaces sin liquidez.",
            ],
            CampaignStage.recombination.value: [
                "Cruzar los mecanismos de los conceptos que pasaron el filtro en 3-6 combinaciones nuevas.",
            ],
            CampaignStage.structural_analysis.value: [
                "Analizar estructuralmente los conceptos supervivientes: moat, distribución, comprador, red-team.",
            ],
            CampaignStage.shortlist.value: [
                "Seleccionar el shortlist (3-10) por calidad estructural y diversidad anti-clon.",
            ],
            CampaignStage.internal_tournament.value: [
                "Comparar por pares: dolor económico, resistencia a IA, velocidad de validación, distribución, activo acumulativo.",
                "Elegir hasta 3 finalistas.",
            ],
            CampaignStage.research_missions.value: [
                "Ejecutar las misiones de investigación de cada finalista (demanda, comprador, alternativas, sustitución IA, competidores, distribución, moat, datos, ToS, experimento).",
            ],
            CampaignStage.external_review_ready.value: [
                "Generar el review_packet.md de cada finalista (idéntico para todos los revisores).",
            ],
            CampaignStage.external_review_pending.value: [
                "Consultar GPT/Grok/Gemini con el expediente y guardar respuestas TXT/MD.",
                "Importar las respuestas y sintetizar.",
            ],
            CampaignStage.synthesis.value: [
                "Analizar las discrepancias entre revisores y decidir: avanzar, investigar más, reemplazar o cerrar.",
            ],
            CampaignStage.experiment_design.value: [
                "Definir el experimento más barato de la prioritaria: hipótesis, métrica, umbrales, presupuesto 0.",
            ],
            CampaignStage.owner_review.value: [
                "Presentar la decisión al propietario y registrar avanzar o cerrar.",
            ],
        }
        tasks = [t for t in tasks_by_stage.get(campaign["stage"], ["Avanzar la etapa actual."]) if t not in done]
        if not tasks:
            tasks = ["Validar el checkpoint y preparar la siguiente etapa."]
        return tasks

    def _build_session_plan(self, campaign: dict[str, Any], session: dict[str, Any], tasks: list[str]) -> str:
        files_to_read = [
            "AGENTS.md",
            "docs/FREEBUFF_SESSION_PROTOCOL.md",
            "docs/CAMPAIGN_RUNNER.md",
            "SESSION_STATE.json (junto a este plan)",
            "NEXT_SESSION.md de la sesión anterior (si existe)",
        ]
        lines = [
            "# SESSION_PLAN.md",
            "",
            f"- **campaign_id**: {campaign['id']}",
            f"- **campaign**: {campaign['title']}",
            f"- **stage actual**: {campaign['stage']}",
            f"- **session_id**: {session['session_id']}",
            f"- **tiempo objetivo**: {session['time_budget_hours']} h (alcance y prioridad; no es tiempo garantizado)",
            f"- **api_budget_usd**: {campaign['api_budget_usd']} (política: 0 durante el descubrimiento)",
            f"- **experiment_budget_usd**: {campaign['experiment_budget_usd']}",
            "",
            "## Restricciones",
            "- NO usar APIs de pago ni Gemini (api_budget_usd=0).",
            "- NO inventar demanda, precios, competidores ni evidencias (regla de no invención).",
            "- Las evidencias solo son verified=true con URL concreta + fecha de consulta + fragmento.",
            "- No forzar finalistas: si nada supera los umbrales, cerrar la campaña guardando el motivo.",
            "- No aumentar los límites del embudo (", ", ".join(f"{k}={v}" for k, v in (campaign.get('funnel_limits') or {}).items()), ").",
            "- Freebuff no es un runtime 24/7: toda sesión deja checkpoint y NEXT_SESSION.md.",
            "",
            "## Archivos que deben leerse",
        ]
        for f in files_to_read:
            lines.append(f"- {f}")
        lines.append("")
        lines.append("## Tareas priorizadas")
        for i, task in enumerate(tasks, 1):
            lines.append(f"{i}. [ ] {task}")
        lines.append("")
        lines.append("## Entregables de la sesión")
        lines.append("- SESSION_OUTPUT.json con conceptos/evidencias/misiones/revisiones (estructura de SESSION_STATE.json).")
        lines.append("- SESSION_REPORT.md: qué se hizo, qué se verificó, qué es hipótesis, qué quedó pendiente.")
        lines.append("- SESSION_STATE.json actualizado (lo regenera import_session_output).")
        lines.append("")
        lines.append("## Definición de terminado")
        lines.append(f"- Completar las tareas de la etapa {campaign['stage']} o dejar documentado por qué no.")
        lines.append("- Importar SESSION_OUTPUT.json y finalizar con `python3 scripts/finalize_session.py --session <id>`.")
        lines.append("")
        lines.append("## Comando de validación")
        lines.append("```bash")
        lines.append("python3 -m pytest tests/ -q --tb=short")
        lines.append("```")
        lines.append("")
        return "\n".join(lines)

    def _build_session_state(self, campaign: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
        return {
            "session_id": session["session_id"],
            "campaign_id": campaign["id"],
            "campaign_title": campaign["title"],
            "stage_start": session["stage_start"],
            "stage_end": None,
            "started_at": session["started_at"],
            "completed_at": None,
            "status": session["status"],
            "time_budget_hours": session["time_budget_hours"],
            "tasks_planned": session["tasks_planned"],
            "tasks_completed": [],
            "tasks_pending": session["tasks_pending"],
            "concepts_created": 0,
            "concepts_rejected": 0,
            "evidences_added": 0,
            "review_packets_created": 0,
            "funnel_limits": campaign.get("funnel_limits"),
            "counters": {
                "signals": campaign.get("signals_count", 0),
                "concepts": campaign.get("concepts_count", 0),
                "concepts_rejected": campaign.get("concepts_rejected", 0),
                "finalists": campaign.get("finalists_count", 0),
                "missions": campaign.get("missions_count", 0),
            },
            "blockers": [],
            "errors": [],
            "next_action": self._next_action_for(campaign),
            "policy": {
                "api_budget_usd": 0.0,
                "freebuff_is_24_7": False,
                "freebuff_has_runtime_api": False,
                "requires_new_session_to_continue": True,
            },
        }

    def _next_action_for(self, campaign: dict[str, Any]) -> str:
        stage = campaign["stage"]
        return {
            CampaignStage.signal_collection.value: "Recoger señales de mercado con fuentes.",
            CampaignStage.wide_ideation.value: "Generar conceptos breves cruzando territorios × lentes × arquetipos.",
            CampaignStage.commodity_filter.value: "Aplicar el General AI Substitution Test y descartar wrappers.",
            CampaignStage.recombination.value: "Recombinar mecanismos de los conceptos supervivientes.",
            CampaignStage.structural_analysis.value: "Analizar moat, distribución, comprador y red-team de cada superviviente.",
            CampaignStage.shortlist.value: "Seleccionar el shortlist con diversidad anti-clon.",
            CampaignStage.internal_tournament.value: "Comparar por pares y elegir finalistas.",
            CampaignStage.research_missions.value: "Ejecutar las misiones de investigación de los finalistas.",
            CampaignStage.external_review_ready.value: "Generar los review packets de los finalistas.",
            CampaignStage.external_review_pending.value: "Consultar y/o importar revisiones externas.",
            CampaignStage.synthesis.value: "Sintetizar el comité y decidir el siguiente paso.",
            CampaignStage.experiment_design.value: "Diseñar el experimento de la prioritaria.",
            CampaignStage.owner_review.value: "Presentar la decisión al propietario.",
            CampaignStage.completed.value: "Campaña cerrada.",
        }.get(stage, "Avanzar la etapa actual.")

    # ==================================================================
    # Prompt breve reutilizable (generado desde el estado real)
    # ==================================================================
    def short_prompt(self, campaign_id: str) -> str:
        campaign = self.repos.campaigns.get_campaign(campaign_id)
        if campaign is None:
            raise NotFoundError("Campaña no encontrada.")
        sessions = self.repos.campaigns.sessions_for(campaign_id)
        session = sessions[0] if sessions else None
        hint = ""
        if session and session.get("next_session_path") and Path(session["next_session_path"]).exists():
            hint = f" Lee NEXT_SESSION.md ({session['next_session_path']})."
        return (
            f"Continúa la campaña {campaign['id']} ({campaign['title']}) siguiendo SESSION_PLAN.md. "
            f"Lee AGENTS.md, SESSION_STATE.json y NEXT_SESSION.md.{hint} "
            f"Ejecuta las tareas de la etapa {campaign['stage']} sin pedirme confirmación, "
            f"valida los resultados, importa los outputs y finaliza la sesión con finalize_session.py. "
            f"No inventes evidencia ni uses APIs de pago (api_budget_usd=0). "
            f"Si la campaña no supera los umbrales, ciérrala guardando el motivo."
        )

    # ==================================================================
    # Importación de SESSION_OUTPUT.json
    # ==================================================================
    def import_session_output(self, session_id: str, payload: SessionOutputIn | dict) -> dict[str, Any]:
        data = payload.model_dump() if isinstance(payload, SessionOutputIn) else payload
        session = self.repos.campaigns.get_session(session_id)
        if session is None:
            raise NotFoundError("Sesión no encontrada.")
        if session["status"] == "completed":
            raise ConflictError("La sesión ya está finalizada; crea una sesión nueva para seguir.")
        if data.get("session_id") != session_id:
            raise ValidationError("session_id del payload no coincide con la sesión.")

        campaign = self.repos.campaigns.get_campaign(session["campaign_id"])
        if campaign is None:
            raise NotFoundError("Campaña no encontrada.")

        # Política: cero API durante el descubrimiento.
        if int(data.get("api_calls_made", 0)) > 0 or float(data.get("api_cost_usd", 0.0)) > 0:
            raise ValidationError(
                "api_budget_usd=0 en esta campaña: las sesiones Freebuff-first no consumen APIs de pago."
            )

        discovery_id = self._ensure_discovery_campaign(campaign)

        errors: list[str] = []
        blocked: list[str] = list(data.get("blockers") or [])
        concepts_created = 0
        concepts_rejected = 0
        evidences_added = 0
        signals_added = 0
        missions_imported = 0
        reviews_imported = 0

        # --- Señales (dedup por hash de contenido) -----------------------------
        seen_signals = set()
        for signal in data.get("signals") or []:
            if not isinstance(signal, dict):
                continue
            key = _sha256(json.dumps(signal, ensure_ascii=False, sort_keys=True))
            if key in seen_signals:
                continue
            seen_signals.add(key)
            if signal.get("tension") or signal.get("observation"):
                signals_added += 1
        if signals_added:
            self.repos.campaigns.update_campaign(campaign["id"], signals_count=campaign.get("signals_count", 0) + signals_added)

        # --- Conceptos (dedup por título normalizado + límites del embudo) -----
        funnel = _funnel(campaign)
        imported_concepts: list[dict[str, Any]] = []
        rejected_payload = list(data.get("concepts_rejected") or [])
        for item in data.get("concepts") or []:
            if not isinstance(item, dict):
                continue
            current_count = campaign.get("concepts_count", 0) + len(imported_concepts)
            if current_count >= funnel["max_concepts"]:
                blocked.append(f"Límite del embudo alcanzado: max_concepts={funnel['max_concepts']}.")
                break
            concept = self.discovery.import_concept(discovery_id, item, source="session")
            if concept is None:
                errors.append(f"Concepto duplicado o inválido descartado: {str(item.get('title'))[:60]}")
            else:
                imported_concepts.append(concept)
        if imported_concepts:
            self.repos.campaigns.update_campaign(
                campaign["id"], concepts_count=campaign.get("concepts_count", 0) + len(imported_concepts)
            )
            concepts_created = len(imported_concepts)

        # --- Conceptos rechazados (aprendizajes) -------------------------------
        for item in rejected_payload:
            if not isinstance(item, dict):
                continue
            concepts_rejected += 1
            self.repos.discovery.add_learning_record(
                kind="rejection",
                pattern=str(item.get("pattern") or f"Rechazado en sesión: {str(item.get('title'))[:80]}"),
                source=f"session:{session_id}",
                notes=str(item.get("reason") or "")[:500],
            )
        if concepts_rejected:
            self.repos.campaigns.update_campaign(
                campaign["id"], concepts_rejected=campaign.get("concepts_rejected", 0) + concepts_rejected
            )

        # --- Evidencias (dedup por URL + resumen; regla de verificación) -------
        for raw in data.get("evidences") or []:
            if not isinstance(raw, dict) or not raw.get("summary"):
                continue
            if self._evidence_is_duplicate(raw):
                continue
            evidence = self._build_evidence(raw, session_id)
            if evidence is None:
                continue
            opp_id = raw.get("opportunity_id")
            if opp_id and self.repos.opportunities.get(opp_id):
                self.repos.evidence.create(evidence(opportunity_id=opp_id))
                evidences_added += 1

        # --- Resultados de misiones --------------------------------------------
        for res in data.get("mission_results") or []:
            if not isinstance(res, dict) or not res.get("mission_id"):
                continue
            try:
                from app.models.discovery import MissionIn

                self.discovery.import_mission_result(res["mission_id"], MissionIn.model_validate(res))
                missions_imported += 1
            except Exception as exc:
                errors.append(f"Misión {str(res.get('mission_id'))[:20]}: {exc}")

        # --- Revisiones externas ------------------------------------------------
        for rev in data.get("reviews") or []:
            if not isinstance(rev, dict) or not rev.get("content") or not rev.get("opportunity_id"):
                errors.append("Revisión sin content u opportunity_id; ignorada.")
                continue
            try:
                payload_review = ReviewImportIn(
                    filename=str(rev.get("filename") or "revision.txt"),
                    content=str(rev["content"]),
                    provider=str(rev.get("provider") or "unknown"),
                    model=str(rev.get("model") or "unknown"),
                    execution_mode=str(rev.get("execution_mode") or "MANUAL_IMPORT"),
                    imported_by="freebuff-session",
                )
                self.reviews.import_review(str(rev["opportunity_id"]), payload_review)
                reviews_imported += 1
            except ConflictError:
                errors.append("Revisión duplicada (mismo hash) ignorada.")
            except Exception as exc:
                errors.append(f"Revisión: {exc}")

        # --- Actualizar sesión ---------------------------------------------------
        completed = list(dict.fromkeys(list(session.get("tasks_completed") or []) + list(data.get("completed_tasks") or [])))
        pending = [t for t in session.get("tasks_pending") or [] if t not in completed]
        updated_session = self.repos.campaigns.update_session(
            session_id,
            status="active",
            tasks_completed=completed,
            tasks_pending=pending,
            concepts_created=session.get("concepts_created", 0) + concepts_created,
            concepts_rejected=session.get("concepts_rejected", 0) + concepts_rejected,
            evidences_added=session.get("evidences_added", 0) + evidences_added,
            blockers=blocked,
            errors=list(dict.fromkeys(errors)),
            next_action=self._next_action_for(self.repos.campaigns.get_campaign(campaign["id"])),
        )
        self.repos.campaigns.update_campaign(
            campaign["id"],
            evidences_added=campaign.get("evidences_added", 0) + evidences_added,
            missions_count=campaign.get("missions_count", 0) + missions_imported,
        )
        self.record_reasoning(
            campaign["id"], ReasoningLevel.level_1_fast_review,
            "import_session_output", "Deduplicación, límites de embudo e integración de outputs (nivel 0-1).",
            session_id=session_id,
        )

        # --- Auto-avance determinista si los entregables ya se cumplen -----------
        auto = self._auto_advance(campaign["id"])
        return {
            "session": updated_session,
            "campaign": self.campaign_detail(campaign["id"]),
            "counters": {
                "signals_added": signals_added,
                "concepts_created": concepts_created,
                "concepts_duplicates_skipped": len(data.get("concepts") or []) - concepts_created,
                "concepts_rejected": concepts_rejected,
                "evidences_added": evidences_added,
                "missions_imported": missions_imported,
                "reviews_imported": reviews_imported,
            },
            "errors": errors,
            "blockers": blocked,
            "auto_advanced_to": auto,
        }

    def _auto_advance(self, campaign_id: str) -> str | None:
        """Avanza una etapa cada vez mientras se cumplan los entregables (sin LLM)."""
        campaign = self.repos.campaigns.get_campaign(campaign_id)
        if campaign is None or campaign["status"] != CampaignStatus.active.value:
            return None
        current = campaign["stage"]
        idx = STAGE_ORDER.index(current)
        if idx + 1 >= len(STAGE_ORDER):
            return None
        nxt = CampaignStage(STAGE_ORDER[idx + 1])
        missing = self._missing_deliverables(campaign, [nxt.value])
        if missing:
            return None
        # No auto-completar la última etapa (requiere decisión del propietario).
        if nxt == CampaignStage.completed:
            return None
        updated = self.repos.campaigns.update_campaign(campaign_id, stage=nxt.value)
        self._transition(updated or campaign, nxt, actor="system", reason="Entregables de la etapa cumplidos tras importar la sesión.")
        return nxt.value

    def _ensure_discovery_campaign(self, campaign: dict[str, Any]) -> str:
        if campaign.get("discovery_campaign_id"):
            return campaign["discovery_campaign_id"]
        created = self.discovery.create_campaign(
            {
                "title": f"FF {campaign['title'][:80]}",
                "territory_keys": campaign.get("territory_keys") or [],
                "lens_keys": campaign.get("lens_keys") or [],
                "archetype_keys": campaign.get("archetype_keys") or [],
                "phase1_target": min(100, max(20, int((campaign.get("funnel_limits") or {}).get("max_concepts", 100)))),
                "shortlist_target": 10,
                "finalists_target": int((campaign.get("funnel_limits") or {}).get("maximum_finalists", 3)),
            }
        )
        self.repos.campaigns.update_campaign(campaign["id"], discovery_campaign_id=created["id"])
        return created["id"]

    # ==================================================================
    # Finalización de sesión
    # ==================================================================
    def finalize_session(self, session_id: str) -> dict[str, Any]:
        session = self.repos.campaigns.get_session(session_id)
        if session is None:
            raise NotFoundError("Sesión no encontrada.")
        if session["status"] == "completed":
            raise ConflictError("La sesión ya está finalizada.")
        campaign = self.repos.campaigns.get_campaign(session["campaign_id"])
        if campaign is None:
            raise NotFoundError("Campaña no encontrada.")

        # Entregables mínimos de la sesión: al menos una tarea completada o
        # un output importado, salvo cierre explícito por blockers.
        if not session.get("tasks_completed") and session.get("concepts_created", 0) == 0 and session.get("evidences_added", 0) == 0:
            raise ValidationError(
                "La sesión no tiene entregables (tareas completadas, conceptos o evidencias). "
                "Importa SESSION_OUTPUT.json antes de finalizar."
            )

        session_dir = self._session_dir(campaign["id"], session["session_id"])
        session_dir.mkdir(parents=True, exist_ok=True)
        report_path = session_dir / "SESSION_REPORT.md"
        next_path = session_dir / "NEXT_SESSION.md"
        report_path.write_text(self._build_session_report(session, campaign), encoding="utf-8")
        next_md = self._build_next_session(session, campaign)
        next_path.write_text(next_md, encoding="utf-8")

        updated = self.repos.campaigns.update_session(
            session_id,
            status="completed",
            completed_at=_now(),
            stage_end=campaign["stage"],
            report_path=str(report_path),
            next_session_path=str(next_path),
        )
        self.record_reasoning(
            campaign["id"], ReasoningLevel.level_0_deterministic,
            "finalize_session", "Checkpoint persistido: SESSION_REPORT.md + NEXT_SESSION.md.",
            session_id=session_id,
        )
        return {
            "session": updated,
            "campaign": self.campaign_detail(campaign["id"]),
            "report_path": str(report_path),
            "next_session_path": str(next_path),
            "next_session_markdown": next_md,
        }

    def _build_session_report(self, session: dict[str, Any], campaign: dict[str, Any]) -> str:
        lines = [
            "# SESSION_REPORT.md",
            "",
            f"- **session_id**: {session['session_id']}",
            f"- **campaign_id**: {campaign['id']}",
            f"- **tiempo asignado**: {session['time_budget_hours']} h (no garantizado)",
            f"- **etapa de inicio**: {session['stage_start']} → **etapa al finalizar**: {campaign['stage']}",
            "",
            "## Qué se hizo realmente",
        ]
        for t in session.get("tasks_completed") or []:
            lines.append(f"- {t}")
        if not session.get("tasks_completed"):
            lines.append("- (sin tareas marcadas completadas)")
        lines.append("")
        lines.append("## Qué se verificó")
        lines.append(f"- Conceptos importados: {session.get('concepts_created', 0)} (duplicados descartados por título).")
        lines.append(f"- Conceptos rechazados: {session.get('concepts_rejected', 0)}.")
        lines.append(f"- Evidencias añadidas: {session.get('evidences_added', 0)} (solo verified=true con URL+fecha+fragmento).")
        lines.append(f"- Llamadas API: 0 · coste API: 0 USD (política api_budget_usd=0).")
        lines.append("")
        lines.append("## Qué es solo hipótesis")
        lines.append("- Todos los conceptos importados son HIPÓTESIS hasta que una misión aporte evidencia.")
        lines.append("- La demanda nunca se da por verificada sin fuentes concretas.")
        lines.append("")
        lines.append("## Qué quedó pendiente")
        for t in session.get("tasks_pending") or []:
            lines.append(f"- [ ] {t}")
        if not session.get("tasks_pending"):
            lines.append("- Nada pendiente en esta etapa.")
        for b in session.get("blockers") or []:
            lines.append(f"- Blocker: {b}")
        for e in session.get("errors") or []:
            lines.append(f"- Error: {e}")
        lines.append("")
        lines.append("## Siguiente acción recomendada")
        lines.append(f"- {session.get('next_action') or self._next_action_for(campaign)}")
        lines.append("- Iniciar una sesión nueva con `python3 scripts/continue_campaign.py --campaign <id> --hours <2-6>`.")
        lines.append("")
        return "\n".join(lines)

    def _build_next_session(self, session: dict[str, Any], campaign: dict[str, Any]) -> str:
        prompt = self.short_prompt(campaign["id"])
        lines = [
            "# NEXT_SESSION.md",
            "",
            f"- **campaign_id**: {campaign['id']}",
            f"- **campaign**: {campaign['title']}",
            f"- **stage alcanzado**: {campaign['stage']}",
            f"- **contadores**: conceptos={campaign.get('concepts_count', 0)} · rechazados={campaign.get('concepts_rejected', 0)} · finalistas={campaign.get('finalists_count', 0)} · misiones={campaign.get('missions_count', 0)}",
            "",
            "## Tareas pendientes",
        ]
        for t in session.get("tasks_pending") or []:
            lines.append(f"- [ ] {t}")
        if not session.get("tasks_pending"):
            lines.append("- (etapa actual sin tareas pendientes; avanzar de etapa si los entregables se cumplen)")
        lines.append("")
        lines.append("## Próxima acción")
        lines.append(f"- {self._next_action_for(campaign)}")
        lines.append("")
        lines.append("## Prompt breve para la próxima sesión")
        lines.append("```text")
        lines.append(prompt)
        lines.append("```")
        lines.append("")
        lines.append("## Reglas permanentes")
        lines.append("- No gastar tokens de API en descubrimiento (api_budget_usd=0).")
        lines.append("- No fingir que Freebuff es un runtime 24/7; esta sesión deja checkpoint.")
        lines.append("- Ninguna campaña está obligada a producir una finalista.")
        lines.append("- El consenso de modelos no es evidencia de mercado.")
        lines.append("")
        return "\n".join(lines)

    # ==================================================================
    # Evidencias de sesión (regla de verificación estricta)
    # ==================================================================
    def _build_evidence(self, raw: dict[str, Any], session_id: str):
        from app.models.evidence import Evidence, EvidenceCreate

        # Los campos de contexto (opportunity_id, captured_at) no pertenecen a
        # EvidenceCreate (extra=forbid): se extraen antes de validar.
        captured_at = str(raw.get("captured_at") or "") or None
        clean = {k: v for k, v in raw.items() if k not in ("opportunity_id", "captured_at")}
        try:
            create = EvidenceCreate.model_validate(clean)
        except Exception:
            return None
        verified = bool(create.verified and create.source_url and create.raw_excerpt)
        if create.verified and not (create.source_url and create.raw_excerpt):
            # Regla de no auto-verificación: sin URL+fecha+fragmento no hay verified.
            verified = False
        captured_at = captured_at or _now()
        return lambda opportunity_id: Evidence(
            **create.model_dump(exclude={"verified", "verification_notes", "method"}),
            opportunity_id=opportunity_id,
            captured_at=captured_at,
            verified=verified,
            verification_notes=(
                create.verification_notes
                or ("Importado de sesión Freebuff con URL+fragmento." if verified else "Sin URL+fecha+fragmento: NO verificado automáticamente.")
            ),
            collected_by=f"freebuff-session:{session_id[:8]}",
            method="session",
        )

    def _evidence_is_duplicate(self, raw: dict[str, Any]) -> bool:
        summary = str(raw.get("summary") or "")[:300]
        url = str(raw.get("source_url") or "")
        if not summary:
            return True
        for opp in self.repos.opportunities.list():
            for existing in self.repos.evidence.list_for(opp.id):
                if str(existing.summary)[:300] == summary and (not url or (existing.source_url or "") == url):
                    return True
        return False

    def _packets_ready(self, campaign: dict[str, Any]) -> bool:
        packets = list((self.settings.external_reviews_dir / f"opportunity_" if False else self.settings.external_reviews_dir).glob("opportunity_*/review_packet.md"))
        return len(packets) >= max(1, campaign.get("finalists_count", 0))

    def _reviews_started(self, campaign: dict[str, Any]) -> bool:
        return True  # la ventana o la importación lo resuelven; se valida en SYNTHESIS

    def _synthesis_exists(self, campaign: dict[str, Any]) -> bool:
        for item in self.repos.reviews.list_reviews(limit=500):
            if item["opportunity_id"] and self.repos.reviews.get_synthesis(item["opportunity_id"]):
                return True
        return False

    def _experiment_defined(self, campaign: dict[str, Any]) -> bool:
        return True  # se valida en la ficha de la prioritaria; el cierre sin experimento es válido

    # ==================================================================
    # Niveles de razonamiento (ahorro de tokens, auditable)
    # ==================================================================
    def record_reasoning(self, campaign_id: str, level: ReasoningLevel, action: str, reason: str | None = None, *, session_id: str | None = None) -> dict[str, Any]:
        if level in (ReasoningLevel.level_2_deep_reasoning, ReasoningLevel.level_3_committee_ready, ReasoningLevel.level_4_experiment_ready):
            campaign = self.repos.campaigns.get_campaign(campaign_id)
            if campaign is None:
                raise NotFoundError("Campaña no encontrada.")
            limits = _funnel(campaign)
            if level == ReasoningLevel.level_2_deep_reasoning and campaign.get("concepts_count", 0) > limits["max_after_structural"]:
                raise ValidationError("Nivel 2 (razonamiento profundo) solo se aplica a shortlist/finalistas, no a 100 conceptos.")
            if level == ReasoningLevel.level_3_committee_ready and campaign.get("concepts_count", 0) > limits["max_after_structural"]:
                raise ValidationError("Nivel 3 (committee ready) solo para el shortlist (máx. 10 candidatas).")
            if level == ReasoningLevel.level_4_experiment_ready and campaign.get("finalists_count", 0) > limits["maximum_finalists"]:
                raise ValidationError("Nivel 4 (experiment ready) solo para finalistas (máx. 3).")
        record = {
            "campaign_id": campaign_id,
            "session_id": session_id,
            "level": level.value,
            "action": action[:200],
            "reason": (reason or "")[:1_000],
        }
        return self.repos.campaigns.add_reasoning(record)

    # ==================================================================
    # API Readiness Gate (determinista; no activa ninguna API)
    # ==================================================================
    def evaluate_api_readiness(self, opportunity_id: str) -> dict[str, Any]:
        opportunity = self.repos.opportunities.get(opportunity_id)
        if opportunity is None:
            raise NotFoundError("Oportunidad no encontrada.")
        evaluation = self.repos.evaluations.get(opportunity_id)
        estimates = evaluation.estimates if evaluation else None
        experiment = self.repos.experiments.get_for(opportunity_id) if self.repos.experiments.get_for(opportunity_id) else None
        evidences = self.repos.evidence.list_for(opportunity_id)
        synthesis = self.repos.reviews.get_synthesis(opportunity_id)

        verified_evidence = [e for e in evidences if e.verified and e.source_url]
        criteria = {
            "oportunidad_finalista": opportunity.status.value in ("approved", "needs_more_research"),
            "no_commodity": True,  # se afina con venture si existe; sin datos se asume no bloqueado
            "comprador_concreto": bool(opportunity.target_customer and "DESCONOCIDO" not in opportunity.target_customer.upper()),
            "canal_viable": bool(estimates and estimates.reachability and "DESCONOCIDO" not in estimates.reachability.upper()),
            "resultado_verificable": bool(estimates and (estimates.automation_degree is not None or estimates.automatable_steps)),
            "experimento_definido": bool(experiment and experiment.cheapest_test and experiment.success_metric),
            "evidencia_externa_suficiente": len(verified_evidence) >= 1,
            "comite_procesado": bool(synthesis and synthesis.get("valid_reviews_count") and synthesis["valid_reviews_count"] >= 1),
            "incertidumbre_principal_identificada": bool(synthesis and synthesis.get("missing_evidence")),
            "trabajo_repetitivo_continuo": bool(estimates and (estimates.automatable_steps or estimates.automation_degree and estimates.automation_degree >= 60)),
            "coste_por_llamada_estimable": True,
            "valor_vs_coste_inferencia": True,
            "fallback_posible": True,
            "limite_diario_propuesto": True,
        }
        missing = [k for k, v in criteria.items() if not v]
        unknown = []
        if "oportunidad_finalista" in missing:
            unknown.append("la oportunidad no es finalista aprobada")
        if "evidencia_externa_suficiente" in missing:
            unknown.append("sin evidencia externa verificada (URL+fecha+fragmento)")
        if "comite_procesado" in missing:
            unknown.append("comité externo no procesado")

        cost_per_call = 0.01  # estimación para gate; no configura claves
        value_per_call = 0.05 if opportunity.status.value == "approved" else 0.01
        daily_limit = 0.10

        if "oportunidad_finalista" in missing or "comprador_concreto" in missing or "canal_viable" in missing:
            state = APIReadinessState.api_premature
        elif not criteria["trabajo_repetitivo_continuo"]:
            state = APIReadinessState.api_not_needed
        elif criteria["trabajo_repetitivo_continuo"] and all(criteria.values()) and criteria["evidencia_externa_suficiente"]:
            state = APIReadinessState.api_required_for_24_7_operation
        elif all(criteria.values()):
            state = APIReadinessState.api_required_for_delivery
        elif criteria["evidencia_externa_suficiente"] and criteria["experimento_definido"]:
            state = APIReadinessState.api_useful_for_experiment
        elif value_per_call < cost_per_call:
            state = APIReadinessState.api_rejected_low_roi
        else:
            state = APIReadinessState.api_premature

        gate = APIReadinessGate(
            opportunity_id=opportunity_id,
            state=state,
            criteria=criteria,
            unknown_criteria=unknown,
            missing=missing,
            reasoning=(
                f"Gate determinista: {sum(criteria.values())}/{len(criteria)} criterios cumplidos. "
                f"Coste estimado/llamada: {cost_per_call:.2f} USD · valor estimado: {value_per_call:.2f} USD · "
                "límite diario propuesto: 0.10 USD. NO se activa ninguna API."
            ),
            proposed_daily_limit_usd=daily_limit,
            estimated_cost_per_call_usd=cost_per_call,
            estimated_value_per_call_usd=value_per_call,
        )
        saved = self.repos.campaigns.save_readiness(gate.model_dump(mode="json"))
        if self.engine is not None:
            try:
                self.engine.record_event(
                    event_type="api_readiness",
                    summary=f"API Readiness de {opportunity.title[:40]}: {state.value}.",
                    opportunity_id=opportunity_id,
                )
            except Exception:
                pass
        return saved

    # ==================================================================
    # Piloto sintético FREEBUFF-FIRST PILOT 001
    # ==================================================================
    def run_demo(self, pipeline) -> dict[str, Any]:
        """Piloto 100% sintético: campaña, 2 sesiones, checkpoints, comité,
        readiness y cierre. No consume APIs (0 llamadas)."""
        existing = [c for c in self.repos.campaigns.list_campaigns() if c["title"] == "FREEBUFF-FIRST PILOT 001"]
        if existing:
            return {"reused": True, "detail": self.campaign_detail(existing[0]["id"])}

        created = self.create_campaign(
            CampaignCreate(
                title="FREEBUFF-FIRST PILOT 001",
                time_budget_hours=5,
                territory_keys=["small_businesses", "invisible_admin_work"],
                lens_keys=["UNBUNDLE_EXPENSIVE_SERVICE", "VERIFY_THE_OUTPUT", "SELL_SAVED_TIME"],
                archetype_keys=["VALIDABLE_CONCIERGE", "VERIFICATION_TOOL", "SOFTWARE_ENABLED_SERVICE"],
                maximum_finalists=3,
                notes="Piloto SINTÉTICO de demostración del protocolo Freebuff-first.",
            )
        )
        campaign_id = created["campaign"]["id"]

        # --- Sesión 1 (5 h): señales + ideación + filtro -------------------------
        session1 = self.prepare_session(campaign_id, 5, actor="demo")
        output1 = {
            "session_id": session1["session_id"],
            "completed_tasks": ["Recoger 3-5 señales de mercado", "Generar conceptos breves"],
            "signals": [
                {"tension": "Los comercios pequeños concilian stock a mano (hojas de cálculo).", "observation": "Hilo de un foro de retail (sintético, sin URL real)."},
                {"tension": "Los autónomos pierden horas re-facturando entre aplicaciones.", "observation": "Queja recurrente en grupos de autónomos (sintético)."},
                {"tension": "Los talleres locales no publican disponibilidad en tiempo real.", "observation": "Reseñas mencionan llamadas perdidas (sintético)."},
            ],
            "concepts": [
                {"title": "Conciliación de inventario físico-online para pequeños comercios", "territory_key": "small_businesses", "lens_keys": ["VERIFY_THE_OUTPUT"], "archetype_key": "VERIFICATION_TOOL", "problem_hypothesis": "El stock no coincide entre canales y se pierden ventas.", "mechanism": "Detección automática de discrepancias de stock entre caja y tienda online con informe accionable semanal.", "buyer_hypothesis": "Dueño de comercio con 1-50 empleados (HIPÓTESIS).", "outcome_hypothesis": "Reducción medible de cancelaciones por falta de stock (HIPÓTESIS)."},
                {"title": "Validación de facturas entre herramientas para autónomos", "territory_key": "invisible_admin_work", "lens_keys": ["UNBUNDLE_EXPENSIVE_SERVICE"], "archetype_key": "VALIDABLE_CONCIERGE", "problem_hypothesis": "Los autónomos pierden horas cotejando facturas entre apps.", "mechanism": "Servicio concierge que reconcilia facturas entre herramientas y devuelve un resumen verificable.", "buyer_hypothesis": "Autónomo con 2+ herramientas de facturación (HIPÓTESIS).", "outcome_hypothesis": "Horas ahorradas por semana (HIPÓTESIS)."},
                {"title": "Disponibilidad en vivo para talleres de reparación locales", "territory_key": "small_businesses", "lens_keys": ["SELL_SAVED_TIME"], "archetype_key": "SOFTWARE_ENABLED_SERVICE", "problem_hypothesis": "Los talleres pierden clientes por no publicar disponibilidad.", "mechanism": "Agenda compartida con confirmación automática por mensaje para el cliente.", "buyer_hypothesis": "Jefe de taller local (HIPÓTESIS).", "outcome_hypothesis": "Menos llamadas perdidas (HIPÓTESIS)."},
                {"title": "Chat genérico que genera contenido para pequeños comercios", "territory_key": "small_businesses", "lens_keys": ["ENTERTAINMENT_PLUS_UTILITY"], "archetype_key": "PROSUMER_PRODUCT", "problem_hypothesis": "Los comercios necesitan contenido genérico para redes.", "mechanism": "Un chat que genera publicaciones a partir de lo que el cliente pega: una IA generalista lo resuelve.", "buyer_hypothesis": "Comerciante (HIPÓTESIS).", "outcome_hypothesis": None},
                {"title": "Generador de informes de ventas genéricos con IA", "territory_key": "invisible_admin_work", "lens_keys": ["SELL_SAVED_TIME"], "archetype_key": "PROSUMER_PRODUCT", "problem_hypothesis": "Los autónomos quieren informes automáticos.", "mechanism": "Pegar los datos en ChatGPT produce el mismo informe: prompt envuelto.", "buyer_hypothesis": "Autónomo (HIPÓTESIS).", "outcome_hypothesis": None},
                {"title": "Verificación de reseñas reales para servicios locales", "territory_key": "small_businesses", "lens_keys": ["VERIFY_THE_OUTPUT"], "archetype_key": "VERIFICATION_TOOL", "problem_hypothesis": "Los clientes no distinguen reseñas reales de falsas.", "mechanism": "Informe de plausibilidad de reseñas por patrones de actividad, con trazabilidad.", "buyer_hypothesis": "Gestor de reputación local (HIPÓTESIS).", "outcome_hypothesis": "Riesgo de reseña falsa detectado (HIPÓTESIS)."},
                {"title": "Conciliación de pagos entre pasarelas para autónomos", "territory_key": "invisible_admin_work", "lens_keys": ["VERIFY_THE_OUTPUT"], "archetype_key": "VERIFICATION_TOOL", "problem_hypothesis": "Los cobros no cuadran entre pasarelas y la contabilidad manual.", "mechanism": "Comparación automática de movimientos entre pasarelas y contabilidad, con alertas.", "buyer_hypothesis": "Autónomo/contable (HIPÓTESIS).", "outcome_hypothesis": "Discrepancias detectadas por semana (HIPÓTESIS)."},
                {"title": "Disponibilidad de mecánicos en tiempo real para flotas", "territory_key": "small_businesses", "lens_keys": ["SELL_SAVED_TIME"], "archetype_key": "SOFTWARE_ENABLED_SERVICE", "problem_hypothesis": "Las flotas pierden tiempo esperando talleres.", "mechanism": "Red de disponibilidad de talleres con reserva directa.", "buyer_hypothesis": "Gestor de flota (HIPÓTESIS).", "outcome_hypothesis": "Tiempo de espera reducido (HIPÓTESIS)."},
            ],
            "concepts_rejected": [
                {"title": "Directorio genérico de servicios locales", "pattern": "Directorio sin distribución", "reason": "No resuelve el problema de liquidez."},
            ],
            "evidences": [],
            "mission_results": [],
            "reviews": [],
            "blockers": [],
            "unknowns": ["demanda no verificada"],
            "notes": "Output SINTÉTICO de demostración; conceptos marcados como hipótesis.",
            "api_calls_made": 0,
            "api_cost_usd": 0.0,
        }
        import1 = self.import_session_output(session1["session_id"], SessionOutputIn.model_validate(output1))
        # Filtro determinista de comoditización sobre los conceptos importados.
        discovery_id = self.repos.campaigns.get_campaign(campaign_id)["discovery_campaign_id"]
        self.discovery.run_commodity_filter(discovery_id)
        final1 = self.finalize_session(session1["session_id"])

        # --- Sesión 2: recombinación + shortlist + torneo + finalistas -----------
        session2 = self.prepare_session(campaign_id, 5, actor="demo")
        # Recombinar deterministamente y seleccionar shortlist/torneo.
        self.discovery.run_recombine(discovery_id)
        self.discovery.run_shortlist(discovery_id)
        self.discovery.run_tournament(discovery_id)

        detail = self.discovery.campaign_detail(discovery_id)
        finalist_concepts = [c for c in detail["concepts"] if c["status"] == "finalist"][: 3]
        promoted: list[Any] = []
        for concept in finalist_concepts:
            promoted.append(self.discovery.promote(concept["id"]))
        self.repos.campaigns.update_campaign(campaign_id, finalists_count=len(promoted))

        # Misiones de investigación para cada finalista.
        for concept in finalist_concepts:
            self.discovery.create_mission(kind="DEMAND_REALITY_CHECK", concept_id=concept["id"])
            self.discovery.create_mission(kind="TOS_AND_LEGAL_CHECK", concept_id=concept["id"])
        missions = [m for m in self.discovery.list_missions() if m["kind"] in ("DEMAND_REALITY_CHECK", "TOS_AND_LEGAL_CHECK")]
        self.repos.campaigns.update_campaign(campaign_id, missions_count=len(missions))

        # Expedientes de comité para cada finalista.
        packets = []
        for opp in promoted:
            packets.append(self.reviews.generate_review_packet(opp.id))

        # Importar 3 revisiones MOCK (desacuerdo) por HTTP-equivalente (servicio).
        mock_reviews = [
            {"provider": "gpt", "model": "gpt-4o", "rec": "PRIORITY_EXPERIMENT", "conf": 70},
            {"provider": "grok", "model": "grok-3", "rec": "MORE_RESEARCH", "conf": 60},
            {"provider": "gemini", "model": "gemini-2.0-flash", "rec": "SMALL_EXPERIMENT", "conf": 65},
        ]
        for opp in promoted:
            for i, rev in enumerate(mock_reviews):
                content = (
                    f"Revisión DEMO (mock) — {rev['provider']}\n\n"
                    f"recommendation: {rev['rec']}\nconfidence: {rev['conf']}\n"
                    f"primary_risk: Riesgo de validación (sintético).\n"
                )
                try:
                    self.reviews.import_review(
                        opp.id,
                        ReviewImportIn(
                            filename=f"mock_{rev['provider']}_{i}.txt", content=content,
                            provider=rev["provider"], model=rev["model"],
                            execution_mode="MOCK", imported_by="demo-pilot",
                        ),
                    )
                except ConflictError:
                    pass
            self.reviews.synthesize(opp.id)

        # Readiness gate de la prioritaria y cierre.
        priority = promoted[0] if promoted else None
        readiness = None
        if priority:
            readiness = self.evaluate_api_readiness(priority.id)
        self.repos.campaigns.update_campaign(
            campaign_id, next_recommended_action="Piloto completado: revisar la prioritaria y decidir el siguiente paso."
        )
        closed = self.set_campaign_status(
            campaign_id, CampaignStatus.completed,
            reason="Piloto SINTÉTICO finalizado: 1 prioritaria seleccionada, comité procesado, readiness evaluado, sin gasto API.",
        )
        return {
            "campaign_id": campaign_id,
            "is_synthetic": True,
            "sessions": [final1["session"]["session_id"], session2["session_id"]],
            "concepts": self.repos.campaigns.get_campaign(campaign_id)["concepts_count"],
            "concepts_rejected": self.repos.campaigns.get_campaign(campaign_id)["concepts_rejected"],
            "finalists": [o.title for o in promoted],
            "finalists_count": len(promoted),
            "missions_count": len(missions),
            "review_packets": [p["sha256"] for p in packets],
            "readiness": readiness,
            "detail": self.campaign_detail(campaign_id),
            "short_prompt": self.short_prompt(campaign_id),
            "note": "Piloto 100% SINTÉTICO: no representa demanda real ni dinero real; 0 llamadas API.",
        }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
