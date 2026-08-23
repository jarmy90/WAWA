"""Pruebas del Business Discovery Engine (iteración 004)."""
from __future__ import annotations

import tempfile
import pathlib

import pytest

from app.core.config import Settings
from app.core.container import build_container
from app.models.discovery import MissionIn, SubstitutionAnswers
from app.scoring.venture import (
    classify_substitution,
    concept_fingerprint,
    diversity_metric,
    is_conceptual_clone,
    originality_score,
    run_substitution_test,
    semantic_distance,
    venture_score,
)


def _container():
    tmp = pathlib.Path(tempfile.mkdtemp())
    settings = Settings(
        database_path=tmp / "t.db",
        manual_research_dir=tmp / "manual",
        llm_provider="mock",
        free_mode=True,
        simulation_mode=True,
    )
    return build_container(settings)


def _answers(**overrides) -> SubstitutionAnswers:
    defaults = dict(
        generic_ai_can_solve=40,
        output_is_generic=35,
        has_operational_workflow=70,
        has_data_integration=60,
        has_accumulative_memory=55,
        has_verifiable_outcome=65,
        has_followup_action=60,
        has_switching_cost=55,
        improves_with_use=55,
        survives_model_improvement=55,
        network_effect=25,
        distribution_loop=35,
        data_advantage=45,
    )
    defaults.update(overrides)
    return SubstitutionAnswers(**defaults)


# ---------------------------------------------------------------------------
# General AI Substitution Test
# ---------------------------------------------------------------------------
class TestSubstitutionTest:
    def test_commodity_wrapper_blocked(self):
        test = run_substitution_test(
            _answers(generic_ai_can_solve=85, output_is_generic=80, has_operational_workflow=10, has_data_integration=10, has_accumulative_memory=10)
        )
        assert test.classification == "COMMODITY_WRAPPER"
        assert test.verdict == "blocked"
        assert test.general_ai_resistance < 40

    def test_commodity_cannot_pass_even_with_demand(self):
        """Una idea con demanda aparente pero clasificada COMMODITY_WRAPPER no pasa."""
        test = run_substitution_test(
            _answers(generic_ai_can_solve=80, output_is_generic=70, has_operational_workflow=20, has_data_integration=15, has_accumulative_memory=10)
        )
        eval_result = venture_score(
            scores={k: 90.0 for k in ("economic_pain", "proven_demand", "general_ai_resistance", "defensibility", "distribution", "originality", "validation_speed", "gross_margin", "recurrence", "demonstrability", "operational_simplicity")},
            novelty_score=80,
            utility_score=80,
            blockers=["COMMODITY_WRAPPER"],
        )
        assert test.verdict == "blocked"
        assert "COMMODITY_WRAPPER" in eval_result.blockers
        assert eval_result.final_score < 40

    def test_data_advantage_classification(self):
        test = run_substitution_test(_answers(data_advantage=85, has_accumulative_memory=80))
        assert test.classification == "DATA_ADVANTAGE"
        assert test.verdict == "ok"

    def test_network_advantage_classification(self):
        test = run_substitution_test(_answers(network_effect=90))
        assert test.classification == "NETWORK_ADVANTAGE"

    def test_compounding_system(self):
        test = run_substitution_test(_answers(improves_with_use=75, has_accumulative_memory=70, survives_model_improvement=65))
        assert test.classification == "COMPOUNDING_SYSTEM"

    def test_resistance_grows_with_defenses(self):
        weak = run_substitution_test(_answers(has_operational_workflow=10, has_data_integration=10, has_accumulative_memory=10))
        strong = run_substitution_test(_answers(has_operational_workflow=90, has_data_integration=85, has_accumulative_memory=80))
        assert strong.general_ai_resistance > weak.general_ai_resistance


