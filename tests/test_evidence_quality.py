"""Duplicados y penalización por baja fiabilidad."""
from __future__ import annotations

from app.core.container import build_container
from app.models.evidence import Evidence
from app.models.opportunity import OpportunityCreate
from tests.conftest import make_settings


def _add_evidence(repo, opp_id, *, summary, reliability, group, url=None, verified=False, method="import"):
    return repo.create(
        Evidence(
            opportunity_id=opp_id,
            evidence_type="demand_signal",
            source_name="fuente",
            source_url=url,
            summary=summary,
            reliability_score=reliability,
            independence_group=group,
            verified=verified,
            method=method,
        )
    )


def test_duplicate_evidence_skipped_on_import(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        opp = container.opportunities.create(
            OpportunityCreate(
                title="Con duplicados",
                problem="Problema con evidencias duplicadas en la importación.",
                proposed_solution="Solución.",
                target_customer="Cliente concreto de ejemplo.",
                sector="pruebas",
            )
        )
        from app.services.import_export import ResearchPackageIn

        payload = ResearchPackageIn(
            opportunity_id=opp.id,
            evidences=[
                {"summary": "Misma fuente y resumen", "source_url": "https://x.test/1", "reliability_score": 0.8},
                {"summary": "Misma fuente y resumen", "source_url": "https://x.test/1", "reliability_score": 0.8},
            ],
        )
        result = container.imports.import_research(payload)
        assert result["evidences_imported"] == 1  # el duplicado se descarta
        imported = [e for e in container.repos.evidence.list_for(opp.id) if e.method == "import"]
        assert len(imported) == 1
    finally:
        container.close()


def test_duplicate_evidence_is_duplicate_flag(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        opp = container.opportunities.create(
            OpportunityCreate(title="Dup", problem="Problema de prueba con resumen largo.", proposed_solution="S.", sector="t")
        )
        e1 = _add_evidence(container.repos.evidence, opp.id, summary="Resumen idéntico A", reliability=0.7, group="a")
        e2 = Evidence(
            opportunity_id=opp.id,
            evidence_type="demand_signal",
            source_name="fuente",
            summary="Resumen idéntico A",
            reliability_score=0.7,
            independence_group="b",
            method="import",
        )
        assert container.repos.evidence.is_duplicate(e2)  # mismo resumen -> duplicado
        e3 = Evidence(
            opportunity_id=opp.id,
            evidence_type="demand_signal",
            source_name="fuente",
            summary="Resumen completamente distinto",
            reliability_score=0.7,
            independence_group="b",
            method="import",
        )
        assert container.repos.evidence.is_duplicate(e3) is False
    finally:
        container.close()


def test_low_reliability_lowers_quality_score(tmp_path):
    settings = make_settings(tmp_path)
    container = build_container(settings)
    try:
        opp = container.opportunities.create(
            OpportunityCreate(
                title="Fiabilidad",
                problem="Problema de prueba para medir fiabilidad de evidencias.",
                proposed_solution="Solución.",
                target_customer="Cliente concreto.",
                sector="pruebas",
            )
        )
        _add_evidence(container.repos.evidence, opp.id, summary="Fuente poco fiable", reliability=0.1, group="a", verified=True)
        evaluation = container.pipeline.evaluate(opp.id, clear_existing=False)
        assert evaluation.evidence_quality_score < 20

        # Rehacer con evidencia fiable y verificada
        container.repos.evidence.delete_for_opportunity(opp.id)
        _add_evidence(container.repos.evidence, opp.id, summary="Fuente fiable y verificada", reliability=1.0, group="a", verified=True)
        evaluation2 = container.pipeline.evaluate(opp.id, clear_existing=False)
        assert evaluation2.evidence_quality_score > evaluation.evidence_quality_score
    finally:
        container.close()
