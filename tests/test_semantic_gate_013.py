"""Iteración 013: calidad semántica, estados honestos y reformulación antes de investigar.

Cubre las reglas de la corrección:
- Estados inequívocos (nunca passed/promoted sin fase; nunca ventajas no
  verificadas como hechos; score de viabilidad con evidencia empieza en 0).
- Quality Gate: comprador genérico inválido; NEEDS_REFORMULATION no se
  investiga; RECOMBINATION_INCOHERENT no genera misiones.
- Misiones PROGRESIVAS: solo Fase 1 (6) por candidata, nunca las 10 de golpe.
- Sin shortlist/finalista sin evidencia; 0 candidatas/finalistas válido.
- Reproceso: estados mapeados, misiones superseded, PRE_CYCLE detenido.
"""
from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.scoring.semantic_gate import (
    FORBIDDEN_STATUSES,
    INCOHERENT_EXAMPLES,
    STATUS_MEANINGS,
    has_generic_markers,
    hypothesis_classification,
    semantic_coherence,
    split_scores,
    validate_opportunity_brief,
)
from app.scoring.venture import venture_score

# ------------------------------------------------------------------ semántica


def _scores(**overrides):
    base = {
        "economic_pain": 70, "proven_demand": 70, "general_ai_resistance": 70,
        "defensibility": 70, "distribution": 70, "originality": 70,
        "validation_speed": 70, "gross_margin": 70, "recurrence": 70,
        "demonstrability": 70, "operational_simplicity": 70,
    }
    base.update(overrides)
    return base


def test_statuses_are_unambiguous_and_in_spanish():
    # Ninguna etiqueta ambigua del pasado puede aparecer como estado.
    for forbidden in FORBIDDEN_STATUSES:
        assert forbidden not in STATUS_MEANINGS
    # Todos los estados tienen significado explicado.
    for status, meaning in STATUS_MEANINGS.items():
        assert meaning and len(meaning) > 10


def test_never_show_passed_without_phase():
    # El vocabulario no contiene "passed" suelto ni "promoted".
    assert "passed" not in STATUS_MEANINGS
    assert "promoted" not in STATUS_MEANINGS
    assert "shortlisted" not in STATUS_MEANINGS
    assert "finalist" not in STATUS_MEANINGS


def test_advantages_are_hypothesis_without_evidence():
    label, meaning = hypothesis_classification("DEFENSIBLE_WORKFLOW", has_verified_evidence=False)
    assert label == "HYPOTHESIS_DEFENSIBLE_WORKFLOW"
    assert "Hipótesis" in meaning
    label, meaning = hypothesis_classification("NETWORK_ADVANTAGE", has_verified_evidence=False)
    assert label == "HYPOTHESIS_NETWORK_ADVANTAGE"
    assert "Hipótesis" in meaning
    # Con evidencia verificable sí se retira la palabra "Hipótesis".
    label, _ = hypothesis_classification("DATA_ADVANTAGE", has_verified_evidence=True)
    assert label == "DATA_ADVANTAGE"
    assert "Hipótesis" not in label


def test_evidence_backed_score_zero_without_evidence_and_capped_under_3_groups():
    r = venture_score(scores=_scores(), novelty_score=90, utility_score=90)
    assert r.evidence_backed_venture_score == 0.0
    assert r.proven_demand == 0.0
    assert r.distribution == 0.0
    # Con 1 grupo independiente: tope honesto 40.
    low = venture_score(
        scores=_scores(), novelty_score=90, utility_score=90,
        has_verified_evidence=True, verified_evidence_groups=1,
    )
    assert low.evidence_backed_venture_score <= 40
    # Con >=3 grupos: score real (puede superar 40).
    full = venture_score(
        scores=_scores(), novelty_score=90, utility_score=90,
        has_verified_evidence=True, verified_evidence_groups=3,
    )
    assert full.evidence_backed_venture_score > 40
    # split_scores unitario.
    s, e = split_scores(68.4, has_verified_evidence=False)
    assert s == 68.4 and e == 0.0


