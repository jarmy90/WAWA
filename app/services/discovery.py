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

# Iteración 013: misiones PROGRESIVAS. Fase 1 (descarte) primero; la fase 2
# solo para supervivientes. NUNCA se generan las 10 de golpe.
RESEARCH_PHASE1_KINDS = (
    "DEMAND_REALITY_CHECK",
    "BUYER_BUDGET_CHECK",
    "CURRENT_ALTERNATIVE_CHECK",
    "DISTRIBUTION_ACCESS_CHECK",
    "COMPETITOR_EQUIVALENT_SEARCH",
    "GENERAL_AI_SUBSTITUTION_CHECK",
)
RESEARCH_PHASE2_KINDS = (
    "MOAT_REALITY_CHECK",
    "DATA_AVAILABILITY_CHECK",
    "TOS_AND_LEGAL_CHECK",
    "EXPERIMENT_FEASIBILITY_CHECK",
)

# Etiqueta que invalida misiones obsoletas al reprocesar con el gate semántico.
SUPERSEDED_BY_SEMANTIC_GATE = "SUPERSEDED_BY_SEMANTIC_QUALITY_GATE"

# Campos que una evidencia DEBE traer para poder marcarse verified (regla de
# no auto-verificación: Freebuff u otra fuente no basta por sí misma).
# Iteración 016: el fragmento original (raw_excerpt) es obligatorio junto a
# URL y fecha, conforme a docs/FREEBUFF_RESEARCH_MISSIONS.md.
VERIFIED_REQUIRED_FIELDS = ("source_url", "captured_at", "summary", "raw_excerpt")


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
            self._enrich_concept(concept)
        return {
            "campaign": campaign,
            "concepts": concepts,
            "comparisons": self.repos.discovery.comparisons_by_campaign(campaign_id),
            "diversity": campaign.get("diversity", 0.0),
        }

    def _enrich_concept(self, concept: dict[str, Any]) -> dict[str, Any]:
        """Iteración 013: campos honestos por concepto — estado, qué significa,
        qué falta, siguiente acción y puntuación estructural vs con evidencia.
        Nunca muestra 'passed' sin fase ni 'promoted'."""
        from app.scoring.semantic_gate import STATUS_MEANINGS, hypothesis_classification, validate_opportunity_brief

        status = concept.get("status") or "GENERATED_HYPOTHESIS"
        concept["status_meaning"] = STATUS_MEANINGS.get(status, "Estado sin significado asignado.")
        ven = concept.get("venture") or {}
        concept["structural_concept_score"] = round(float(ven.get("structural_concept_score") or 0.0), 2)
        concept["evidence_backed_venture_score"] = round(float(ven.get("evidence_backed_venture_score") or 0.0), 2)
        concept["has_verified_evidence"] = bool(ven.get("has_verified_evidence"))

        # Clasificación de ventaja como HIPÓTESIS mientras no haya evidencia.
        sub = concept.get("substitution") or {}
        cls = sub.get("classification") or "UNKNOWN"
        label, meaning = hypothesis_classification(cls, concept["has_verified_evidence"])
        concept["ai_substitution_label"] = label
        concept["ai_substitution_meaning"] = meaning

        # Evidencia asociada (vía oportunidad promovida).
        groups, verified_count = self._evidence_counts(concept["id"])
        concept["evidence_groups"] = groups
        concept["verified_evidence_count"] = verified_count

        # Motivo de descarte / qué falta / próxima acción, por estado.
        brief = validate_opportunity_brief(concept.get("brief") or {})
        if status == "NEEDS_REFORMULATION":
            concept["rejection_reason"] = (
                "patrón interesante pero todavía no es una oportunidad concreta"
                + (f": {', '.join(brief['reasons'][:4])}" if brief["reasons"] else "")
            )
            concept["missing_evidence"] = ", ".join(brief["missing"][:8]) or "brief sin completar"
            concept["next_action"] = "generar reformulaciones específicas y completar el Opportunity Brief"
        elif status == "RECOMBINATION_INCOHERENT":
            concept["rejection_reason"] = concept.get("coherence_reason") or "recombinación incoherente"
            concept["missing_evidence"] = "reformulación con conexión causal"
            concept["next_action"] = "reformular con contexto y comprador conectados"
        elif status == "COMMODITY_BLOCKED":
            concept["rejection_reason"] = "una IA generalista puede resolver la mayor parte del problema"
            concept["missing_evidence"] = "limitación específica de una IA generalista"
            concept["next_action"] = "descartada (no invertir más)"
        elif status == "CONCEPTUAL_CLONE":
            concept["rejection_reason"] = "clon conceptual de otra idea de la campaña"
            concept["missing_evidence"] = "—"
            concept["next_action"] = "descartada (redundante)"
        elif status == "DIVERSITY_ELIMINATED":
            concept["rejection_reason"] = "eliminada para conservar diversidad de la shortlist"
            concept["missing_evidence"] = "—"
            concept["next_action"] = "descartada por diversidad"
        elif status == "RESEARCH_PENDING":
            concept["rejection_reason"] = ""
            concept["missing_evidence"] = "investigación externa pendiente (demanda, comprador, canal)"
            concept["next_action"] = "COPIAR MISIÓN PARA FREEBUFF y pegar la respuesta"
        elif status == "RESEARCH_CANDIDATE":
            concept["rejection_reason"] = ""
            concept["missing_evidence"] = "evidencia externa verificable (URL + fecha + fragmento)"
            concept["next_action"] = "generar misiones de Fase 1 (6) e investigar"
        elif status == "FINALIST":
            concept["rejection_reason"] = ""
            concept["missing_evidence"] = "revisiones del comité y síntesis"
            concept["next_action"] = "entrar al comité de contraste"
        elif status == "SHORTLISTED_WITH_EVIDENCE":
            concept["rejection_reason"] = ""
            concept["missing_evidence"] = "reevaluación final con evidencia"
            concept["next_action"] = "reevaluar y decidir finalistas"
        elif status == "EXPERIMENT_READY":
            concept["rejection_reason"] = ""
            concept["missing_evidence"] = "—"
            concept["next_action"] = "crear el plan de experimento"
        else:
            concept["rejection_reason"] = ""
            concept["missing_evidence"] = "—"
            concept["next_action"] = "continuar en el embudo"
        return concept

    def _evidence_counts(self, concept_id: str) -> tuple[int, int]:
        """Grupos independientes y evidencias verificadas de la oportunidad
        promovida (si existe). Sin oportunidad → 0."""
        try:
            opp = self.repos.opportunities.get_by_concept(concept_id) if hasattr(self.repos.opportunities, "get_by_concept") else None
        except Exception:
            opp = None
        if opp is None:
            return 0, 0
        rows = self.repos.evidence.list_for(opp.id)
        verified = [e for e in rows if getattr(e, "verified", False)]
        groups = {getattr(e, "independence_group", None) or "x" for e in verified}
        return len(groups), len(verified)

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
            "status": "GENERATED_HYPOTHESIS",
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
            self.repos.discovery.update_concept(concept["id"], status="COMMODITY_BLOCKED")
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
        blocked, passed, reform = 0, 0, 0
        for concept in concepts:
            if concept["status"] in ("COMMODITY_BLOCKED", "RECOMBINATION_INCOHERENT"):
                blocked += 1
                continue
            if concept["status"] in ("NEEDS_REFORMULATION",):
                reform += 1
                continue
            blockers = self._filter_blockers(concept)
            if blockers:
                self.repos.discovery.update_concept(concept["id"], status="COMMODITY_BLOCKED")
                for b in blockers:
                    self.repos.discovery.add_learning_record(
                        kind="rejection", pattern=b, source=f"filter:{concept['id']}", notes=concept["title"]
                    )
                blocked += 1
                continue
            # Iteración 013: este filtro SOLO decide commodity o no. La puerta
            # de marcadores genéricos (NEEDS_REFORMULATION) se aplica en la
            # promoción a candidata (run_shortlist / Opportunity Brief).
            self.repos.discovery.update_concept(concept["id"], status="AI_FILTER_PASSED")
            passed += 1
        self.repos.discovery.update_campaign(campaign_id, phase="phase2")
        self._log("discovery.phase2", f"Filtro de comoditización: {passed} pasan, {blocked} bloqueados (campaña {campaign_id}).", model="rules")
        return self.campaign_detail(campaign_id)

    # ------------------------------------------------------------------
    # FASE 3: recombinación de mecanismos
    # ------------------------------------------------------------------
    def run_recombine(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.get_campaign(campaign_id)
        passed = [
            c for c in self.repos.discovery.concepts_by_campaign(campaign_id)
            if c["status"] in ("AI_FILTER_PASSED", "STRUCTURAL_FILTER_PASSED")
        ]
        if len(passed) < 4:
            # Iteración 013: la recombinación es OPTATIVA. Con menos de 4
            # conceptos pasados se omite honestamente y el flujo continúa.
            detail = self.campaign_detail(campaign_id)
            detail["recombination_skipped"] = True
            detail["recombination_reason"] = f"menos de 4 conceptos pasaron el filtro ({len(passed)})."
            return detail
        call = self.providers.generate(
            "Recombina los mecanismos de los mejores conceptos en conceptos superiores.",
            system=json.dumps([{"id": c["id"], "title": c["title"], "territory_key": c["territory_key"], "mechanism": c["mechanism"]} for c in passed], ensure_ascii=False),
            task="discover_recombine",
            action="discovery_recombine",
            opportunity_id=campaign_id,
        )
        raw = (call.response.structured or {}).get("concepts", [])
        created = []
        from app.scoring.semantic_gate import semantic_coherence

        for item in raw:
            concept = self._save_concept(campaign_id, item, phase="phase3", source="recombined")
            coherent, reason = semantic_coherence(concept)
            self.repos.discovery.update_concept(concept["id"], coherence_ok=coherent, coherence_reason=reason)
            blockers = self._filter_blockers(concept)
            if not coherent:
                status = "RECOMBINATION_INCOHERENT"
            elif blockers:
                status = "COMMODITY_BLOCKED"
            else:
                status = "STRUCTURAL_FILTER_PASSED"
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
        # Sin investigación: demand/distribution no puntúan (lo fuerza venture_score).
        verified, groups = self._verified_evidence_for(concept["id"])
        result = venture_score(
            scores=eval_scores, novelty_score=novelty, utility_score=utility, blockers=blockers,
            has_verified_evidence=verified, verified_evidence_groups=groups,
        )
        saved = self.repos.discovery.save_venture_evaluation(
            concept["id"],
            {
                "scores": result.model_dump(mode="json", exclude={"final_score", "novelty_score", "utility_score", "blockers", "labels", "rationale"}),
                "final_score": result.final_score,
                "structural_concept_score": result.structural_concept_score,
                "evidence_backed_venture_score": result.evidence_backed_venture_score,
                "has_verified_evidence": result.has_verified_evidence,
                "novelty_score": result.novelty_score,
                "utility_score": result.utility_score,
                "blockers": result.blockers,
                "labels": result.labels,
                "rationale": result.rationale,
            },
        )
        return {**concept, "venture": saved}

    def _verified_evidence_for(self, concept_id: str) -> tuple[bool, int]:
        """Evidencia verificable asociada a un concepto (vía opportunity si existe)."""
        try:
            opp = self.repos.opportunities.get_by_concept(concept_id) if hasattr(self.repos.opportunities, "get_by_concept") else None
        except Exception:
            opp = None
        if opp is None:
            return False, 0
        rows = self.repos.evidence.list_for(opp.id)
        verified = [e for e in rows if getattr(e, "verified", False)]
        groups = {getattr(e, "independence_group", None) or "x" for e in verified}
        return bool(verified), len(groups)

    def evaluate_structural(self, campaign_id: str) -> dict[str, Any]:
        """Análisis estructural (iteración 010): Venture Quality Score
        determinista para los conceptos que pasaron el filtro. Sin LLM.
        No cambia estados: solo registra evaluaciones estructurales."""
        campaign = self.get_campaign(campaign_id)
        concepts = self.repos.discovery.concepts_by_campaign(campaign_id)
        evaluated = 0
        for concept in concepts:
            if concept["status"] not in ("AI_FILTER_PASSED", "STRUCTURAL_FILTER_PASSED"):
                continue
            self._evaluate_venture(concept, campaign_id)
            evaluated += 1
        self.repos.discovery.update_campaign(campaign_id, phase="structural")
        self._log(
            "discovery.structural",
            f"Análisis estructural: {evaluated} conceptos con Venture Quality Score (campaña {campaign_id}).",
            model="rules",
        )
        return self.campaign_detail(campaign_id)

    def run_shortlist(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.get_campaign(campaign_id)
        candidates = [
            c for c in self.repos.discovery.concepts_by_campaign(campaign_id)
            if c["status"] in ("AI_FILTER_PASSED", "STRUCTURAL_FILTER_PASSED")
        ]
        if not candidates:
            # Iteración 013: 0 candidatas es un resultado VÁLIDO (no se fuerzan).
            detail = self.campaign_detail(campaign_id)
            detail["shortlist_skipped"] = True
            detail["shortlist_reason"] = "ningún concepto superó el filtro de comoditización."
            return detail
        evaluated = [self._evaluate_venture(c, campaign_id) for c in candidates]
        evaluated.sort(key=lambda c: c["venture"]["final_score"], reverse=True)

        target = campaign["shortlist_target"]
        shortlisted: list[dict[str, Any]] = []
        from app.scoring.semantic_gate import validate_opportunity_brief

        for candidate in evaluated:
            if len(shortlisted) >= target:
                self.repos.discovery.update_concept(candidate["id"], status="DIVERSITY_ELIMINATED")
                continue
            fp = concept_fingerprint(candidate)
            if any(is_conceptual_clone(fp, concept_fingerprint(s))[0] for s in shortlisted):
                self.repos.discovery.update_concept(candidate["id"], status="CONCEPTUAL_CLONE")
                continue
            # Iteración 013: sin evidencia no existe shortlist validado. El
            # pre-shortlist solo puede ser NEEDS_REFORMULATION o RESEARCH_CANDIDATE
            # (si el Opportunity Brief es concreto).
            brief = validate_opportunity_brief(candidate.get("brief") or {})
            if brief["ok"] and candidate.get("buyer_hypothesis") and candidate.get("outcome_hypothesis"):
                status = "RESEARCH_CANDIDATE"
            else:
                status = "NEEDS_REFORMULATION"
            self.repos.discovery.update_concept(candidate["id"], status=status)
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
            if c["status"] not in ("RESEARCH_CANDIDATE", "FINALIST"):
                continue
            evals = self.repos.discovery.venture_evaluations_by_concept(c["id"])
            if evals:
                c["venture"] = evals[0]
                shortlisted.append(c)
        if len(shortlisted) < 2:
            # Iteración 013: con menos de 2 candidatas concretas el torneo se
            # omite honestamente (0 finalistas es un resultado válido).
            detail = self.campaign_detail(campaign_id)
            detail["tournament_skipped"] = True
            detail["tournament_reason"] = f"solo {len(shortlisted)} candidata(s) concreta(s) (mínimo 2)."
            return detail
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
            if c["id"] in {f["id"] for f in finalists}:
                self.repos.discovery.update_concept(c["id"], status="FINALIST")
            else:
                # Los no finalistas siguen siendo candidatas concretas (no
                # "eliminadas"): simplemente no ganaron el torneo.
                self.repos.discovery.update_concept(c["id"], status="RESEARCH_CANDIDATE")
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
        if concept["status"] not in ("RESEARCH_CANDIDATE", "FINALIST", "SHORTLISTED_WITH_EVIDENCE"):
            raise ValidationError(
                "Solo se promueven candidatas concretas (RESEARCH_CANDIDATE/FINALIST) o shortlist con evidencia."
            )
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
        self.repos.discovery.update_concept(concept_id, status="RESEARCH_PENDING")
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
            excerpt = str(raw.get("raw_excerpt") or "").strip()
            # Iteración 016: sin URL + fecha + fragmento NUNCA hay verificación.
            has_fields = all([summary, url, captured, excerpt])
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
    # ITERACIÓN 013: reprocesamiento semántico + reformulaciones
    # ------------------------------------------------------------------
    _OLD_STATUS_MAP = {
        "draft": "GENERATED_HYPOTHESIS",
        "passed": "AI_FILTER_PASSED",
        "recombined": "STRUCTURAL_FILTER_PASSED",
        "clone": "CONCEPTUAL_CLONE",
        "blocked": "COMMODITY_BLOCKED",
        "eliminated": "DIVERSITY_ELIMINATED",
        "shortlisted": "RESEARCH_CANDIDATE",
        "promoted": "RESEARCH_PENDING",
        "finalist": "FINALIST",
    }

    def reprocess_semantic_gate(self, campaign_id: str) -> dict[str, Any]:
        """Iteración 013: aplica los estados honestos y la puerta de calidad
        semántica a una campaña existente SIN borrar nada.

        - Mapea estados antiguos (passed/promoted/clone/...) a los nuevos.
        - Re-evalúa coherencia semántica y marcadores genéricos; degrada a
          RECOMBINATION_INCOHERENT / NEEDS_REFORMULATION cuando corresponde.
        - Invalida misiones obsoletas con SUPERSEDED_BY_SEMANTIC_QUALITY_GATE
          (no cuentan como investigación pendiente activa).
        - Recalcula la puntuación estructural / con evidencia.
        - No borra ideas ni evidencia: conserva trazabilidad.
        """
        from app.scoring.semantic_gate import has_generic_markers, semantic_coherence

        concepts = self.repos.discovery.concepts_by_campaign(campaign_id)
        counts = {
            "mapped": 0, "needs_reformulation": 0, "incoherent": 0,
            "generic_markers": 0, "research_candidates": 0, "re_evaluated": 0,
        }
        for concept in concepts:
            old = concept.get("status") or "draft"
            mapped = self._OLD_STATUS_MAP.get(old, old)
            counts["mapped"] += 1 if mapped != old else 0

            coherent, reason = semantic_coherence(concept)
            self.repos.discovery.update_concept(
                concept["id"], coherence_ok=coherent, coherence_reason=reason
            )
            hits = has_generic_markers(
                concept.get("problem_hypothesis"), concept.get("buyer_hypothesis"), concept.get("title")
            )

            if not coherent:
                mapped = "RECOMBINATION_INCOHERENT"
                counts["incoherent"] += 1
            elif hits:
                mapped = "NEEDS_REFORMULATION"
                counts["generic_markers"] += 1

            if mapped in ("NEEDS_REFORMULATION",):
                counts["needs_reformulation"] += 1
            elif mapped in ("RESEARCH_CANDIDATE", "RESEARCH_PENDING", "FINALIST", "SHORTLISTED_WITH_EVIDENCE", "EXPERIMENT_READY"):
                # Una candidata debe seguir siendo CONCRETA tras el gate: sin
                # Opportunity Brief concreto, una promovida abstracta vuelve a
                # NEEDS_REFORMULATION (nunca se investiga una idea abstracta).
                brief_ok = self._brief_ok(concept)
                if not brief_ok and mapped != "EXPERIMENT_READY":
                    mapped = "NEEDS_REFORMULATION"
                    counts["needs_reformulation"] += 1
                else:
                    counts["research_candidates"] += 1

            self.repos.discovery.update_concept(concept["id"], status=mapped)
            # Re-evaluación estructural honesta (sin evidencia, demanda/distribución a 0).
            self._evaluate_venture(concept, campaign_id)
            counts["re_evaluated"] += 1

        # Invalida misiones obsoletas (no se borran: se marcan y se conservan).
        superseded = 0
        for mission in self.repos.discovery.missions_by_campaign(campaign_id):
            if mission.get("status") != SUPERSEDED_BY_SEMANTIC_GATE:
                self.repos.discovery.update_mission_status(mission["mission_id"], SUPERSEDED_BY_SEMANTIC_GATE)
                superseded += 1
        counts["missions_superseded"] = superseded

        # Reformula las candidatas previas (promovidas/finalistas) que ahora
        # necesitan reformulación, ejecuta el torneo de reformulaciones y crea
        # misiones de Fase 1 SOLO para candidatas realmente concretas.
        reform_counts = self._reformulate_and_select(campaign_id, counts)
        counts.update(reform_counts)

        self._log(
            "discovery.semantic_gate",
            f"Reproceso semántico (campaña {campaign_id}): {counts['mapped']} estados mapeados, "
            f"{counts['needs_reformulation']} necesitan reformulación, {superseded} misiones superseded, "
            f"{counts.get('selected_candidates', 0)} candidatas seleccionadas, "
            f"{counts.get('phase1_missions', 0)} misiones de Fase 1 creadas.",
            model="rules",
        )
        return {**self.campaign_detail(campaign_id), "reprocess": counts}

    def _reformulate_and_select(self, campaign_id: str, counts: dict[str, int]) -> dict[str, int]:
        """Paso 2 del reproceso (iteración 013):
        1. Genera 3-5 reformulaciones concretas para las candidatas previas
           (las que fueron promovidas/finalistas y ahora son abstractas).
        2. Completa sus briefs (hipótesis) y ejecuta el torneo de
           reformulaciones (máx. 3 candidatas; puede ser 0).
        3. Promueve las seleccionadas y crea misiones de Fase 1 (6 por
           candidata). Ninguna idea con NEEDS_REFORMULATION se investiga.
        """
        reformulated = 0
        selected_candidates = 0
        phase1_missions = 0
        reform_candidates = []
        for concept in self.repos.discovery.concepts_by_campaign(campaign_id):
            if (concept.get("source") or "").startswith("reformulation_of:"):
                continue  # no reformular reformulaciones
            if concept.get("status") != "NEEDS_REFORMULATION":
                continue
            if concept.get("brief"):
                continue
            was_promoted = False
            try:
                opp = (
                    self.repos.opportunities.get_by_concept(concept["id"])
                    if hasattr(self.repos.opportunities, "get_by_concept") else None
                )
                was_promoted = opp is not None
            except Exception:
                was_promoted = False
            reform_candidates.append((concept, was_promoted))
        # Las candidatas previamente promovidas se reformulan primero.
        reform_candidates.sort(key=lambda t: (not t[1]))
        for concept, _ in reform_candidates[:3]:
            self.generate_reformulations(campaign_id, concept["id"])
            reformulated += 1
        counts["reformulations_generated"] = reformulated

        # Completa los briefs ya rellenos de las reformulaciones (hipótesis).
        for concept in self.repos.discovery.concepts_by_campaign(campaign_id):
            if (concept.get("source") or "").startswith("reformulation_of:") and concept.get("brief"):
                try:
                    self.complete_opportunity_brief(concept["id"], concept.get("brief") or {})
                except ValidationError:
                    pass  # si el brief no pasa el gate, queda NEEDS_REFORMULATION

        tournament = self.run_reformulation_tournament(campaign_id)
        counts["selected_candidates"] = tournament["count"]
        selected_candidates = tournament["count"]

        for concept in self.repos.discovery.concepts_by_campaign(campaign_id):
            if concept.get("status") not in ("RESEARCH_CANDIDATE",):
                continue
            if concept["id"] not in tournament["selected"]:
                continue
            self.promote(concept["id"])  # crea la oportunidad; estado RESEARCH_PENDING
            for kind in RESEARCH_PHASE1_KINDS:
                self.create_mission(kind=kind, campaign_id=campaign_id, concept_id=concept["id"])
                phase1_missions += 1
        counts["phase1_missions"] = phase1_missions
        counts["promoted_candidates"] = tournament["count"]
        return counts

    def _brief_ok(self, concept: dict[str, Any]) -> bool:
        from app.scoring.semantic_gate import validate_opportunity_brief

        return bool(validate_opportunity_brief(concept.get("brief") or {})["ok"])

    # Reformulaciones deterministas por familia (HIPÓTESIS concretas, sin
    # inventar demanda: los sectores/normas/roles son anclas reales conocidas).
    REFORMULATION_TEMPLATES: dict[str, list[dict[str, str]]] = {
        "regulatorio": [
            {
                "title": "Checklist y expediente documental RGPD para despachos de abogados pequeños",
                "problem_hypothesis": "Los despachos de abogados con menos de 10 empleados no tienen un registro de actividades de tratamiento completo y arriesgan sanciones RGPD que no pueden afrontar.",
                "mechanism": "Plantilla guiada que genera el registro de actividades, la política de privacidad y el checklist de cumplimiento adaptados al despacho, con revisión humana final.",
                "buyer_hypothesis": "Socio titular de despachos de abogados de 2-10 empleados en España.",
                "outcome_hypothesis": "Expediente documental listo para entregar a un asesor externo en menos de una tarde, sin contratar consultoría.",
            },
            {
                "title": "Preparación del modelo 232 de operaciones vinculadas para asesorías contables",
                "problem_hypothesis": "Las asesorías contables pequeñas preparan el modelo 232 (operaciones vinculadas) con datos dispersos en Excel y pierden horas cada ejercicio.",
                "mechanism": "Checklist por cliente con plantilla de recogida de datos, cruce contra el padrón de socios y generación del borrador del modelo 232.",
                "buyer_hypothesis": "Asesorías contables de 1-5 personas que llevan clientes con operaciones vinculadas.",
                "outcome_hypothesis": "Borradero del modelo 232 por cliente en menos de 2 horas, con la lista de datos que faltan.",
            },
            {
                "title": "Expediente de subvención Next Generation para talleres de reparación de vehículos",
                "problem_hypothesis": "Los talleres de reparación de vehículos no se presentan a subvenciones de digitalización porque el expediente es largo y desconocen los requisitos.",
                "mechanism": "Guía de elegibilidad + checklist de documentación + plantilla de memoria técnica específica de la convocatoria.",
                "buyer_hypothesis": "Titulares de talleres de reparación de vehículos de 5-15 empleados.",
                "outcome_hypothesis": "Expediente de solicitud completo y revisado contra los requisitos de la convocatoria antes de la fecha límite.",
            },
            {
                "title": "Checklist de facturación electrónica (Ley Crea y Crece) para pequeños comercios",
                "problem_hypothesis": "Los pequeños comercios desconocen qué debe emitir su software de facturación para cumplir la facturación electrónica y no tienen quién lo verifique.",
                "mechanism": "Checklist de requisitos por programa de facturación + plantilla de verificación y plan de migración en 30 días.",
                "buyer_hypothesis": "Titulares de comercios minoristas de 1-5 empleados con software de facturación básico.",
                "outcome_hypothesis": "Plan de cumplimiento concreto con fechas y responsables para el software que ya usan.",
            },
        ],
        "intermediarios": [
            {
                "title": "Historial verificable de comisiones para propietarios que contratan agencias inmobiliarias",
                "problem_hypothesis": "Los propietarios que encargan la venta a una agencia no conservan un registro verificable de comisiones, condiciones y entregables pactados.",
                "mechanism": "Plantilla de registro por operación (comisión pactada, condiciones, entregables, fechas) exportable a PDF y compartible con un asesor.",
                "buyer_hypothesis": "Propietarios de vivienda que contratan una agencia inmobiliaria de barrio.",
                "outcome_hypothesis": "Historial completo de la operación listo para reclamar o comparar servicios.",
            },
            {
                "title": "Dossier de presupuestos y entregables para autónomos que contratan plataformas de intermediación",
                "problem_hypothesis": "Los autónomos que trabajan a través de plataformas de intermediación no conservan comparables de comisiones, plazos de pago y entregables entre plataformas.",
                "mechanism": "Registro estandarizado por plataforma (comisión, plazo de pago, entregables) con alerta cuando un plazo de pago se incumple.",
                "buyer_hypothesis": "Autónomos de servicios digitales que venden a través de 2-3 plataformas.",
                "outcome_hypothesis": "Comparativa actualizada de condiciones por plataforma para decidir dónde publicar.",
            },
            {
                "title": "Registro de cuotas y servicios para comunidades que contratan administradores de fincas",
                "problem_hypothesis": "Las comunidades de propietarios no pueden contrastar lo que cobra y entrega su administrador de fincas porque no existe un registro común.",
                "mechanism": "Cuaderno de servicios por comunidad: cuota, servicios incluidos, facturas y entregables, rellenado a partir de las actas.",
                "buyer_hypothesis": "Juntas de comunidades de propietarios de 10-40 viviendas.",
                "outcome_hypothesis": "Dossier anual por comunidad que permite comparar la cuota con los servicios realmente prestados.",
            },
        ],
        "incertidumbre": [
            {
                "title": "Benchmark anónimo de tarifas para clínicas dentales que deciden su precio de ortodoncia",
                "problem_hypothesis": "Las clínicas dentales pequeñas fijan el precio de ortodoncia sin un comparativo de tarifas de su zona y pierden margen o pacientes.",
                "mechanism": "Encuesta de tarifas anónima entre clínicas de la misma provincia con informe comparativo trimestral.",
                "buyer_hypothesis": "Gerentes de clínicas dentales de 2-5 dentistas.",
                "outcome_hypothesis": "Informe de tarifas por provincia con percentiles para decidir el precio.",
            },
            {
                "title": "Benchmark de costes de instalación para empresas de placas solares que deciden presupuesto",
                "problem_hypothesis": "Los instaladores de placas solares pequeños presupuestan sin un comparativo de costes por tipo de tejado y tipo de instalación.",
                "mechanism": "Registro colaborativo anónimo de costes reales por tipo de instalación con informe comparativo.",
                "buyer_hypothesis": "Instaladores de energía solar de 3-10 empleados.",
                "outcome_hypothesis": "Rango de costes por tipo de instalación para ajustar presupuestos.",
            },
            {
                "title": "Benchmark de honorarios para gestorías que deciden su tarifa mensual",
                "problem_hypothesis": "Las gestorías pequeñas fijan la cuota mensual de clientes sin saber el rango de honorarios de su provincia.",
                "mechanism": "Encuesta anónima de honorarios por tipo de cliente (autónomo, pyme) con informe comparativo.",
                "buyer_hypothesis": "Titulares de gestorías administrativas de 1-5 empleados.",
                "outcome_hypothesis": "Rango de honorarios por provincia y tipo de cliente para posicionar la cuota.",
            },
        ],
    }

    def generate_reformulations(self, campaign_id: str, concept_id: str) -> dict[str, Any]:
        """Genera 3-5 reformulaciones CONCRETAS (hipótesis) para un concepto
        abstracto. Se guardan como conceptos nuevos con estado
        NEEDS_REFORMULATION y un brief pendiente de completar. Nunca inventa
        demanda: los ejemplos son hipótesis de formulación, no afirmaciones de
        mercado."""
        concept = self.repos.discovery.get_concept(concept_id)
        if concept is None:
            raise NotFoundError("Concepto no encontrado.")
        title = (concept.get("title") or "").lower()
        if "regul" in title or "norma" in title or "cumplimiento" in title:
            family = "regulatorio"
        elif "intermediar" in title or "opac" in title or "comision" in title:
            family = "intermediarios"
        else:
            family = "incertidumbre"
        templates = self.REFORMULATION_TEMPLATES.get(family, self.REFORMULATION_TEMPLATES["incertidumbre"])
        created = []
        for tpl in templates:
            brief = {
                "specific_name": tpl["title"],
                "user": tpl["buyer_hypothesis"],
                "buyer": tpl["buyer_hypothesis"],
                "situation": tpl["problem_hypothesis"],
                "observable_problem": tpl["problem_hypothesis"],
                "current_alternative": "La gestión se hace hoy con plantillas genéricas de internet y tiempo manual del propio negocio.",
                "economic_or_time_cost": "Horas de preparación no facturables y riesgo de incumplimiento o de fijar precios sin datos.",
                "concrete_deliverable": tpl["outcome_hypothesis"],
                "measurable_outcome": tpl["outcome_hypothesis"],
                "revenue_model": "Pago único por entrega del expediente o informe (30-90 EUR) con revisión incluida.",
                "expected_price_hypothesis": "Precio hipótesis de 30-90 EUR por entrega; por confirmar con compradores reales.",
                "first_distribution_channel": "Mensaje directo a 20 negocios concretos del sector identificados por zona (sin spam).",
                "first_20_buyers_location": "Lista de 20 negocios locales del sector objetivo, a verificar con directorios públicos.",
                "test_in_48_hours": "Ofrecer la entrega a 3 negocios reales y confirmar si pagarían (no es demanda verificada).",
                "generic_ai_limitation": "Una IA generalista no conoce los requisitos exactos de cada convocatoria ni entrega un expediente revisado por alguien responsable.",
                "compounding_asset": "Banco de plantillas y expedientes propios que mejora cada entrega.",
                "primary_risk": "Que el comprador no perciba urgencia o resuelva con la plantilla gratuita del organismo.",
                "assumptions": "Hipótesis de comprador, dolor y precio; ninguna verificada todavía.",
                "prohibited_claims": "No afirmar demanda, no prometer resultados, no citar clientes reales sin su permiso.",
            }
            item = {
                "title": tpl["title"],
                "problem_hypothesis": tpl["problem_hypothesis"],
                "mechanism": tpl["mechanism"],
                "buyer_hypothesis": tpl["buyer_hypothesis"],
                "outcome_hypothesis": tpl["outcome_hypothesis"],
                "why_now": "Reformulación de candidata abstracta (iteración 013).",
                "general_ai_risk": "Requiere datos específicos del sector y entregable revisable.",
                "asset_potential": "Plantillas y expedientes acumulados.",
                "territory_key": concept.get("territory_key"),
                "lens_keys": concept.get("lens_keys") or [],
                "archetype_key": concept.get("archetype_key"),
            }
            new_concept = self._save_concept(
                campaign_id, item, phase="reformulation", source=f"reformulation_of:{concept_id}"
            )
            self.repos.discovery.update_concept(
                new_concept["id"], status="NEEDS_REFORMULATION", brief=brief
            )
            created.append(new_concept)
        self._log(
            "discovery.reformulation",
            f"{len(created)} reformulaciones generadas para {concept_id} (familia {family}).",
            model="rules",
        )
        return {"family": family, "source_concept_id": concept_id, "created": created}

    def demo_brief_for(self, concept: dict[str, Any]) -> dict[str, Any]:
        """Brief de HIPÓTESIS derivado del propio concepto. SOLO para demos y
        tests sintéticos: cada valor es una hipótesis de formulación, NUNCA
        evidencia de demanda ni afirmación de mercado. Los campos genéricos se
        sustituyen por frases concretas de hipótesis (el gate semántico nunca
        acepta 'profesional o pequeña organización' como comprador válido)."""
        from app.scoring.semantic_gate import has_generic_markers

        def concrete(text: str | None, fallback: str) -> str:
            value = str(text or "").strip()
            if len(value) < 12 or has_generic_markers(value):
                return fallback
            return value

        title = str(concept.get("title") or "Servicio concreto")[:300]
        problem = concrete(
            concept.get("problem_hypothesis"),
            "Hipótesis de problema: un negocio concreto del sector pierde tiempo o dinero cada semana por un proceso manual.",
        )
        buyer = concrete(
            concept.get("buyer_hypothesis"),
            "Comprador hipotético concreto: titular de un negocio local de un sector específico (a identificar por zona).",
        )
        deliverable = concrete(
            concept.get("outcome_hypothesis") or concept.get("mechanism"),
            "Entrega hipotética concreta: documento o informe revisable que el comprador puede guardar y reutilizar.",
        )
        return {
            "specific_name": title,
            "user": buyer,
            "buyer": buyer,
            "situation": problem,
            "observable_problem": problem,
            "current_alternative": "Alternativa actual: se hace hoy de forma manual con tiempo propio y sin verificación.",
            "economic_or_time_cost": "Coste hipotético: horas no facturables y riesgo de error o incumplimiento.",
            "concrete_deliverable": deliverable,
            "measurable_outcome": deliverable,
            "revenue_model": "Modelo hipotético: pago único por entrega (30-90 EUR) con revisión incluida.",
            "expected_price_hypothesis": "Precio hipótesis: 30-90 EUR; por confirmar con compradores reales.",
            "first_distribution_channel": "Canal hipotético: contacto directo con 20 negocios concretos de la zona (sin spam).",
            "first_20_buyers_location": "Ubicación hipotética: 20 negocios locales del sector objetivo, a verificar.",
            "test_in_48_hours": "Test hipotético: ofrecer la entrega a 3 negocios reales y confirmar intención de pago.",
            "generic_ai_limitation": "Limitación: una IA generalista no entrega un expediente responsable con los datos específicos del sector.",
            "compounding_asset": "Activo acumulativo: plantillas, expedientes y casos propios.",
            "primary_risk": "Riesgo principal: que el comprador no perciba urgencia o lo resuelva gratis.",
            "assumptions": "Suposiciones: comprador, dolor y precio sin verificar (hipótesis).",
            "prohibited_claims": "Prohibido: afirmar demanda, prometer resultados o citar clientes sin su permiso.",
        }

    def complete_opportunity_brief(self, concept_id: str, brief: dict[str, Any]) -> dict[str, Any]:
        """Completa el Opportunity Brief de un concepto. Solo si el brief es
        concreto (sin marcadores genéricos y con todos los campos) el concepto
        pasa a RESEARCH_CANDIDATE. El brief es HIPÓTESIS: no añade evidencia."""
        from app.scoring.semantic_gate import validate_opportunity_brief

        concept = self.repos.discovery.get_concept(concept_id)
        if concept is None:
            raise NotFoundError("Concepto no encontrado.")
        clean = {k: str(v).strip() for k, v in (brief or {}).items() if str(v).strip()}
        verdict = validate_opportunity_brief(clean)
        if not verdict["ok"]:
            raise ValidationError(
                "El Opportunity Brief no es concreto: " + "; ".join(verdict["reasons"][:5])
            )
        self.repos.discovery.update_concept(concept_id, brief=clean, status="RESEARCH_CANDIDATE")
        # Puntuación estructural determinista (sin evidencia: con evidencia 0).
        evals = self.repos.discovery.venture_evaluations_by_concept(concept_id)
        if not evals:
            self._evaluate_venture(concept, (concept or {}).get("campaign_id") or "")
        self._log(
            "discovery.brief",
            f"Opportunity Brief completado para {concept_id} -> RESEARCH_CANDIDATE.",
            model="rules",
        )
        updated = self.repos.discovery.get_concept(concept_id)
        evals = self.repos.discovery.venture_evaluations_by_concept(concept_id)
        if evals:
            updated["venture"] = evals[0]
        return {**updated, "brief_verdict": verdict}

    def run_reformulation_tournament(self, campaign_id: str) -> dict[str, Any]:
        """Torneo de reformulaciones: selecciona como MÁXIMO 3 candidatas
        concretas (RESEARCH_CANDIDATE) entre las reformulaciones con brief
        validado. Puede seleccionar 0: no existe obligación de conservar una
        idea de cada familia original."""
        campaign = self.get_campaign(campaign_id)
        max_candidates = int(campaign.get("finalists_target", 3))
        candidates = []
        for c in self.repos.discovery.concepts_by_campaign(campaign_id):
            if c.get("status") != "RESEARCH_CANDIDATE":
                continue
            evals = self.repos.discovery.venture_evaluations_by_concept(c["id"])
            if evals:
                c["venture"] = evals[0]
            else:
                # Las reformulaciones recién creadas aún no tienen evaluación
                # estructural: se calcula (determinista, sin evidencia).
                c = self._evaluate_venture(c, campaign_id)
            candidates.append(c)
        candidates.sort(key=lambda c: (c.get("venture") or {}).get("final_score", 0.0), reverse=True)
        selected = candidates[:max_candidates]
        for c in candidates[max_candidates:]:
            self.repos.discovery.update_concept(c["id"], status="NEEDS_REFORMULATION")
        self._log(
            "discovery.reformulation_tournament",
            f"{len(selected)} candidatas concretas seleccionadas de {len(candidates)} (máx. {max_candidates}; puede ser 0).",
            model="rules",
        )
        return {
            "campaign_id": campaign_id,
            "selected": [c["id"] for c in selected],
            "count": len(selected),
            "maximum": max_candidates,
            "titles": [c.get("title") for c in selected],
        }

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
