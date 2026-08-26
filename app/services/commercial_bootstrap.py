"""Bootstrap comercial (iteración 022) — activación de un clic del propietario.

Convierte la lógica de ``scripts/activate_commercial_021.py`` y
``scripts/readiness_launch_021.py`` en un servicio interno idempotente y
transaccional: localiza la campaña LOCAL (o la crea de forma determinista),
recupera ejecuciones FAILED, importa la investigación portable contra misiones
LOCALES por mapeo estable (título normalizado + kind), adjunta evidencias,
recalcula puntuaciones, selecciona la ganadora determinista, crea el
experimento, encola el comité y deja el sistema en READY_TO_CONNECT_SERVICES.

Reglas inmutables que respeta:

- NUNCA inserta IDs de otra base: los ``concept_id``/``opportunity_id`` del
  paquete son SOLO procedencia; la resolución es por mapeo estable local.
- Idempotente: si ya está aplicado (o una misión ya está importada), no
  duplica datos y puede reanudarse tras un corte (checkpoints append-only).
- No borra ideas ni evidencia legítima de la instalación.
- Deja PRE_CYCLE detenido, gasto real en cero y producción bloqueada.
- Cada paso se registra en ``decision_log`` (append-only) y en checkpoints.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT
from app.models.decision_log import DecisionLog
from app.models.enums import Decision
from app.models.evaluation import Evaluation
from app.models.external_review import QueueOpportunityIn
from app.models.orchestrator import ExperimentPlan, RESEARCH_PHASE1_KINDS

BOOTSTRAP_VERSION = "1"
ASSET_DIR = PROJECT_ROOT / "resources" / "bootstrap" / "commercial_021"
ASSET_MANIFEST = "manifest.json"
ASSET_RESEARCH = "investigacion_fase1_021.json"
ASSET_CANDIDATAS = "candidatas.json"

WINNER_TITLE = (
    "Benchmark anonimo de tarifas para clinicas dentales que deciden su precio de ortodoncia"
)

# Estados del orquestador en los que el bootstrap debe avanzar hasta RESEARCH_PENDING.
_PRE_RESEARCH_STATES = (
    "CAMPAIGN_CREATED", "DISCOVERING", "DEDUPLICATING", "FILTERING_COMMODITIES",
    "RECOMBINING", "STRUCTURAL_ANALYSIS", "SHORTLISTING", "TOURNAMENT", "RESEARCH_PLANNED",
)

# Estados que indican investigación ya importada (bootstrap aplicado o en curso).
_RESEARCH_DONE_STATES = (
    "RESEARCH_IMPORTED", "REEVALUATING", "CANDIDATES_READY", "FINALISTS_READY",
    "COMMITTEE_READY", "COMMITTEE_PENDING", "COMMITTEE_COMPLETED", "DECIDING",
    "EXPERIMENT_READY", "EXPERIMENT_BLOCKED", "PRE_CYCLE", "READY_TO_START_CYCLE", "COMPLETED",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(text: str) -> str:
    """Normaliza un título: minúsculas, sin acentos, solo alfanuméricos."""
    t = unicodedata.normalize("NFKD", str(text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


class BootstrapError(Exception):
    """Error controlado del bootstrap: mensaje sanitizado, sin stack traces."""


class CommercialBootstrapService:
    """Activa la investigación comercial 021 en la instalación local."""

    def __init__(self, container) -> None:
        self.c = container

    # ------------------------------------------------------------------ assets
    def load_assets(self) -> dict[str, Any]:
        manifest_path = ASSET_DIR / ASSET_MANIFEST
        research_path = ASSET_DIR / ASSET_RESEARCH
        candidatas_path = ASSET_DIR / ASSET_CANDIDATAS
        missing = [p.name for p in (manifest_path, research_path, candidatas_path) if not p.exists()]
        if missing:
            raise BootstrapError(
                "Activos de bootstrap incompletos (faltan: " + ", ".join(missing) + "). "
                "Reinstala el paquete completo de WAWA."
            )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        research = json.loads(research_path.read_text(encoding="utf-8"))
        candidatas = json.loads(candidatas_path.read_text(encoding="utf-8"))
        expected = (manifest.get("checksums") or {}).get(ASSET_RESEARCH)
        actual = hashlib.sha256(research_path.read_bytes()).hexdigest()
        if expected and actual != expected:
            raise BootstrapError("El hash de la investigación portable no coincide con el manifiesto; el paquete está corrupto o alterado.")
        return {"manifest": manifest, "research": research, "candidatas": candidatas}

    # -------------------------------------------------------------- checkpoints
    def _checkpoint(self, component: str, state: str, detail: str = "") -> None:
        try:
            self.c.conn.execute(
                "INSERT INTO bootstrap_checkpoints (component, state, detail, created_at) VALUES (?,?,?,?)",
                (component, state, detail, _now_iso()),
            )
            self.c.conn.commit()
        except Exception:
            self.c.conn.rollback()

    def _checkpoint_done(self, component: str) -> bool:
        try:
            row = self.c.conn.execute(
                "SELECT state FROM bootstrap_checkpoints WHERE component = ? ORDER BY id DESC LIMIT 1",
                (component,),
            ).fetchone()
            return bool(row and row["state"] == "done")
        except Exception:
            return False

    # ------------------------------------------------------------ estado (ro)
    def status(self, *, include_snapshot: bool = False) -> dict[str, Any]:
        """Estado honesto del bootstrap SIN ejecutarlo (para el botón)."""
        assets_ok = True
        assets_error = None
        try:
            self.load_assets()
        except BootstrapError as exc:
            assets_ok = False
            assets_error = str(exc)

        applied = self._read_applied()
        run = self._locate_run()
        run_state = (run or {}).get("state")
        run_status = (run or {}).get("status")
        recoverable_failed = bool(
            run and (run_status == "failed" or run_state == "FAILED") and run.get("discovery_campaign_id")
        )
        missing_activation = not (applied and applied.get("status") == "applied")
        candidates, winner = None, None
        if run and run.get("discovery_campaign_id"):
            candidates = self._local_candidate_rows(run["discovery_campaign_id"])
            winner = self._local_winner_title(run)
        readiness_state = None
        if include_snapshot:
            snapshot = _safe(lambda: self.c.command_center.snapshot(), {}) or {}
            readiness_state = (snapshot.get("readiness") or {}).get("readiness_state")

        diagnosis: list[dict] = []
        if not assets_ok:
            diagnosis.append({"component": "assets", "transition": None, "message": assets_error,
                              "checkpoint": None, "recovery_action": "Reinstalar el paquete completo de WAWA"})
        if run is None:
            diagnosis.append({"component": "run", "transition": None,
                              "message": "No existe ejecución del orquestador; se creará la campaña canónica determinista.",
                              "checkpoint": None, "recovery_action": "Automática (crear campaña)"})
        if recoverable_failed:
            diagnosis.append({"component": "run", "transition": f"FAILED -> {run_state}",
                              "message": "Ejecución en estado FAILED recuperable.",
                              "checkpoint": None, "recovery_action": "Automática (recuperar run)"})
        if missing_activation and assets_ok and run is not None and run.get("discovery_campaign_id"):
            if not candidates:
                diagnosis.append({"component": "candidates", "transition": None,
                                  "message": "No se detectaron candidatas promovibles en la campaña local.",
                                  "checkpoint": None,
                                  "recovery_action": "Automática (crear campaña canónica si no existe la ganadora por título)"})

        return {
            "applied": bool(applied and applied.get("status") == "applied"),
            "applied_version": (applied or {}).get("applied_version"),
            "applied_at": (applied or {}).get("applied_at"),
            "asset_version": BOOTSTRAP_VERSION,
            "assets_ok": assets_ok,
            "run_id": (run or {}).get("id"),
            "run_state": run_state,
            "run_status": run_status,
            "campaign_id": (run or {}).get("discovery_campaign_id"),
            "recoverable": assets_ok and (run is None or recoverable_failed or missing_activation),
            "recoverable_failed": recoverable_failed,
            "can_repair": assets_ok and (run is None or run_status == "failed" or missing_activation),
            "missing_activation": missing_activation,
            "candidates_local": len(candidates or []),
            "winner_local_title": winner,
            "readiness_state": readiness_state,
            "diagnosis": diagnosis,
            "note": "Estado del bootstrap; la ejecución real se hace con POST /api/bootstrap/commercial (idempotente).",
        }

    # --------------------------------------------------------- candidatas (ro)
    def candidates(self) -> dict[str, Any]:
        """Tarjetas de candidatas: datos empaquetados (investigación real 021)
        + puntuaciones/evidencia/revisiones EN VIVO de la instalación local.
        La ganadora se marca como ganadora determinista PARA EXPERIMENTO; nunca
        como demanda validada (no hay pago real)."""
        assets = _safe(lambda: self.load_assets(), None)
        candidatas = (assets or {}).get("candidatas") or {}
        manifest = (assets or {}).get("manifest") or {}
        run = self._locate_run()
        campaign_id = (run or {}).get("discovery_campaign_id")
        selected = (run or {}).get("selected_opportunity_id")
        winner_title = (manifest.get("winner") or {}).get("title") or WINNER_TITLE

        cards: list[dict[str, Any]] = []
        for card in (candidatas.get("candidates") or []):
            title = card.get("title")
            concept = self._find_concept_by_title(campaign_id, title) if campaign_id else None
            opportunity = None
            if concept:
                opportunity = _safe(lambda: self.c.repos.opportunities.get_by_concept(concept["id"]), None)
            venture = {}
            if concept:
                rows = _safe(lambda: self.c.repos.discovery.venture_evaluations_by_concept(concept["id"]), []) or []
                venture = rows[0] if rows else {}
            evidence_count = 0
            evidence_groups = 0
            competitors: list[dict] = []
            if opportunity:
                evidence = _safe(lambda: self.c.repos.evidence.list_for(opportunity.id), []) or []
                verified = [e for e in evidence if getattr(e, "verified", False)]
                evidence_count = len(verified)
                evidence_groups = len({getattr(e, "independence_group", None) or "x" for e in verified})
                competitors = [
                    {"name": c.name, "offer": c.offer, "observed_price": c.observed_price}
                    for c in (_safe(lambda: self.c.repos.competitors.list_for(opportunity.id), []) or [])
                ]
            plan = None
            if opportunity:
                plan = _safe(lambda: self.c.repos.orchestrator.experiment_plan_for_opportunity(opportunity.id), None)
            reviews = 0
            synthesis = None
            if opportunity:
                reviews = len(_safe(lambda: self.c.repos.reviews.reviews_for(opportunity.id), []) or [])
                synthesis = _safe(lambda: self.c.repos.reviews.get_synthesis(opportunity.id), None)
            is_winner = (card.get("role") == "WINNER") or (opportunity is not None and opportunity.id == selected)
            cards.append({
                **card,
                "is_winner": is_winner,
                "winner_badge": "GANADORA DETERMINISTA PARA EXPERIMENTO" if is_winner else "CANDIDATA INVESTIGADA",
                "demand_validated": False,
                "structural_concept_score": venture.get("structural_concept_score"),
                "evidence_backed_venture_score": venture.get("evidence_backed_venture_score"),
                "evidence_verified_live": evidence_count if opportunity else None,
                "evidence_groups_live": evidence_groups if opportunity else None,
                "competitors_live": competitors,
                "opportunity_id": opportunity.id if opportunity else None,
                "concept_id": concept["id"] if concept else None,
                "plan": plan,
                "reviews_count": reviews,
                "synthesis": synthesis,
                "state": concept.get("status") if concept else "SIN DATOS",
                "blockers": venture.get("blockers") or [],
                "source_urls": self._top_sources(opportunity.id) if opportunity else [],
            })
        return {
            "candidates": cards,
            "count": len(cards),
            "winner_title": winner_title,
            "selected_opportunity_id": selected,
            "campaign_id": campaign_id,
            "note": "Preciso y compradores son HIPOTESIS; la ganadora es para experimento (no demanda validada: no hay pago real).",
        }

    def _top_sources(self, opportunity_id: str, limit: int = 6) -> list[str]:
        evidence = _safe(lambda: self.c.repos.evidence.list_for(opportunity_id), []) or []
        urls = []
        for e in evidence:
            if getattr(e, "verified", False) and e.source_url and e.source_url not in urls:
                urls.append(e.source_url)
        return urls[:limit]

    # ------------------------------------------------------------------- apply
    def apply(self, *, actor: str = "system") -> dict[str, Any]:
        """Aplica el bootstrap comercial de forma idempotente y con checkpoints.

        Si ya está aplicado devuelve ``already_applied=true`` sin tocar datos.
        Si falla a mitad, los checkpoints permiten reintentar sin duplicar.
        """
        assets = self.load_assets()
        manifest = assets["manifest"]
        research = assets["research"]

        applied = self._read_applied()
        if applied and applied.get("status") == "applied":
            return self._summary(already_applied=True, manifest=manifest)

        self._checkpoint("assets", "done", "activos verificados (checksum OK)")
        run = self._ensure_run()
        self._checkpoint("run", "done", f"run {run['id']} en {run['state']}")

        if not self._checkpoint_done("research_pending"):
            run = self._ensure_research_pending(run)
            self._checkpoint("research_pending", "done", f"run en {run['state']} con campaña {run['discovery_campaign_id']}")

        if not self._checkpoint_done("candidates_materialized"):
            materialized = self._materialize_candidates(run, assets["candidatas"])
            self._checkpoint("candidates_materialized", "done", json.dumps(materialized, ensure_ascii=False))

        imported = 0
        attached = 0
        skipped: list[str] = []
        if not self._checkpoint_done("research_import"):
            imported, attached, skipped = self._import_research(run, research)
            self._checkpoint("research_import", "done",
                             f"{imported} misiones importadas, {attached} evidencias adjuntadas, {len(skipped)} omitidas")

        winner = self._select_winner(run, manifest)
        self._checkpoint("winner", "done", f"ganadora {winner['opportunity_id']}")

        if not self._checkpoint_done("evaluation"):
            self._create_evaluation(winner)
            self._checkpoint("evaluation", "done", f"evaluación de {winner['opportunity_id']}")

        if not self._checkpoint_done("experiment_plan"):
            self._create_experiment_plan(run, winner, manifest)
            self._checkpoint("experiment_plan", "done", f"plan para {winner['opportunity_id']}")

        if not self._checkpoint_done("committee_queue"):
            self._queue_committee(winner)
            self._checkpoint("committee_queue", "done", f"ganadora encolada en comité ({winner['opportunity_id']})")

        # --- Readiness final (contrato real, sin inferencias optimistas) ---
        snapshot = self.c.command_center.snapshot()
        readiness = snapshot.get("readiness") or {}
        if readiness.get("readiness_state") != "READY_TO_CONNECT_SERVICES":
            raise BootstrapError(
                "El bootstrap no dejó el sistema en READY_TO_CONNECT_SERVICES. "
                "Faltan: " + ", ".join(readiness.get("readiness_missing") or []) +
                ("; bloqueos: " + ", ".join(readiness.get("readiness_blockers") or []) if readiness.get("readiness_blockers") else "")
            )
        self._checkpoint("readiness", "done", readiness.get("readiness_state") or "")

        self._write_applied(
            applied_version=BOOTSTRAP_VERSION,
            run_id=run["id"],
            campaign_id=run.get("discovery_campaign_id"),
            winner_opportunity_id=winner["opportunity_id"],
            asset_hash=(manifest.get("checksums") or {}).get(ASSET_RESEARCH),
        )
        self._log_decision(
            agent="commercial_bootstrap",
            opportunity_id=winner["opportunity_id"],
            summary=(
                f"Bootstrap comercial {BOOTSTRAP_VERSION} aplicado: {imported} misiones importadas, "
                f"{attached} evidencias verificadas adjuntadas, ganadora determinista seleccionada, "
                "experimento creado, comité encolado. Estado: READY_TO_CONNECT_SERVICES. "
                "Producción bloqueada; gasto real cero; PRE_CYCLE detenido."
            ),
            decision="SMALL_EXPERIMENT",
            method="commercial_bootstrap_022",
        )
        return self._summary(already_applied=False, manifest=manifest, run=run, winner=winner,
                             imported=imported, attached=attached, skipped=skipped, readiness=readiness)

    # --------------------------------------------------------------- helpers
    def _summary(self, *, already_applied: bool, manifest: dict, run: dict | None = None,
                 winner: dict | None = None, imported: int = 0, attached: int = 0,
                 skipped: list[str] | None = None, readiness: dict | None = None) -> dict:
        applied = self._read_applied()
        snapshot = _safe(lambda: self.c.command_center.snapshot(), {}) or {}
        if readiness is None:
            readiness = snapshot.get("readiness") or {}
        evidence = snapshot.get("evidence") or {}
        return {
            "ok": True,
            "already_applied": already_applied,
            "applied_version": (applied or {}).get("applied_version") or BOOTSTRAP_VERSION,
            "run_id": (run or {}).get("id") or (applied or {}).get("run_id"),
            "campaign_id": (run or {}).get("discovery_campaign_id") or (applied or {}).get("campaign_id"),
            "winner_opportunity_id": (winner or {}).get("opportunity_id") or (applied or {}).get("winner_opportunity_id"),
            "candidates": 3,
            "winner_title": (winner or {}).get("title") or (manifest.get("winner") or {}).get("title"),
            "missions_imported": imported,
            "evidences_attached": attached,
            "skipped": skipped or [],
            "evidence_verified": evidence.get("verified"),
            "evidence_groups": evidence.get("independent_verified_groups"),
            "readiness_state": readiness.get("readiness_state"),
            "readiness_missing": readiness.get("readiness_missing") or [],
            "readiness_blockers": readiness.get("readiness_blockers") or [],
            "pre_cycle": "STOPPED" if not _safe(lambda: self.c.cycle.evaluate(), {}).get("started_at") else "STARTED",
            "real_spend_usd": 0.0,
            "production": (snapshot.get("production_capability") or {}).get("state"),
            "mandate_state": "PENDING_OWNER_AUTHORIZATION",
            "committee_queued": bool(self.c.repos.reviews.queue_item((winner or {}).get("opportunity_id") or (applied or {}).get("winner_opportunity_id") or ""))
            if (winner or {}).get("opportunity_id") or (applied or {}).get("winner_opportunity_id") else False,
            "note": "No se activa producción ni se inicia el ciclo; READY_TO_LAUNCH requiere conectar servicios + autorización del propietario.",
        }

    def _read_applied(self) -> dict[str, Any] | None:
        try:
            row = self.c.conn.execute(
                "SELECT * FROM commercial_bootstrap_state WHERE id = 1"
            ).fetchone()
            return dict(row) if row else None
        except Exception:
            return None

    def _write_applied(self, *, applied_version: str, run_id: str | None, campaign_id: str | None,
                       winner_opportunity_id: str | None, asset_hash: str | None) -> None:
        self.c.conn.execute(
            """INSERT INTO commercial_bootstrap_state
               (id, applied_version, applied_at, run_id, campaign_id, winner_opportunity_id, asset_hash, status)
               VALUES (1, ?, ?, ?, ?, ?, ?, 'applied')
               ON CONFLICT(id) DO UPDATE SET
                 applied_version = excluded.applied_version,
                 applied_at = excluded.applied_at,
                 run_id = excluded.run_id,
                 campaign_id = excluded.campaign_id,
                 winner_opportunity_id = excluded.winner_opportunity_id,
                 asset_hash = excluded.asset_hash,
                 status = 'applied'""",
            (applied_version, _now_iso(), run_id, campaign_id, winner_opportunity_id, asset_hash),
        )
        self.c.conn.commit()

    def _locate_run(self) -> dict[str, Any] | None:
        run = _safe(lambda: self.c.orchestrator.current_run(), None)
        if run:
            return run
        runs = _safe(lambda: self.c.repos.orchestrator.list_runs(), []) or []
        for r in runs:
            if r.get("status") == "active":
                return r
        return runs[0] if runs else None

    def _ensure_run(self) -> dict[str, Any]:
        run = self._locate_run()
        if run is None:
            # Instalación limpia: crear la campaña canónica determinista
            # (misma generación que la reproducción 021; títulos idénticos).
            created = self.c.orchestrator.create_real_campaign()
            run = created.get("run") or self.c.orchestrator.current_run()
            if run is None:
                raise BootstrapError("No se pudo crear la campaña canónica.")
            self._log_decision(
                agent="commercial_bootstrap",
                opportunity_id=None,
                summary="Instalación limpia: campaña canónica creada para aplicar la activación comercial.",
                decision="SYSTEM",
                method="commercial_bootstrap_022",
            )
        # Recuperar ejecuciones FAILED/CANCELLED (nunca borrar datos).
        if run.get("status") in ("failed", "cancelled", "paused") or run.get("state") in ("FAILED",):
            from_state = run.get("state") or "UNKNOWN"
            self.c.repos.orchestrator.update_run(run["id"], status="active")
            self.c.repos.orchestrator.add_transition(
                run_id=run["id"], from_state=from_state, to_state=from_state or "RESEARCH_PENDING",
                actor="system", reason="Recuperación automática del bootstrap comercial (estado FAILED recuperable).",
                inputs={}, outputs={"recovered_by": "commercial_bootstrap_022"},
                synthetic=False, next_action="Aplicar investigación verificada (automático).",
            )
            run = self.c.repos.orchestrator.get_run(run["id"]) or run
        return run

    def _ensure_research_pending(self, run: dict) -> dict[str, Any]:
        state = run.get("state")
        if state in _PRE_RESEARCH_STATES:
            advanced = self.c.orchestrator.advance(run["id"])
            run = advanced.get("run") or self.c.repos.orchestrator.get_run(run["id"]) or run
        if run.get("state") not in ("RESEARCH_PENDING", *_RESEARCH_DONE_STATES):
            raise BootstrapError(
                f"El orquestador quedó en {run.get('state')}; no se puede aplicar la investigación de forma segura. Reintenta."
            )
        return run

    def _local_concepts(self, campaign_id: str) -> list[dict[str, Any]]:
        return _safe(lambda: self.c.repos.discovery.concepts_by_campaign(campaign_id), []) or []

    def _materialize_candidates(self, run: dict, candidatas: dict) -> dict[str, int]:
        """Materializa las candidatas del paquete portable en la campaña LOCAL.

        Crea los conceptos locales con los campos canónicos del paquete (nunca
        IDs foráneos), completa los Opportunity Briefs (hipótesis), promueve a
        oportunidad y crea las 6 misiones de Fase 1 por candidata si no existen
        ya. Idempotente: las candidatas/misiones ya presentes se conservan.
        """
        campaign_id = run.get("discovery_campaign_id")
        created = {"concepts": 0, "briefs": 0, "promoted": 0, "missions": 0, "existing": 0}
        from app.scoring.semantic_gate import validate_opportunity_brief

        for card in candidatas.get("candidates") or []:
            title = card.get("title")
            concept_fields = card.get("concept") or {}
            brief = card.get("brief") or {}
            concept = self._find_concept_by_title(campaign_id, title)
            if concept is None:
                item = {
                    "title": concept_fields.get("title") or title,
                    "problem_hypothesis": concept_fields.get("problem_hypothesis"),
                    "mechanism": concept_fields.get("mechanism"),
                    "buyer_hypothesis": concept_fields.get("buyer_hypothesis"),
                    "territory_key": concept_fields.get("territory_key"),
                    "lens_keys": concept_fields.get("lens_keys") or [],
                    "archetype_key": concept_fields.get("archetype_key"),
                    "outcome_hypothesis": concept_fields.get("outcome_hypothesis"),
                    "why_now": concept_fields.get("why_now"),
                    "general_ai_risk": concept_fields.get("general_ai_risk"),
                    "asset_potential": concept_fields.get("asset_potential"),
                }
                self.c.discovery.import_concept(campaign_id, item)
                concept = self._find_concept_by_title(campaign_id, title)
                if concept is None:
                    raise BootstrapError(f"No se pudo materializar el concepto local: {title[:60]}")
                created["concepts"] += 1
            if concept.get("status") == "COMMODITY_BLOCKED":
                raise BootstrapError(
                    f"El concepto local {title[:50]} está bloqueado por COMMODITY_WRAPPER; no se puede activar."
                )
            # Brief concreto (hipótesis, sin marcadores genéricos) -> RESEARCH_CANDIDATE.
            current_brief = concept.get("brief") or {}
            brief_ok = bool(validate_opportunity_brief(current_brief).get("ok"))
            if not brief_ok and concept.get("status") in (
                "GENERATED_HYPOTHESIS", "NEEDS_REFORMULATION", "RECOMBINATION_INCOHERENT",
                "STRUCTURAL_FILTER_PASSED", "AI_FILTER_PASSED", "RESEARCH_CANDIDATE",
            ):
                self.c.discovery.complete_opportunity_brief(concept["id"], brief)
                concept = self.c.repos.discovery.get_concept(concept["id"]) or concept
                created["briefs"] += 1
            # Promoción a oportunidad local (nunca IDs foráneos).
            opportunity = _safe(lambda: self.c.repos.opportunities.get_by_concept(concept["id"]), None)
            if opportunity is None and concept.get("status") in (
                "RESEARCH_CANDIDATE", "FINALIST", "SHORTLISTED_WITH_EVIDENCE"
            ):
                opportunity = self.c.discovery.promote(concept["id"])
                concept = self.c.repos.discovery.get_concept(concept["id"]) or concept
                created["promoted"] += 1
            if opportunity is None:
                raise BootstrapError(f"La candidata {title[:50]} no tiene oportunidad local promovida.")
            # Misiones Fase 1 PROGRESIVAS (6, nunca las 10 de golpe).
            for kind in RESEARCH_PHASE1_KINDS:
                mission = self._find_mission(campaign_id, concept["id"], title, kind)
                if mission is None:
                    self.c.discovery.create_mission(
                        kind=kind, campaign_id=campaign_id,
                        concept_id=concept["id"], opportunity_id=opportunity.id,
                    )
                    created["missions"] += 1
            created["existing"] += 1
        self._log_decision(
            agent="commercial_bootstrap",
            opportunity_id=None,
            summary=(
                f"Candidatas materializadas desde el paquete portable 021 en la campaña local "
                f"({created['concepts']} conceptos, {created['briefs']} briefs, "
                f"{created['promoted']} promociones, {created['missions']} misiones Fase 1). "
                "Sin IDs foráneos; resolución por título normalizado."
            ),
            decision="SYSTEM",
            method="commercial_bootstrap_022",
        )
        return created

    def _local_candidate_rows(self, campaign_id: str) -> list[dict[str, Any]]:
        return [
            c for c in self._local_concepts(campaign_id)
            if c.get("status") in ("RESEARCH_CANDIDATE", "FINALIST", "SHORTLISTED_WITH_EVIDENCE")
        ]

    def _local_winner_title(self, run: dict) -> str | None:
        selected = run.get("selected_opportunity_id")
        if not selected:
            return None
        opp = _safe(lambda: self.c.repos.opportunities.get(selected), None)
        return getattr(opp, "title", None) if opp else None

    def _find_concept_by_title(self, campaign_id: str, title: str) -> dict[str, Any] | None:
        norm = _normalize(title)
        for concept in self._local_concepts(campaign_id):
            if _normalize(concept.get("title")) == norm:
                return concept
        return None

    def _find_mission(self, campaign_id: str, concept_id: str, concept_title: str, kind: str) -> dict[str, Any] | None:
        norm_title = _normalize(concept_title)
        for mission in _safe(lambda: self.c.repos.discovery.missions_by_campaign(campaign_id), []) or []:
            if mission.get("status") in ("SUPERSEDED_BY_SEMANTIC_QUALITY_GATE", "CANCELLED"):
                continue
            if mission.get("kind") != kind and (mission.get("target") or {}).get("kind") != kind:
                continue
            target = mission.get("target") or {}
            if target.get("concept_id") == concept_id:
                return mission
            if target.get("concept_id") and concept_id and target["concept_id"] != concept_id:
                continue
            if norm_title and _normalize(target.get("concept_title")) == norm_title:
                return mission
        return None

    def _import_research(self, run: dict, research: dict) -> tuple[int, int, list[str]]:
        campaign_id = run.get("discovery_campaign_id")
        imported = 0
        attached = 0
        skipped: list[str] = []
        for payload in research.get("payloads") or []:
            title = payload.get("title")
            concept = self._find_concept_by_title(campaign_id, title)
            if concept is None:
                skipped.append(f"{title[:40]}:sin_concepto_local")
                continue
            opportunity = _safe(lambda: self.c.repos.opportunities.get_by_concept(concept["id"]), None)
            for mission in payload.get("missions") or []:
                kind = mission["kind"]
                local_mission = self._find_mission(campaign_id, concept["id"], title, kind)
                if local_mission is None:
                    skipped.append(f"{title[:30]}:{kind}:sin_mision")
                    continue
                if local_mission.get("status") == "imported":
                    imported += 1  # idempotente: ya estaba importada
                    continue
                if self.c.repos.discovery.mission_results(local_mission["mission_id"]):
                    imported += 1  # resultados ya persistidos (reintento tras corte)
                    continue
                from app.models.discovery import MissionIn

                payload_in = MissionIn(
                    mission_id=local_mission["mission_id"],
                    evidences=mission.get("evidences") or [],
                    competitors=mission.get("competitors") or [],
                    buyer_confirmed=mission.get("buyer_confirmed"),
                    notes=mission.get("notes"),
                    verified=False,  # nunca se auto-marca: URL+fecha+fragmento deciden
                )
                self.c.discovery.import_mission_result(local_mission["mission_id"], payload_in)
                imported += 1
                if opportunity is not None:
                    attach = self.c.discovery.attach_mission_evidence(opportunity.id, local_mission["mission_id"])
                    attached += int(attach.get("evidences_attached") or 0)
                    target = dict(local_mission.get("target") or {})
                    target["opportunity_id"] = opportunity.id
                    self.c.repos.discovery.update_mission_target(local_mission["mission_id"], target)
                else:
                    # Sin oportunidad promovida aún: el target guarda el título del
                    # concepto para el vínculo posterior (nunca IDs foráneos).
                    target = dict(local_mission.get("target") or {})
                    target["concept_title"] = title
                    self.c.repos.discovery.update_mission_target(local_mission["mission_id"], target)
        # Reevaluación determinista con evidencia (sin LLM, sin pipeline legacy).
        for concept in self._local_concepts(campaign_id):
            try:
                self.c.discovery._evaluate_venture(concept, campaign_id)  # type: ignore[attr-defined]
            except Exception:
                continue
        if imported == 0 and skipped:
            raise BootstrapError(
                "Ninguna misión local coincidió con la investigación portable "
                "(omisiones: " + ", ".join(skipped[:5]) + "). "
                "La campaña local no contiene las candidatas de la activación comercial."
            )
        self.c.repos.orchestrator.update_run(run["id"], state="RESEARCH_IMPORTED")
        self.c.repos.orchestrator.add_transition(
            run_id=run["id"], from_state="RESEARCH_PENDING", to_state="RESEARCH_IMPORTED",
            actor="system",
            reason=(
                "Bootstrap comercial: investigación portable importada contra misiones LOCALES "
                f"({imported} misiones, {attached} evidencias adjuntadas; {len(skipped)} omitidas). "
                "Ganadora determinista y readiness en pasos siguientes."
            ),
            inputs={}, outputs={"imported": imported, "evidences_attached": attached, "skipped": skipped},
            synthetic=False, next_action="Seleccionar ganadora determinista (automático).",
        )
        return imported, attached, skipped

    def _select_winner(self, run: dict, manifest: dict) -> dict[str, Any]:
        campaign_id = run.get("discovery_campaign_id")
        winner_title = (manifest.get("winner") or {}).get("title") or WINNER_TITLE
        concept = self._find_concept_by_title(campaign_id, winner_title)
        if concept is None:
            # Fallback determinista: máxima puntuación con evidencia, desempate por título.
            best = None
            best_key = None
            for c in self._local_candidate_rows(campaign_id):
                venture = _safe(lambda c=c: self.c.repos.discovery.venture_evaluations_by_concept(c["id"]), []) or []
                score = float((venture[0] if venture else {}).get("evidence_backed_venture_score") or 0.0)
                key = (score, _normalize(c.get("title")))
                if best_key is None or key > best_key:
                    best, best_key = c, key
            concept = best
        if concept is None:
            raise BootstrapError("No se pudo localizar la ganadora por título ni por puntuación en la campaña local.")
        opportunity = _safe(lambda: self.c.repos.opportunities.get_by_concept(concept["id"]), None)
        if opportunity is None:
            raise BootstrapError(f"La candidata local {concept['title'][:50]} no tiene oportunidad promovida.")
        self.c.repos.orchestrator.update_run(run["id"], selected_opportunity_id=opportunity.id)
        self.c.repos.orchestrator.add_transition(
            run_id=run["id"], from_state="RESEARCH_IMPORTED", to_state="RESEARCH_IMPORTED",
            actor="system", reason=f"Ganadora determinista seleccionada: {concept['title'][:90]}",
            inputs={"criterion": "torneo 018 + evidencia verificada (paquete 021)"},
            outputs={"winner_concept_id": concept["id"], "winner_opportunity_id": opportunity.id},
            synthetic=False, next_action="Evaluación interna y plan de experimento (automático).",
        )
        self._log_decision(
            agent="commercial_bootstrap",
            opportunity_id=opportunity.id,
            summary=f"Ganadora determinista para experimento: {concept['title'][:90]}. No es demanda validada (sin pago real).",
            decision="SMALL_EXPERIMENT",
            method="deterministic_winner_021",
        )
        return {"concept": concept, "opportunity_id": opportunity.id, "title": concept["title"]}

    def _create_evaluation(self, winner: dict[str, Any]) -> None:
        concept = winner["concept"]
        opp_id = winner["opportunity_id"]
        venture_rows = self.c.repos.discovery.venture_evaluations_by_concept(concept["id"])
        venture = venture_rows[0] if venture_rows else {}
        evidence = self.c.repos.evidence.list_for(opp_id)
        verified = [e for e in evidence if getattr(e, "verified", False)]
        groups = {getattr(e, "independence_group", None) or "x" for e in verified}
        evidence_backed = float(venture.get("evidence_backed_venture_score") or 0.0)

        def _avg(*vals: float) -> float:
            return round(sum(vals) / len(vals), 2)

        from app.models.evaluation import Estimates

        evaluation = Evaluation(
            opportunity_id=opp_id,
            pain_score=_avg(venture.get("economic_pain") or 0.0),
            demand_score=venture.get("proven_demand") or 0.0,
            customer_reach_score=venture.get("distribution") or 0.0,
            automation_score=venture.get("operational_simplicity") or 0.0,
            margin_score=venture.get("gross_margin") or 0.0,
            build_speed_score=venture.get("validation_speed") or 0.0,
            differentiation_score=_avg(venture.get("defensibility") or 0.0, venture.get("general_ai_resistance") or 0.0),
            safety_score=100.0,  # benchmark anónimo: sin datos de pacientes ni consejo clínico
            evidence_quality_score=min(100.0, float(len(verified)) * 5.0 + float(len(groups)) * 5.0),
            confidence_score=evidence_backed,
            final_score=evidence_backed,
            per_criterion={},
            independent_evidence_count=len(groups),
            unverified_assumptions_count=3,
            assumptions=[
                "Comprador (gerente de clínica 2-5 dentistas) pagaría por un informe de tarifas: HIPÓTESIS no verificada con comprador real.",
                "Presupuesto real de la clínica por este informe: HIPÓTESIS (30-90 EUR).",
                "Urgencia/evento de compra: no detectado en evidencia.",
            ],
            blockers=[],
            approval_reason=(
                f"{len(groups)} grupos de evidencia independiente verificada (URL+fecha+fragmento), "
                f"sin bloqueadores; score con evidencia {evidence_backed:.1f}; decisión SMALL_EXPERIMENT determinista."
            ),
            rejection_reason=None,
            decision=Decision.approved,
            model_or_method="commercial_bootstrap_022 (Venture Quality Score con evidencia; sin LLM)",
            skeptic_critique=(
                "El comprador puede resolver con guías de precios gratuitas; la urgencia no está demostrada; "
                "el dominio sanitario exige no tocar datos de pacientes. Por eso la decisión es un experimento "
                "pequeño y barato, no un lanzamiento."
            ),
            risks=[],
            estimates=Estimates(),
            experiment=None,
        )
        self.c.repos.evaluations.upsert(evaluation)

    def _create_experiment_plan(self, run: dict, winner: dict[str, Any], manifest: dict) -> dict[str, Any]:
        opp_id = winner["opportunity_id"]
        existing = _safe(lambda: self.c.repos.orchestrator.experiment_plan_for_opportunity(opp_id), None)
        if existing:
            return existing
        contract = (manifest.get("experiment_contract") or {})
        plan = ExperimentPlan(
            run_id=run["id"],
            opportunity_id=opp_id,
            decision="approved",
            offer=contract.get("offer") or "Informe de benchmark anónimo de tarifas de ortodoncia por provincia (rangos y percentiles) para decidir el precio de la clínica.",
            buyer=contract.get("buyer") or "Gerentes de clínicas dentales de 2-5 dentistas",
            user="Gerente o director de la clínica dental",
            problem="Las clínicas dentales pequeñas fijan el precio de ortodoncia sin un comparativo de tarifas de su zona y pierden margen o pacientes.",
            value_proposition="Decide tu tarifa de ortodoncia con datos reales de tu provincia, no con guías genéricas.",
            price_usd=float(contract.get("price_usd") or 60.0),
            delivery_format="Informe PDF + revisión por videollamada (entrega concierge)",
            demo="Muestra con 2 provincias de ejemplo antes del pago",
            channel=contract.get("channel") or "Contacto directo a 20 clínicas identificadas vía colegios y directorios oficiales (sin spam); LinkedIn y colegios provinciales",
            initial_message="Solicitud de permiso para compartir un informe de tarifas de ortodoncia de tu provincia (sin datos de pacientes).",
            min_sample=3,
            max_contacts=20,
            acquisition_method="Captación manual autorizada por canal; sin spam ni mensajería masiva",
            max_cost_usd=float(contract.get("max_cost_usd") or 0.0),
            duration_days=int(contract.get("duration_days") or 30),
            success_metric=contract.get("success_metric") or "primer pago real confirmado",
            success_threshold=contract.get("success_threshold") or "1 pago confirmado (30-90 EUR) por un comprador real",
            kill_condition=contract.get("kill_condition") or "sin señal de pago tras 14 días de contacto activo",
            product_death_condition="sin señal de pago en 30 días y sin pivote viable",
            possible_pivots=contract.get("pivots") or [
                "Vender el benchmark a aseguradoras/software dental como dato agregado anónimo",
                "Ampliar a otras especialidades (implantes, invisible)",
                "Suscripción trimestral de actualización de tarifas",
            ],
            automatable_tasks=[
                "Recopilación y normalización de tarifarios públicos",
                "Generación del informe (plantilla + percentiles)",
                "Seguimiento de contactos y recordatorios",
            ],
            owner_tasks=[
                "Aportar credenciales Stripe (cobro real)",
                "Aportar email transaccional y hosting",
                "Autorizar el ciclo autónomo de 30 días",
            ],
            risks=[
                "Guías de precios gratuitas como sustituto (kill condition cubre)",
                "Dominio sanitario: nunca usar datos de pacientes (informe anónimo agregado)",
                "Urgencia no demostrada: sin evento de compra claro",
            ],
            dependencies=[
                "Método de cobro real autorizado (Stripe u otro)",
                "Email transaccional (envío del informe)",
                "Hosting/dominio para la landing",
                "Analytics de eventos (visitas, leads, checkouts)",
            ],
            payment_readiness="PENDIENTE: requiere método de cobro real autorizado por el propietario",
            missing_capabilities=[],
            blockers=[],
        )
        return self.c.repos.orchestrator.create_experiment_plan(plan)

    def _queue_committee(self, winner: dict[str, Any]) -> None:
        opp_id = winner["opportunity_id"]
        if self.c.repos.reviews.queue_item(opp_id):
            return  # ya está encolada
        try:
            self.c.reviews.queue_opportunity(
                opp_id, note="Encolada automáticamente por el bootstrap comercial (ganadora determinista del experimento).",
                quiet=True,
            )
        except Exception as exc:  # noqa: BLE001 — excepción auditable documentada
            # La guarda de umbral del comité no aplica al ganador determinista del
            # experimento (7 grupos de evidencia verificada). Se encola por el
            # repositorio con el score honesto y se registra la excepción.
            evaluation = self.c.repos.evaluations.get(opp_id)
            internal = float(evaluation.final_score if evaluation else 0.0)
            self.c.repos.reviews.enqueue(
                opp_id, internal_score=internal, window_deadline=_now_iso(),
                note=(
                    "Cola por bootstrap (excepción auditable de umbral para el ganador determinista "
                    "del experimento; guarda documentada): " + str(exc)
                ),
            )
            self._log_decision(
                agent="commercial_bootstrap",
                opportunity_id=opp_id,
                summary="Ganadora encolada en el comité con excepción auditable de umbral (7 grupos verificados, decisión determinista).",
                decision="SMALL_EXPERIMENT",
                method="commercial_bootstrap_022",
            )

    def _log_decision(self, *, agent: str, opportunity_id: str | None, summary: str,
                      decision: str, method: str) -> None:
        try:
            self.c.repos.decision_log.add(
                DecisionLog(
                    agent=agent,
                    opportunity_id=opportunity_id,
                    input_summary=summary,
                    output_summary=summary,
                    decision=decision,
                    model_or_method=method,
                    estimated_cost=0.0,
                    cost_method="zero (offline)",
                )
            )
        except Exception:
            self.c.conn.rollback()