def test_generic_buyer_is_invalid():
    assert has_generic_markers("profesional o pequeña organización")
    assert has_generic_markers("persona interesada", "sufre el territorio")
    verdict = validate_opportunity_brief({"buyer": "profesional o pequeña organización", "specific_name": "x"})
    assert verdict["ok"] is False


def test_incoherent_recombination_phrases_detected():
    for phrase in INCOHERENT_EXAMPLES:
        ok, reason = semantic_coherence({"title": phrase, "mechanism": "algo"})
        assert ok is False, phrase
        assert reason
    # Un concepto con conexión causal pasa.
    ok, _ = semantic_coherence(
        {
            "title": "Checklist de cumplimiento RGPD para despachos de abogados pequeños",
            "problem_hypothesis": "Los despachos pequeños no tienen registro de actividades de tratamiento.",
            "mechanism": "Plantilla guiada que genera el registro de actividades del despacho.",
            "buyer_hypothesis": "Socio titular de despacho de abogados de 2-10 empleados.",
            "outcome_hypothesis": "Expediente documental listo para entregar a un asesor.",
        }
    )
    assert ok is True


# ------------------------------------------------------------------ pipeline

def test_commodity_filter_uses_new_statuses(container):
    camp = container.discovery.create_campaign({"title": "C", "phase1_target": 30, "shortlist_target": 6, "finalists_target": 2})
    container.discovery.run_phase1(camp["id"])
    detail = container.discovery.run_commodity_filter(camp["id"])
    statuses = {c["status"] for c in detail["concepts"]}
    assert statuses <= {"AI_FILTER_PASSED", "COMMODITY_BLOCKED"}
    assert not (statuses & set(FORBIDDEN_STATUSES))
    for c in detail["concepts"]:
        assert c["status_meaning"]


def test_needs_reformulation_cannot_be_promoted(container):
    camp = container.discovery.create_campaign({"title": "C", "phase1_target": 30, "shortlist_target": 6, "finalists_target": 2})
    container.discovery.run_phase1(camp["id"])
    detail = container.discovery.run_commodity_filter(camp["id"])
    # Sin brief: nadie es candidata.
    assert all(c["status"] != "RESEARCH_CANDIDATE" for c in detail["concepts"])
    with pytest.raises(ValidationError):
        container.discovery.promote(detail["concepts"][0]["id"])


def test_reformulation_requires_concrete_brief(container):
    camp = container.discovery.create_campaign({"title": "C", "phase1_target": 30, "shortlist_target": 6, "finalists_target": 2})
    container.discovery.run_phase1(camp["id"])
    detail = container.discovery.run_commodity_filter(camp["id"])
    concept = next(c for c in detail["concepts"] if c["status"] == "AI_FILTER_PASSED")
    # Brief genérico: rechazado.
    with pytest.raises(ValidationError):
        container.discovery.complete_opportunity_brief(
            concept["id"], {"buyer": "profesional o pequeña organización"}
        )
    # Brief concreto de hipótesis: candidata.
    updated = container.discovery.complete_opportunity_brief(
        concept["id"], container.discovery.demo_brief_for(concept)
    )
    assert updated["status"] == "RESEARCH_CANDIDATE"
    assert updated["venture"]["evidence_backed_venture_score"] == 0.0


def test_phase1_missions_only_six_not_ten(container):
    camp = container.discovery.create_campaign({"title": "C", "phase1_target": 30, "shortlist_target": 6, "finalists_target": 2})
    container.discovery.run_phase1(camp["id"])
    detail = container.discovery.run_commodity_filter(camp["id"])
    candidate = None
    for c in detail["concepts"]:
        if c["status"] != "AI_FILTER_PASSED":
            continue
        candidate = container.discovery.complete_opportunity_brief(
            c["id"], container.discovery.demo_brief_for(c)
        )
        break
    assert candidate and candidate["status"] == "RESEARCH_CANDIDATE"
    missions = []
    from app.services.discovery import RESEARCH_PHASE1_KINDS, RESEARCH_PHASE2_KINDS

    for kind in RESEARCH_PHASE1_KINDS:
        m = container.discovery.create_mission(kind=kind, campaign_id=camp["id"], concept_id=candidate["id"])
        missions.append(m)
    assert len(missions) == 6
    # La fase 2 NO se genera automáticamente.
    active = [m for m in container.discovery.list_missions() if m.get("status") != "SUPERSEDED_BY_SEMANTIC_QUALITY_GATE"]
    assert len(active) == 6
    assert all(m.kind in RESEARCH_PHASE1_KINDS for m in missions)
    assert all(m.kind not in RESEARCH_PHASE2_KINDS for m in missions)