# ---------------------------------------------------------------------------
# Venture Quality Score
# ---------------------------------------------------------------------------
class TestVentureScore:
    def _scores(self, **overrides):
        base = {
            "economic_pain": 60,
            "proven_demand": 60,
            "general_ai_resistance": 60,
            "defensibility": 60,
            "distribution": 60,
            "originality": 60,
            "validation_speed": 60,
            "gross_margin": 70,
            "recurrence": 60,
            "demonstrability": 60,
            "operational_simplicity": 60,
        }
        base.update(overrides)
        return base

    def test_weights_sum_100_and_score_is_weighted(self):
        # novelty/utility altos para que originality no se anule en el recálculo
        result = venture_score(scores=self._scores(), novelty_score=75, utility_score=75)
        assert 0 <= result.final_score <= 100
        # todos 60 + margin 70 -> media > 60
        assert result.final_score > 60
        assert result.final_score < 62

    def test_ai_resistance_weights_higher(self):
        low = venture_score(scores=self._scores(general_ai_resistance=10))
        high = venture_score(scores=self._scores(general_ai_resistance=90))
        assert high.final_score > low.final_score

    def test_hard_blocker_caps_score(self):
        result = venture_score(scores=self._scores(), blockers=["Sin comprador identificable."])
        assert result.final_score < 40
        assert "Sin comprador identificable." in result.blockers

    def test_labels(self):
        result = venture_score(scores=self._scores(economic_pain=30), novelty_score=95, utility_score=90)
        assert "NOVEL_BUT_WEAK" in result.labels
        result2 = venture_score(scores=self._scores(general_ai_resistance=15, economic_pain=85), novelty_score=10, utility_score=10)
        assert "BORING_BUT_STRONG" in result2.labels

    def test_originality_utility_cap(self):
        """Novedosa pero inútil -> baja. Útil pero copiada -> baja en originalidad."""
        novel_useless = originality_score(novelty_score=95, utility_score=10)
        assert novel_useless < 25
        useful_copied = originality_score(novelty_score=10, utility_score=90)
        assert useful_copied < 50
        both = originality_score(novelty_score=85, utility_score=85)
        assert both > 70


# ---------------------------------------------------------------------------
# Diversidad y clones
# ---------------------------------------------------------------------------
class TestDiversity:
    def _concept(self, mechanism, archetype="VERTICAL_SAAS", territory="home", **kw):
        c = {"archetype_key": archetype, "territory_key": territory, "mechanism": mechanism, "problem_hypothesis": kw.get("problem", "problema"), "buyer_hypothesis": kw.get("buyer"), "outcome_hypothesis": kw.get("outcome"), "lens_keys": kw.get("lenses", [])}
        return c

    def test_identical_concepts_are_clones(self):
        a = self._concept("automatiza la contabilidad del hogar con integración bancaria")
        b = self._concept("automatiza la contabilidad del hogar con integración bancaria")
        fp_a, fp_b = concept_fingerprint(a), concept_fingerprint(b)
        clone, reason = is_conceptual_clone(fp_a, fp_b)
        assert clone
        assert semantic_distance(fp_a, fp_b) < 0.1

    def test_same_mechanism_different_sector_is_clone(self):
        """Cambiar de sector manteniendo idéntico mecanismo NO es diversidad."""
        a = self._concept("mercado inverso donde compradores publican su necesidad", archetype="REVERSE_MARKETPLACE", territory="home")
        b = self._concept("mercado inverso donde compradores publican su necesidad", archetype="REVERSE_MARKETPLACE", territory="tourism")
        fp_a, fp_b = concept_fingerprint(a), concept_fingerprint(b)
        clone, _ = is_conceptual_clone(fp_a, fp_b)
        assert clone

    def test_different_mechanisms_not_clones(self):
        a = self._concept("verificación de resultados con trazabilidad", archetype="VERIFICATION_TOOL")
        b = self._concept("comunidad que comparte datos y reparte valor", archetype="DATA_PRODUCT")
        fp_a, fp_b = concept_fingerprint(a), concept_fingerprint(b)
        clone, _ = is_conceptual_clone(fp_a, fp_b)
        assert not clone

    def test_diversity_metric(self):
        a = self._concept("verificación de resultados con trazabilidad", archetype="VERIFICATION_TOOL", territory="home", problem="problema A", buyer="dueño de casa", outcome="informe")
        b = self._concept("comunidad que comparte datos y reparte valor", archetype="DATA_PRODUCT", territory="tourism", problem="problema B", buyer="gestor hotelero", outcome="panel")
        fps = [concept_fingerprint(a), concept_fingerprint(b)]
        assert diversity_metric(fps) > 0.5
        assert diversity_metric([concept_fingerprint(a), concept_fingerprint(a)]) == 0.0
        assert diversity_metric([concept_fingerprint(a)]) == 1.0


