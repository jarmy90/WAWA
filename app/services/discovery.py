"""Business Discovery Engine (iteración 004).

Implementa la Ruta B (open opportunity discovery): campañas que generan,
filtran, recombinan, comparan y seleccionan conceptos SIN que el usuario deba
proponer un negocio. Todo es determinista en offline: los conceptos son
HIPÓTESIS sin verificar, el General AI Substitution Test bloquea wrappers de
IA generalista, y la demanda nunca se inventa (proven_demand=0 hasta que una
misión de investigación aporte evidencia con URL, fecha y fragmento).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationError
from app.core.libraries import get_archetype, get_lens, get_territory
from app.models.decision_log import DecisionLog
from app.models.discovery import (
    MissionExport,
    MissionIn,
    new_id,
)
from app.models.enums import AgentName, OpportunityStatus
from app.models.opportunity import Opportunity
from app.repositories import Repos
from app.scoring.venture import (
    concept_fingerprint,
    derive_substitution_answers,
    diversity_metric,
    estimate_venture_scores,
    is_conceptual_clone,
    run_substitution_test,
    venture_score,
)

PHASES = ("created", "phase1", "phase2", "phase3", "shortlist", "tournament", "finalists", "done")


def _normalize_key(text: str) -> str:
    """Normaliza un título para deduplicación (acentos, mayúsculas, signos)."""
    import re
    import unicodedata

    t = unicodedata.normalize("NFKD", str(text).lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()

MISSION_KINDS = (
    "campaign", "signal", "candidate", "tournament", "competitors", "buyer", "substitution", "equivalents",
    "DEMAND_REALITY_CHECK", "BUYER_BUDGET_CHECK", "CURRENT_ALTERNATIVE_CHECK", "GENERAL_AI_SUBSTITUTION_CHECK",
    "COMPETITOR_EQUIVALENT_SEARCH", "DISTRIBUTION_ACCESS_CHECK", "MOAT_REALITY_CHECK", "DATA_AVAILABILITY_CHECK",
    "TOS_AND_LEGAL_CHECK", "EXPERIMENT_FEASIBILITY_CHECK",
)

# Campos que una evidencia DEBE traer para poder marcarse verified (regla de
# no auto-verificación: Freebuff u otra fuente no basta por sí misma).
VERIFIED_REQUIRED_FIELDS = ("source_url", "captured_at", "summary")


class DiscoveryService:
    def __init__(self, settings: Settings, repos: Repos, providers, opportunities) -> None:
        self.settings = settings
        self.repos = repos
        self.providers = providers
        self.opportunities = opportunities

    # ------------------------------------------------------------------
    # Campañas
    # ------------------------------------------------------------------
    def create_campaign(self, data: dict[str, Any]) -> dict[str, Any]:
        territories = self._resolve_keys(data.get("territory_keys") or [], "territorio")
        lenses = self._resolve_keys(data.get("lens_keys") or [], "lente")
        archetypes = self._resolve_keys(data.get("archetype_keys") or [], "arquetipo")
        campaign = self.repos.discovery.create_campaign(
            {
                "title": data["title"],
                "territory_keys": territories,
                "lens_keys": lenses,
                "archetype_keys": archetypes,
                "phase1_target": data.get("phase1_target", 60),
                "shortlist_target": data.get("shortlist_target", 10),
                "finalists_target": data.get("finalists_target", 3),
            }
        )
        self._log("discovery.campaign", f"Campaña creada: {campaign['title']} (fase 1 objetivo: {campaign['phase1_target']})", model="rules")
        return campaign

    def _resolve_keys(self, keys: list[str], kind: str) -> list[str]:
        from app.core import libraries

        valid = {
            "territorio": set(libraries.territory_keys()),
            "lente": set(libraries.lens_keys()),
            "arquetipo": set(libraries.archetype_keys()),
        }[kind]
        unknown = [k for k in keys if k not in valid]
        if unknown:
            raise ValidationError(f"Claves de {kind} desconocidas: {', '.join(unknown)}")
        return list(keys)  # vacío = todos (se resuelve en la generación)

    def get_campaign(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.repos.discovery.get_campaign(campaign_id)
        if campaign is None:
            raise NotFoundError("Campaña no encontrada.")
        return campaign

    def list_campaigns(self) -> list[dict[str, Any]]:
        return self.repos.discovery.list_campaigns()

    def campaign_detail(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.get_campaign(campaign_id)
        concepts = self.repos.discovery.concepts_by_campaign(campaign_id)
        for concept in concepts:
            tests = self.repos.discovery.substitution_tests_by_concept(concept["id"])
            evals = self.repos.discovery.venture_evaluations_by_concept(concept["id"])
            concept["substitution"] = tests[0] if tests else None
            concept["venture"] = evals[0] if evals else None
        return {
            "campaign": campaign,
            "concepts": concepts,
            "comparisons": self.repos.discovery.comparisons_by_campaign(campaign_id),
            "diversity": campaign.get("diversity", 0.0),
        }

    # ------------------------------------------------------------------
    # FASE 1: exploración amplia (50-100 conceptos breves)
    # ------------------------------------------------------------------
    def run_phase1(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.get_campaign(campaign_id)
        config = {
            "territories": campaign["territory_keys"],
            "lenses": campaign["lens_keys"],
            "archetypes": campaign["archetype_keys"],
            "target": campaign["phase1_target"],
        }
        call = self.providers.generate(
            "Genera conceptos de negocio breves (hipótesis, no ideas finales).",
            system=json.dumps(config, ensure_ascii=False),
            task="discover_phase1",
            action="discovery_phase1",
            opportunity_id=campaign_id,
        )
        raw = (call.response.structured or {}).get("concepts", [])
        if not isinstance(raw, list) or not raw:
            raise ValidationError("El proveedor no devolvió conceptos (offline: comprueba el modo de generación).")

        created: list[dict[str, Any]] = []
        for item in raw[: campaign["phase1_target"]]:
            concept = self._save_concept(campaign_id, item, phase="phase1", source="generated")
            created.append(concept)
        self._update_campaign_diversity(campaign_id)
        self._log("discovery.phase1", f"Fase 1 completada: {len(created)} conceptos generados (campaña {campaign_id}).", model=call.provider)
        return self.campaign_detail(campaign_id)

    def _save_concept(self, campaign_id: str, item: dict[str, Any], *, phase: str, source: str) -> dict[str, Any]:
        concept = {
            "campaign_id": campaign_id,
            "title": str(item.get("title") or "").strip()[:300],
            "territory_key": item.get("territory_key"),
            "lens_keys": list(item.get("lens_keys") or []),
            "archetype_key": item.get("archetype_key"),
            "problem_hypothesis": str(item.get("problem_hypothesis") or "").strip(),
            "mechanism": str(item.get("mechanism") or "").strip(),
            "buyer_hypothesis": (item.get("buyer_hypothesis") or "").strip() or None,
            "outcome_hypothesis": (item.get("outcome_hypothesis") or "").strip() or None,
            "why_now": (item.get("why_now") or "").strip() or None,
            "general_ai_risk": (item.get("general_ai_risk") or "").strip() or None,
            "asset_potential": (item.get("asset_potential") or "").strip() or None,
            "phase": phase,
            "status": "draft",
            "source": source,
        }
        if not concept["title"] or not concept["problem_hypothesis"] or not concept["mechanism"]:
            raise ValidationError("Concepto inválido: faltan title/problem_hypothesis/mechanism.")
        concept["fingerprint"] = concept_fingerprint(concept)
        saved = self.repos.discovery.create_concept(concept)
        self._evaluate_substitution(saved)
        return saved

    def _update_campaign_diversity(self, campaign_id: str) -> None:
        concepts = self.repos.discovery.concepts_by_campaign(campaign_id)
        fps = [c["fingerprint"] for c in concepts]
        diversity = diversity_metric(fps)
        self.repos.discovery.update_campaign(campaign_id, diversity=diversity)

    def _evaluate_substitution(self, concept: dict[str, Any]) -> dict[str, Any]:
        answers = derive_substitution_answers(concept)
        test = run_substitution_test(answers)
        saved = self.repos.discovery.save_substitution_test(
            concept["id"], test.model_dump(mode="json")
        )
        if test.verdict == "blocked":
            self.repos.discovery.update_concept(concept["id"], status="blocked")
            self.repos.discovery.add_learning_record(
                kind="rejection",
                pattern="COMMODITY_WRAPPER: IA generalista resuelve el problema sin workflow, integración ni memoria.",
                source=f"substitution:{concept['id']}",
                notes=f"Concepto bloqueado: {concept['title']}",
            )
        return saved

    # ------------------------------------------------------------------
    # FASE 2: filtro de comoditización y obviedad
    # ------------------------------------------------------------------
    def _filter_blockers(self, concept: dict[str, Any]) -> list[str]:
        """Bloqueadores del filtro de comoditización/obviedad (fase 2)."""
        blockers: list[str] = []
        test = self.repos.discovery.substitution_tests_by_concept(concept["id"])
        if test and test[0]["verdict"] == "blocked":
            blockers.append("COMMODITY_WRAPPER")
        if not concept.get("buyer_hypothesis"):
            blockers.append("Sin comprador identificable.")
        if not concept.get("outcome_hypothesis"):
            blockers.append("Sin resultado medible.")
        mechanism = (concept.get("mechanism") or "").lower()
        if "póliza" in mechanism or "producto asegurador" in mechanism:
            blockers.append("Riesgo legal o de plataforma grave.")
        return blockers

    def run_commodity_filter(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.get_campaign(campaign_id)
        concepts = self.repos.discovery.concepts_by_campaign(campaign_id)
        blocked, passed = 0, 0
        for concept in concepts:
            if concept["status"] == "blocked":
                blocked += 1
                continue
            blockers = self._filter_blockers(concept)
            if blockers:
                self.repos.discovery.update_concept(concept["id"], status="blocked")
                for b in blockers:
                    self.repos.discovery.add_learning_record(
                        kind="rejection", pattern=b, source=f"filter:{concept['id']}", notes=concept["title"]
                    )
                blocked += 1
            else:
                self.repos.discovery.update_concept(concept["id"], status="passed")
                passed += 1
        self.repos.discovery.update_campaign(campaign_id, phase="phase2")
        self._log("discovery.phase2", f"Filtro de comoditización: {passed} pasan, {blocked} bloqueados (campaña {campaign_id}).", model="rules")
        return self.campaign_detail(campaign_id)

    # ------------------------------------------------------------------
    # FASE 3: recombinación de mecanismos
    # ------------------------------------------------------------------
    def run_recombine(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.get_campaign(campaign_id)
        passed = [c for c in self.repos.discovery.concepts_by_campaign(campaign_id) if c["status"] == "passed"]
        if len(passed) < 4:
            raise ValidationError("Se necesitan al menos 4 conceptos que pasen el filtro para recombinar.")
        call = self.providers.generate(
            "Recombina los mecanismos de los mejores conceptos en conceptos superiores.",
            system=json.dumps([{"id": c["id"], "title": c["title"], "territory_key": c["territory_key"], "mechanism": c["mechanism"]} for c in passed], ensure_ascii=False),
            task="discover_recombine",
            action="discovery_recombine",
            opportunity_id=campaign_id,
        )
        raw = (call.response.structured or {}).get("concepts", [])
        created = []
        for item in raw:
            concept = self._save_concept(campaign_id, item, phase="phase3", source="recombined")
            blockers = self._filter_blockers(concept)
            status = "blocked" if blockers else "passed"
            self.repos.discovery.update_concept(concept["id"], status=status)
            created.append(concept)
        self._update_campaign_diversity(campaign_id)
        self.repos.discovery.update_campaign(campaign_id, phase="phase3")
        self._log("discovery.phase3", f"Recombinación: {len(created)} conceptos recombinados (campaña {campaign_id}).", model=call.provider)
        return self.campaign_detail(campaign_id)

    # ------------------------------------------------------------------
    # FASE 4: shortlist con diversidad
    # ------------------------------------------------------------------
    def _evaluate_venture(self, concept: dict[str, Any], campaign_id: str) -> dict[str, Any]:
        test = self.repos.discovery.substitution_tests_by_concept(concept["id"])
        substitution = None
        if test:
            from app.models.discovery import SubstitutionTest

            substitution = SubstitutionTest(
                answers=test[0]["answers"],
                classification=test[0]["classification"],
                general_ai_resistance=test[0]["general_ai_resistance"],
                verdict=test[0]["verdict"],
                reasons=test[0]["reasons"],
            )
        scores = estimate_venture_scores(concept, substitution) if substitution else {}

        # Novelty: distancia respecto a los demás conceptos de la campaña.
        others = [c for c in self.repos.discovery.concepts_by_campaign(campaign_id) if c["id"] != concept["id"]]
        if others:
            # novelty = distancia máxima a cualquier otro concepto de la campaña
            max_dist = max(min(1.0, _fingerprint_distance(concept, o)) for o in others)
            novelty = round(100.0 * max_dist, 2)
        else:
            novelty = 70.0  # neutro: sin referencias previas
        outcome_clarity = 100.0 if concept.get("outcome_hypothesis") else 30.0
        buyer_defined = 100.0 if concept.get("buyer_hypothesis") else 0.0
        utility = round(0.45 * scores.get("economic_pain", 50) + 0.3 * outcome_clarity + 0.25 * buyer_defined, 2)

        blockers: list[str] = []
        if substitution and substitution.verdict == "blocked":
            blockers.append("COMMODITY_WRAPPER")
        if not concept.get("buyer_hypothesis"):
            blockers.append("Sin comprador identificable.")
        if not concept.get("outcome_hypothesis"):
            blockers.append("Sin resultado medible.")

        eval_scores = dict(scores)
        eval_scores["economic_pain"] = scores.get("economic_pain", 0.0)
        eval_scores["proven_demand"] = 0.0  # offline: sin evidencia de demanda (nunca se inventa)
        result = venture_score(scores=eval_scores, novelty_score=novelty, utility_score=utility, blockers=blockers)
        saved = self.repos.discovery.save_venture_evaluation(
            concept["id"],
            {
                "scores": result.model_dump(mode="json", exclude={"final_score", "novelty_score", "utility_score", "blockers", "labels", "rationale"}),
                "final_score": result.final_score,
                "novelty_score": result.novelty_score,
                "utility_score": result.utility_score,
                "blockers": result.blockers,
                "labels": result.labels,
                "rationale": result.rationale,
            },
        )
        return {**concept, "venture": saved}

    def run_shortlist(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.get_campaign(campaign_id)
        candidates = [c for c in self.repos.discovery.concepts_by_campaign(campaign_id) if c["status"] == "passed"]
        if not candidates:
            raise ValidationError("No hay conceptos que hayan pasado el filtro de comoditización.")
        evaluated = [self._evaluate_venture(c, campaign_id) for c in candidates]
        evaluated.sort(key=lambda c: c["venture"]["final_score"], reverse=True)

        target = campaign["shortlist_target"]
        shortlisted: list[dict[str, Any]] = []
        for candidate in evaluated:
            if len(shortlisted) >= target:
                break
            fp = concept_fingerprint(candidate)
            if any(is_conceptual_clone(fp, concept_fingerprint(s))[0] for s in shortlisted):
                self.repos.discovery.update_concept(candidate["id"], status="clone")
                continue
            self.repos.discovery.update_concept(candidate["id"], status="shortlisted")
            shortlisted.append(candidate)

        self.repos.discovery.update_campaign(campaign_id, phase="shortlist")
        self._log(
            "discovery.shortlist",
            f"Shortlist: {len(shortlisted)} de {len(evaluated)} candidatos (campaña {campaign_id}).",
            model="rules",
        )
        return self.campaign_detail(campaign_id)

    # ------------------------------------------------------------------
    # FASE 5: torneo por pares
    # ------------------------------------------------------------------
    TOURNAMENT_CRITERIA = (
        ("economic_pain", "mayor dolor económico"),
        ("general_ai_resistance", "menos sustituible por IA"),
        ("validation_speed", "se valida antes"),
        ("distribution", "mejor distribución"),
        ("defensibility", "crea activo acumulativo"),
        ("demonstrability", "se explica mejor"),
        ("gross_margin", "mayor potencial de margen"),
        ("recurrence", "merece el siguiente euro y la siguiente hora"),
    )

    def run_tournament(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.get_campaign(campaign_id)
        shortlisted: list[dict[str, Any]] = []
        for c in self.repos.discovery.concepts_by_campaign(campaign_id):
            if c["status"] != "shortlisted":
                continue
            evals = self.repos.discovery.venture_evaluations_by_concept(c["id"])
            if evals:
                c["venture"] = evals[0]
                shortlisted.append(c)
        if len(shortlisted) < 2:
            raise ValidationError("El torneo necesita al menos 2 finalistas del shortlist.")
        wins: dict[str, int] = {c["id"]: 0 for c in shortlisted}
        for i in range(len(shortlisted)):
            for j in range(i + 1, len(shortlisted)):
                a, b = shortlisted[i], shortlisted[j]
                winner, loser, criteria = self._pairwise(a, b)
                self.repos.discovery.save_comparison(
                    {
                        "campaign_id": campaign_id,
                        "winner_id": winner["id"],
                        "loser_id": loser["id"],
                        "winner_score": winner["venture"]["final_score"],
                        "loser_score": loser["venture"]["final_score"],
                        "criteria": criteria,
                    }
                )
                wins[winner["id"]] += 1
        ranked = sorted(shortlisted, key=lambda c: (wins[c["id"]], c["venture"]["final_score"]), reverse=True)
        finalists = ranked[: campaign["finalists_target"]]
        for c in ranked:
            status = "finalist" if c["id"] in {f["id"] for f in finalists} else "eliminated"
            self.repos.discovery.update_concept(c["id"], status=status)
        self.repos.discovery.update_campaign(campaign_id, phase="finalists")
        self._log(
            "discovery.tournament",
            f"Torneo completado: {len(finalists)} finalistas de {len(shortlisted)} (campaña {campaign_id}).",
            model="rules",
        )
        detail = self.campaign_detail(campaign_id)
        detail["ranking"] = [
            {"id": c["id"], "title": c["title"], "wins": wins[c["id"]], "final_score": c["venture"]["final_score"]}
            for c in ranked
        ]
        return detail

    def _pairwise(self, a: dict[str, Any], b: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        sa = a["venture"]["scores"]
        sb = b["venture"]["scores"]
        criteria: dict[str, Any] = {}
        wins_a = 0
        for key, label in self.TOURNAMENT_CRITERIA:
            va, vb = sa.get(key, 0.0), sb.get(key, 0.0)
            if va == vb:
                criteria[label] = "empate"
            elif va > vb:
                criteria[label] = a["title"]
                wins_a += 1
            else:
                criteria[label] = b["title"]
        if wins_a > len(self.TOURNAMENT_CRITERIA) / 2:
            return a, b, criteria
        if wins_a < len(self.TOURNAMENT_CRITERIA) / 2:
            return b, a, criteria
        # Desempate determinista por puntuación final.
        if a["venture"]["final_score"] >= b["venture"]["final_score"]:
            return a, b, criteria
        return b, a, criteria

    # ------------------------------------------------------------------
    # FASE 7: promoción a Opportunity
    # ------------------------------------------------------------------
    def promote(self, concept_id: str) -> Opportunity:
        concept = self.repos.discovery.get_concept(concept_id)
        if concept is None:
            raise NotFoundError("Concepto no encontrado.")
        if concept["status"] not in ("shortlisted", "finalist"):
            raise ValidationError("Solo se promueven conceptos del shortlist o finalistas.")
        territory = get_territory(concept["territory_key"] or "") if concept.get("territory_key") else None
        archetype = get_archetype(concept["archetype_key"] or "") if concept.get("archetype_key") else None
        sector = f"discovery: {territory.name if territory else 'sin territorio'} / {archetype.name if archetype else 'sin arquetipo'}"

        opportunity = Opportunity(
            title=concept["title"],
            problem=concept["problem_hypothesis"],
            proposed_solution=concept["mechanism"],
            target_customer=concept.get("buyer_hypothesis") or "DESCONOCIDO (pendiente de misión de investigación)",
            sector=sector,
            source=f"discovery:{concept['campaign_id']}",
            status=OpportunityStatus.draft,
        )
        self.repos.opportunities.create(opportunity)
        self.repos.decision_log.add(
            DecisionLog(
                agent=AgentName.system.value,
                opportunity_id=opportunity.id,
                input_summary=f"Promoción de concepto {concept_id} a oportunidad.",
                output_summary=f"Oportunidad creada desde discovery: {opportunity.title}",
                model_or_method="discovery.rules",
            )
        )
        self.repos.discovery.update_concept(concept_id, status="promoted")
        return opportunity

    # ------------------------------------------------------------------
    # Misiones de investigación Freebuff-first
    # ------------------------------------------------------------------
    def create_mission(self, *, kind: str, campaign_id: str | None = None, concept_id: str | None = None) -> MissionExport:
        if kind not in MISSION_KINDS:
            raise ValidationError(f"Tipo de misión desconocido: {kind}. Válidos: {', '.join(MISSION_KINDS)}.")
        if campaign_id is None and concept_id is None:
            raise ValidationError("Una misión necesita campaign_id o concept_id.")
        target: dict[str, Any] = {}
        if campaign_id:
            campaign = self.get_campaign(campaign_id)
            target["campaign_id"] = campaign_id
            target["campaign_title"] = campaign["title"]
        if concept_id:
            concept = self.repos.discovery.get_concept(concept_id)
            if concept is None:
                raise NotFoundError("Concepto no encontrado.")
            target["concept_id"] = concept_id
            target["concept_title"] = concept["title"]
            target["problem_hypothesis"] = concept["problem_hypothesis"]
            target["mechanism"] = concept["mechanism"]
            target["buyer_hypothesis"] = concept.get("buyer_hypothesis")
        mission = self._build_mission(kind, target)
        self.repos.discovery.save_mission(
            {
                "mission_id": mission.mission_id,
                "kind": kind,
                "target": mission.target,
                "export_payload": mission.model_dump(mode="json"),
            }
        )
        self._log("discovery.mission", f"Misión creada: {kind} ({mission.mission_id}).", model="manual")
        return mission

    def import_concept(self, campaign_id: str, item: dict[str, Any], *, source: str = "session") -> dict[str, Any] | None:
        """Importa un concepto de sesión Freebuff con deduplicación por título.

        Devuelve None si es duplicado (título normalizado ya existente en la
        campaña). Los conceptos se evalúan deterministamente (substitution +
        venture) como HIPÓTESIS, nunca como demanda verificada.
        """
        title = str(item.get("title") or "").strip()
        if not title:
            return None
        normalized = _normalize_key(title)
        for existing in self.repos.discovery.concepts_by_campaign(campaign_id):
            if _normalize_key(existing["title"]) == normalized:
                return None
        try:
            return self._save_concept(campaign_id, item, phase="session", source=source)
        except ValidationError:
            return None

    def _build_mission(self, kind: str, target: dict[str, Any]) -> MissionExport:
        mission_id = new_id()
        from app.core.mission_templates import get_mission_template

        template = get_mission_template(kind)
        if template:
            return MissionExport(
                mission_id=mission_id,
                kind=kind,
                target=target,
                objective=template["objective"],
                questions=template["questions"],
                suggested_queries=template["suggested_queries"],
                output_format="JSON conforme al esquema json_import_schema (nunca inventar datos).",
                required_evidence_fields=list(VERIFIED_REQUIRED_FIELDS),
                no_invention_rule=(
                    "NO inventar demanda, precios, competidores, clientes, estadísticas ni resultados. "
                    "Si no hay dato, escribir null y marcar el dato como desconocido."
                ),
                reliability_criteria=[
                    "Fuente primaria > secundaria.",
                    "URL concreta y fecha de consulta.",
                    "Fragmento textual relevante.",
                    "Notas de incertidumbre cuando aplique.",
                ],
                json_import_schema=template["json_schema"],
            )
        base_questions: dict[str, list[str]] = {
            "campaign": [
                "¿Qué problemas reales existen en este territorio que la gente paga por resolver?",
                "¿Quién paga ya por una solución, cuánto y con qué frecuencia?",
                "¿Qué soluciones existen hoy y por qué son caras, lentas o malas?",
            ],
            "signal": [
                "¿Qué comportamientos o costes ocultos confirman esta tensión?",
                "¿Dónde se queja la gente de este problema (foros, reseñas, redes)?",
                "¿Qué intenta la gente hoy para resolverlo a mano?",
            ],
            "candidate": [
                "¿Quién exactamente pagaría por esto y de qué presupuesto saldría el pago?",
                "¿Qué alternativa usa hoy y cuánto le cuesta?",
                "¿Existen ya equivalentes? ¿Qué les falta?",
                "¿Puede una IA generalista resolver el 80% de este problema?",
            ],
            "tournament": [
                "Compara estas candidatas: ¿cuál tiene mayor dolor económico real?",
                "¿Cuál es menos sustituible por una IA generalista?",
                "¿Cuál puede validarse antes y más barato?",
            ],
            "competitors": [
                "¿Quiénes compiten hoy y qué ofrecen exactamente?",
                "¿Qué precios publican y qué incluye cada plan?",
                "¿Qué debilidades citan sus clientes en reseñas?",
            ],
            "buyer": [
                "¿Quién es el usuario, quién el comprador y quién el beneficiario?",
                "¿Qué evento dispara la compra?",
                "¿Cuál es el coste de no resolver el problema?",
            ],
            "substitution": [
                "¿Puede el cliente pegar su información en ChatGPT/Gemini y obtener un resultado suficiente?",
                "¿Qué parte del resultado requiere workflow, integración o memoria que la IA genérica no tiene?",
            ],
            "equivalents": [
                "¿Existen productos o servicios equivalentes ya en el mercado?",
                "¿Qué hacen distinto? ¿Qué dejarían de hacer los clientes si existiera esto?",
            ],
        }
        queries: dict[str, list[str]] = {
            "campaign": ["\"<término del problema>\" foro", "\"<problema>\" precio servicio", "alternativas a <problema>"],
            "candidate": ["<concepto> competidores", "<concepto> precio", "reviews <concepto> similar"],
            "competitors": ["competidores <concepto>", "precio <concepto> servicio", "reseñas <concepto>"],
            "buyer": ["quién contrata <servicio>", "cuánto cuesta <servicio>", "alternativa a <servicio>"],
            "substitution": ["ChatGPT para <tarea> vs herramienta", "<tarea> sin programar"],
            "equivalents": ["alternativa a <concepto>", "herramienta similar a <concepto>", "<concepto> ya existe"],
        }
        return MissionExport(
            mission_id=mission_id,
            kind=kind,
            target=target,
            objective=f"Investigar con evidencias verificables (URL + fecha + fragmento) la hipótesis: {target.get('concept_title') or target.get('campaign_title', 'campaña de descubrimiento')}.",
            questions=base_questions.get(kind, base_questions["candidate"]),
            suggested_queries=queries.get(kind, queries["candidate"]),
            output_format="JSON conforme al esquema json_import_schema (nunca inventar datos).",
            required_evidence_fields=list(VERIFIED_REQUIRED_FIELDS),
            no_invention_rule=(
                "NO inventar demanda, precios, competidores, clientes, estadísticas ni resultados. "
                "Si no hay dato, escribir null y marcar el dato como desconocido."
            ),
            reliability_criteria=[
                "Fuente primaria > secundaria.",
                "URL concreta y fecha de consulta.",
                "Fragmento textual relevante.",
                "Notas de incertidumbre cuando aplique.",
            ],
            json_import_schema={
                "mission_id": "<id de la misión>",
                "evidences": [
                    {"evidence_type": "demand_signal|competitor|price|customer_profile|technical|regulatory|other",
                     "source_name": "string", "source_url": "string", "captured_at": "ISO-8601", "summary": "string",
                     "raw_excerpt": "string", "reliability_score": "0-1", "independence_group": "string",
                     "verified": "bool — solo true si hay URL+fecha+fragmento", "verification_notes": "string"}
                ],
                "competitors": [{"name": "string", "url": "string", "offer": "string", "observed_price": "USD|null", "strengths": "string", "weaknesses": "string"}],
                "buyer_confirmed": {"user": "string", "buyer": "string", "beneficiary": "string", "budget_source": "string", "trigger_event": "string", "current_alternative": "string", "cost_of_not_solving": "string"},
                "notes": "string",
                "verified": False,
            },
        )

    def export_mission_markdown(self, mission_id: str) -> str:
        mission = self.repos.discovery.get_mission(mission_id)
        if mission is None:
            raise NotFoundError("Misión no encontrada.")
        payload = mission["export_payload"]
        lines = [
            f"# Misión de investigación — {payload['kind']}",
            "",
            f"- **Mission ID**: `{mission_id}`",
            f"- **Tipo**: {payload['kind']}",
            f"- **Objetivo**: {payload['objective']}",
            "",
            "## Preguntas",
        ]
        lines += [f"{i+1}. {q}" for i, q in enumerate(payload["questions"])]
        lines += ["", "## Consultas sugeridas"]
        lines += [f"- `{q}`" for q in payload["suggested_queries"]]
        lines += [
            "",
            "## Regla de no invención",
            payload["no_invention_rule"],
            "",
            "## Criterios de fiabilidad",
        ]
        lines += [f"- {c}" for c in payload["reliability_criteria"]]
        lines += [
            "",
            "## Formato de salida (JSON para reimportar)",
            "```json",
            json.dumps(payload["json_import_schema"], ensure_ascii=False, indent=2),
            "```",
        ]
        return "\n".join(lines)

    def import_mission_result(self, mission_id: str, payload: MissionIn) -> dict[str, Any]:
        mission = self.repos.discovery.get_mission(mission_id)
        if mission is None:
            raise NotFoundError("Misión no encontrada.")
        if payload.mission_id != mission_id:
            raise ValidationError("mission_id del payload no coincide con la misión.")

        n_verified, n_unverified = 0, 0
        cleaned_evidences: list[dict[str, Any]] = []
        for raw in payload.evidences:
            summary = str(raw.get("summary") or "").strip()
            url = str(raw.get("source_url") or "").strip()
            captured = str(raw.get("captured_at") or "").strip()
            has_fields = all([summary, url, captured])
            verified = bool(raw.get("verified")) and has_fields
            verification_notes = str(raw.get("verification_notes") or "")
            if verified:
                n_verified += 1
            else:
                n_unverified += 1
            cleaned_evidences.append(
                {
                    "evidence_type": str(raw.get("evidence_type") or "other"),
                    "source_name": str(raw.get("source_name") or "").strip() or None,
                    "source_url": url or None,
                    "captured_at": captured or None,
                    "summary": summary,
                    "raw_excerpt": str(raw.get("raw_excerpt") or "").strip() or None,
                    "reliability_score": max(0.0, min(1.0, float(raw.get("reliability_score") or 0.5))),
                    "independence_group": str(raw.get("independence_group") or "").strip() or None,
                    "verified": verified,
                    "verification_notes": (
                        verification_notes or ("Verificada: URL + fecha + fragmento presentes." if verified else "No cumple los criterios mínimos de verificación.")
                    ),
                }
            )
        self.repos.discovery.save_mission_result(
            mission_id,
            {
                "raw": payload.model_dump(mode="json"),
                "evidences": cleaned_evidences,
                "competitors": [dict(c) for c in payload.competitors],
                "buyer_confirmed": payload.buyer_confirmed,
                "verified": n_verified > 0,
                "verification_notes": (
                    f"{n_verified} evidencias verificadas, {n_unverified} no verificadas."
                    + (f" {payload.notes}" if payload.notes else "")
                ),
            },
        )
        self.repos.discovery.mark_mission_imported(mission_id)
        self._log(
            "discovery.mission_import",
            f"Resultados importados de la misión {mission_id}: {n_verified} verificadas, {n_unverified} sin verificar.",
            model="manual",
        )
        return {
            "mission_id": mission_id,
            "evidences_imported": len(cleaned_evidences),
            "verified": n_verified,
            "unverified": n_unverified,
        }

    def attach_mission_evidence(self, opportunity_id: str, mission_id: str) -> dict[str, Any]:
        """Copia las evidencias verificadas de una misión a una oportunidad."""
        if self.repos.opportunities.get(opportunity_id) is None:
            raise NotFoundError("Oportunidad no encontrada.")
        results = self.repos.discovery.mission_results(mission_id)
        if not results:
            raise ValidationError("La misión no tiene resultados importados.")
        from datetime import datetime, timezone

        from app.models.evidence import Evidence

        n_attached = 0
        for result in results:
            for raw in result.get("evidences", []):
                if not raw.get("verified"):
                    continue
                evidence = Evidence(
                    opportunity_id=opportunity_id,
                    evidence_type=raw["evidence_type"],
                    source_name=raw.get("source_name"),
                    source_url=raw.get("source_url"),
                    captured_at=raw.get("captured_at") or datetime.now(timezone.utc).isoformat(),
                    summary=raw["summary"],
                    raw_excerpt=raw.get("raw_excerpt"),
                    reliability_score=raw.get("reliability_score", 0.5),
                    independence_group=raw.get("independence_group"),
                    verified=raw["verified"],
                    verification_notes=raw.get("verification_notes"),
                    collected_by="mission",
                    method="manual",
                )
                if not self.repos.evidence.is_duplicate(evidence):
                    self.repos.evidence.create(evidence)
                    n_attached += 1
            for comp in result.get("competitors", []):
                from app.models.evidence import Competitor

                self.repos.competitors.create(
                    Competitor(
                        name=str(comp.get("name") or "competidor")[:300],
                        url=comp.get("url"),
                        offer=str(comp.get("offer") or "")[:5000] or None,
                        observed_price=comp.get("observed_price"),
                        strengths=str(comp.get("strengths") or "")[:2000] or None,
                        weaknesses=str(comp.get("weaknesses") or "")[:2000] or None,
                        opportunity_id=opportunity_id,
                    )
                )
        self._log("discovery.attach", f"{n_attached} evidencias verificadas adjuntadas a {opportunity_id} desde la misión {mission_id}.", model="manual")
        return {"opportunity_id": opportunity_id, "evidences_attached": n_attached}

    def list_missions(self, status: str | None = None) -> list[dict[str, Any]]:
        return self.repos.discovery.list_missions(status=status)

    def list_learning_records(self, kind: str | None = None) -> list[dict[str, Any]]:
        return self.repos.discovery.list_learning_records(kind=kind)

    # ------------------------------------------------------------------
    def _log(self, agent: str, summary: str, *, model: str) -> None:
        self.repos.decision_log.add(
            DecisionLog(
                agent=agent,
                input_summary="Business Discovery Engine",
                output_summary=summary,
                model_or_method=model,
            )
        )


def _fingerprint_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    from app.scoring.venture import semantic_distance

    return semantic_distance(a.get("fingerprint") or {}, b.get("fingerprint") or {})