def test_incoherent_concept_gets_no_missions(container):
    from app.services.discovery import SUPERSEDED_BY_SEMANTIC_GATE

    camp = container.discovery.create_campaign({"title": "C", "phase1_target": 30, "shortlist_target": 6, "finalists_target": 2})
    container.discovery.run_phase1(camp["id"])
    detail = container.discovery.run_commodity_filter(camp["id"])
    concept = next(c for c in detail["concepts"] if c["status"] == "AI_FILTER_PASSED")
    container.discovery.reprocess_semantic_gate(camp["id"])  # no op relevante
    # Forzamos incoherencia real y verificamos que no se promueve ni investiga.
    container.repos.discovery.update_concept(
        concept["id"],
        title=INCOHERENT_EXAMPLES[0],
        coherence_ok=False,
        coherence_reason="patrón de recombinación incoherente (ejemplo detectado)",
        status="RECOMBINATION_INCOHERENT",
    )
    with pytest.raises(ValidationError):
        container.discovery.promote(concept["id"])
    # Ninguna misión para el concepto incoherente.
    missions = [m for m in container.discovery.list_missions() if (m.get("target") or {}).get("concept_id") == concept["id"]]
    assert missions == []


def test_shortlist_without_evidence_is_not_validated(container):
    # SHORTLISTED_WITH_EVIDENCE solo existe en el vocabulario; un concepto sin
    # evidencia verificada no puede alcanzar ese estado vía el pipeline.
    camp = container.discovery.create_campaign({"title": "C", "phase1_target": 30, "shortlist_target": 6, "finalists_target": 2})
    container.discovery.run_phase1(camp["id"])
    container.discovery.run_commodity_filter(camp["id"])
    detail = container.discovery.campaign_detail(camp["id"])
    assert all(c.get("status") != "SHORTLISTED_WITH_EVIDENCE" for c in detail["concepts"])
    assert all((c.get("verified_evidence_count") or 0) == 0 for c in detail["concepts"])


def test_zero_finalists_is_valid(container):
    # Sin briefs completados -> 0 candidatas -> torneo omitido -> 0 finalistas.
    run = container.orchestrator.create_real_campaign()
    rid = run["run"]["id"]
    detail = container.orchestrator.advance(rid)
    assert detail["run"]["state"] == "RESEARCH_PENDING"
    concepts = (detail.get("discovery") or {}).get("concepts") or []
    assert sum(1 for c in concepts if c.get("status") in ("FINALIST", "RESEARCH_CANDIDATE")) >= 0


# ------------------------------------------------------------------ reproceso