# ---------------------------------------------------------------------------
# Campaña offline completa
# ---------------------------------------------------------------------------
class TestCampaignOffline:
    def test_full_pipeline(self):
        c = _container()
        try:
            campaign = c.discovery.create_campaign(
                {
                    "title": "Campaña offline",
                    "territory_keys": [],
                    "lens_keys": [],
                    "archetype_keys": [],
                    "phase1_target": 30,
                    "shortlist_target": 6,
                    "finalists_target": 2,
                }
            )
            assert campaign["phase"] == "created"

            detail = c.discovery.run_phase1(campaign["id"])
            concepts = detail["concepts"]
            assert len(concepts) >= 20
            for x in concepts:
                assert x["fingerprint"]
                assert x["substitution"] is not None
            assert detail["campaign"]["diversity"] > 0

            detail = c.discovery.run_commodity_filter(campaign["id"])
            statuses = {x["status"] for x in detail["concepts"]}
            assert statuses <= {"passed", "blocked"}

            detail = c.discovery.run_recombine(campaign["id"])
            assert len(detail["concepts"]) > len(concepts)

            detail = c.discovery.run_shortlist(campaign["id"])
            shortlisted = [x for x in detail["concepts"] if x["status"] == "shortlisted"]
            assert 2 <= len(shortlisted) <= 6
            for x in shortlisted:
                assert x["venture"]["final_score"] > 0
                assert x["venture"]["scores"]["proven_demand"] == 0  # offline: no se inventa demanda

            detail = c.discovery.run_tournament(campaign["id"])
            finalists = [x for x in detail["concepts"] if x["status"] == "finalist"]
            assert 1 <= len(finalists) <= 2
            assert detail["ranking"]
            assert detail["comparisons"]
            # el ranking ordena por victorias
            wins = [r["wins"] for r in detail["ranking"]]
            assert wins == sorted(wins, reverse=True)
        finally:
            c.close()

    def test_promote_requires_shortlist_or_finalist(self):
        c = _container()
        try:
            campaign = c.discovery.create_campaign({"title": "C", "phase1_target": 20, "shortlist_target": 6, "finalists_target": 2})
            c.discovery.run_phase1(campaign["id"])
            c.discovery.run_commodity_filter(campaign["id"])
            detail = c.discovery.campaign_detail(campaign["id"])
            draft = next(x for x in detail["concepts"])
            with pytest.raises(Exception):
                c.discovery.promote(draft["id"])
        finally:
            c.close()

    def test_learning_records_created(self):
        c = _container()
        try:
            campaign = c.discovery.create_campaign({"title": "C", "phase1_target": 30})
            c.discovery.run_phase1(campaign["id"])
            c.discovery.run_commodity_filter(campaign["id"])
            records = c.discovery.list_learning_records()
            assert any(r["kind"] == "rejection" for r in records)
        finally:
            c.close()