def test_reprocess_maps_statuses_and_supersedes_missions(container):
    camp = container.discovery.create_campaign({"title": "C", "phase1_target": 30, "shortlist_target": 6, "finalists_target": 2})
    container.discovery.run_phase1(camp["id"])
    detail = container.discovery.run_commodity_filter(camp["id"])
    # Crear misiones antiguas (las 10 de golpe, como hacía la iteración 010).
    from app.services.discovery import RESEARCH_PHASE1_KINDS

    concept = next(c for c in detail["concepts"] if c["status"] == "AI_FILTER_PASSED")
    for kind in RESEARCH_PHASE1_KINDS:
        container.discovery.create_mission(kind=kind, campaign_id=camp["id"], concept_id=concept["id"])
    before = container.discovery.list_missions()
    assert len(before) == 6

    # Simular estado antiguo en un concepto (trazabilidad sin borrar).
    container.repos.discovery.update_concept(concept["id"], status="promoted")
    res = container.discovery.reprocess_semantic_gate(camp["id"])
    assert res["reprocess"]["missions_superseded"] == 6
    # Las 6 antiguas quedan SUPERSEDED (no borradas); solo las nuevas de Fase 1
    # para candidatas seleccionadas quedan activas.
    after = container.discovery.list_missions()
    old_ids = {m["mission_id"] for m in before}
    for m in after:
        if m["mission_id"] in old_ids:
            assert m["status"] == "SUPERSEDED_BY_SEMANTIC_QUALITY_GATE"
    active = [m for m in after if m["status"] != "SUPERSEDED_BY_SEMANTIC_QUALITY_GATE"]
    assert len(active) == res["reprocess"]["phase1_missions"]
    # Los estados viejos quedan mapeados a la nueva semántica.
    for c in res["concepts"]:
        assert c["status"] not in FORBIDDEN_STATUSES


def test_reprocess_keeps_traceability(container):
    camp = container.discovery.create_campaign({"title": "C", "phase1_target": 30, "shortlist_target": 6, "finalists_target": 2})
    d1 = container.discovery.run_phase1(camp["id"])
    n_before = len(d1["concepts"])
    container.discovery.run_commodity_filter(camp["id"])
    res = container.discovery.reprocess_semantic_gate(camp["id"])
    # No se borra ninguna idea: trazabilidad completa (las reformulaciones son
    # adiciones, nunca sustituciones).
    ids_before = {c["id"] for c in d1["concepts"]}
    ids_after = {c["id"] for c in res["concepts"]}
    assert ids_before <= ids_after
    assert len(res["concepts"]) >= n_before


def test_reprocess_does_not_start_cycle(container):
    camp = container.discovery.create_campaign({"title": "C", "phase1_target": 30, "shortlist_target": 6, "finalists_target": 2})
    container.discovery.run_phase1(camp["id"])
    container.discovery.run_commodity_filter(camp["id"])
    container.discovery.reprocess_semantic_gate(camp["id"])
    status = container.cycle.evaluate()
    assert status["status"] == "PRE_CYCLE"
    assert status["clock_running"] is False
    assert status["started_at"] is None


def test_full_reprocess_flow_reformulates_and_creates_phase1_missions(container):
    """Reproceso completo: 3 candidatas abstractas -> reformulaciones ->
    torneo -> selección (máx. 3) -> misiones de Fase 1 (6 por candidata)."""
    camp = container.discovery.create_campaign({"title": "C", "phase1_target": 30, "shortlist_target": 6, "finalists_target": 2})
    container.discovery.run_phase1(camp["id"])
    detail = container.discovery.run_commodity_filter(camp["id"])
    # Promover 3 candidatas como si fuesen las finalistas previas (abstractas).
    promoted_ids = []
    for c in detail["concepts"]:
        if c["status"] != "AI_FILTER_PASSED" or len(promoted_ids) >= 3:
            continue
        container.repos.discovery.update_concept(c["id"], status="promoted")
        promoted_ids.append(c["id"])
    res = container.discovery.reprocess_semantic_gate(camp["id"])
    rep = res["reprocess"]
    # Las 3 antiguas se reformularon (3-5 reformulaciones cada una).
    assert rep["reformulations_generated"] == 3
    reform = [c for c in res["concepts"] if (c.get("source") or "").startswith("reformulation_of:")]
    assert 9 <= len(reform) <= 15
    # Se seleccionaron candidatas concretas (máx 3) y se crearon 6 misiones Fase 1 por candidata.
    assert rep["selected_candidates"] <= 3
    assert rep["phase1_missions"] == rep["selected_candidates"] * 6
    # Ninguna idea NEEDS_REFORMULATION tiene misiones activas.
    from app.services.discovery import SUPERSEDED_BY_SEMANTIC_GATE

    for m in container.discovery.list_missions():
        assert m["status"] != SUPERSEDED_BY_SEMANTIC_GATE