# ---------------------------------------------------------------------------
# Misiones Freebuff-first
# ---------------------------------------------------------------------------
class TestMissions:
    def test_create_and_export_mission(self):
        c = _container()
        try:
            campaign = c.discovery.create_campaign({"title": "C", "phase1_target": 20})
            c.discovery.run_phase1(campaign["id"])
            concept = c.discovery.campaign_detail(campaign["id"])["concepts"][0]
            mission = c.discovery.create_mission(kind="candidate", concept_id=concept["id"])
            assert mission.kind == "candidate"
            assert mission.no_invention_rule
            md = c.discovery.export_mission_markdown(mission.mission_id)
            assert "# Misión de investigación" in md
            assert "```json" in md
            saved = c.discovery.list_missions()
            assert any(m["mission_id"] == mission.mission_id for m in saved)
        finally:
            c.close()

    def test_import_verification_rules(self):
        c = _container()
        try:
            campaign = c.discovery.create_campaign({"title": "C", "phase1_target": 20})
            c.discovery.run_phase1(campaign["id"])
            concept = c.discovery.campaign_detail(campaign["id"])["concepts"][0]
            mission = c.discovery.create_mission(kind="candidate", concept_id=concept["id"])
            # verified=true sin URL+fecha+fragmento -> NO se marca verificada
            res = c.discovery.import_mission_result(
                mission.mission_id,
                MissionIn(
                    mission_id=mission.mission_id,
                    evidences=[
                        {"evidence_type": "demand_signal", "source_url": None, "captured_at": None, "summary": "sin datos", "verified": True},
                        {"evidence_type": "demand_signal", "source_url": "https://example.com/hilo", "captured_at": "2026-08-23T10:00:00Z", "summary": "Hilo real", "raw_excerpt": "frag", "verified": True},
                    ],
                ),
            )
            assert res["verified"] == 1
            assert res["unverified"] == 1
            results = c.discovery.repos.discovery.mission_results(mission.mission_id)
            by_url = {e["source_url"]: e for e in results[0]["evidences"]}
            assert by_url["https://example.com/hilo"]["verified"] is True
            assert by_url[None]["verified"] is False
        finally:
            c.close()

    def test_attach_mission_evidence(self):
        c = _container()
        try:
            campaign = c.discovery.create_campaign({"title": "C", "phase1_target": 30, "shortlist_target": 6, "finalists_target": 2})
            c.discovery.run_phase1(campaign["id"])
            c.discovery.run_commodity_filter(campaign["id"])
            c.discovery.run_recombine(campaign["id"])
            c.discovery.run_shortlist(campaign["id"])
            c.discovery.run_tournament(campaign["id"])
            detail = c.discovery.campaign_detail(campaign["id"])
            finalist = next(x for x in detail["concepts"] if x["status"] == "finalist")
            opp = c.discovery.promote(finalist["id"])
            mission = c.discovery.create_mission(kind="candidate", concept_id=finalist["id"])
            c.discovery.import_mission_result(
                mission.mission_id,
                MissionIn(
                    mission_id=mission.mission_id,
                    evidences=[
                        {"evidence_type": "demand_signal", "source_url": "https://example.com/hilo", "captured_at": "2026-08-23T10:00:00Z", "summary": "Hilo real", "raw_excerpt": "frag", "verified": True},
                    ],
                    competitors=[{"name": "Competidor A", "url": "https://example.com/a", "offer": "Servicio", "observed_price": 99.0}],
                ),
            )
            res = c.discovery.attach_mission_evidence(opp.id, mission.mission_id)
            assert res["evidences_attached"] == 1
            detail_opp = c.opportunities.detail(opp.id)
            assert len(detail_opp["evidences"]) == 1
            assert len(detail_opp["competitors"]) == 1
        finally:
            c.close()

    def test_mission_requires_target(self):
        c = _container()
        try:
            with pytest.raises(Exception):
                c.discovery.create_mission(kind="candidate")
        finally:
            c.close()


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
class TestDiscoveryAPI:
    def _client(self):
        from fastapi.testclient import TestClient

        from app.main import app

        tmp = pathlib.Path(tempfile.mkdtemp())
        settings = Settings(
            database_path=tmp / "t.db",
            manual_research_dir=tmp / "manual",
            llm_provider="mock",
            free_mode=True,
            simulation_mode=True,
        )
        container = build_container(settings)
        app.state.container = container
        return TestClient(app), container

    def test_campaign_flow_over_http(self):
        client, container = self._client()
        try:
            res = client.post(
                "/api/discovery/campaigns",
                json={"title": "Campaña HTTP", "phase1_target": 20, "shortlist_target": 6, "finalists_target": 2},
            )
            assert res.status_code == 200
            campaign_id = res.json()["campaign"]["id"]

            res = client.post(f"/api/discovery/campaigns/{campaign_id}/phase1")
            assert res.status_code == 200
            assert len(res.json()["concepts"]) >= 20

            res = client.post(f"/api/discovery/campaigns/{campaign_id}/filter")
            assert res.status_code == 200

            res = client.post(f"/api/discovery/campaigns/{campaign_id}/recombine")
            assert res.status_code == 200

            res = client.post(f"/api/discovery/campaigns/{campaign_id}/shortlist")
            assert res.status_code == 200

            res = client.post(f"/api/discovery/campaigns/{campaign_id}/tournament")
            assert res.status_code == 200
            body = res.json()
            assert body["ranking"]

            # inválido: id mal formado
            res = client.post("/api/discovery/campaigns/abc/phase1")
            assert res.status_code == 422
        finally:
            container.close()

    def test_mission_over_http(self):
        client, container = self._client()
        try:
            camp = client.post("/api/discovery/campaigns", json={"title": "Campaña M", "phase1_target": 20}).json()["campaign"]
            client.post(f"/api/discovery/campaigns/{camp['id']}/phase1")
            concepts = client.get(f"/api/discovery/campaigns/{camp['id']}").json()["concepts"]
            concept_id = concepts[0]["id"]
            res = client.post("/api/discovery/missions", json={"kind": "candidate", "concept_id": concept_id})
            assert res.status_code == 200
            mission_id = res.json()["mission"]["mission_id"]

            md = client.get(f"/api/discovery/missions/{mission_id}/export")
            assert md.status_code == 200
            assert "no invención" in md.text.lower() or "No inventar" in md.text

            res = client.post(
                f"/api/discovery/missions/{mission_id}/import",
                json={"mission_id": mission_id, "evidences": [{"evidence_type": "other", "summary": "x"}]},
            )
            assert res.status_code == 200
            assert res.json()["verified"] == 0
        finally:
            container.close()
