"""Iteración 017 — importación automática de planes de reformulación y
paquetes de investigación portables.

Garantías probadas (100 % offline):
1. Los concept_id/opportunity_id/mission_id del paquete portable NUNCA se
   insertan en la base local; los conceptos se localizan por título
   normalizado (reforzado por territorio+lente+arquetipo).
2. Coincidencia INEQUÍVCA exigida: ambiguo o inexistente ⇒ rechazo registrado,
   nunca aplicación dudosa.
3. Quality Gate: un brief inválido no convierte el concepto en candidata.
4. Idempotencia: re-aplicar el mismo plan no duplica nada.
5. El paquete de investigación se asocia a misiones LOCALES por mapeo
   estable; sin URL+fecha+fragmento la evidencia queda verified=false;
   el estado avanza a RESEARCH_IMPORTED solo vía import_research.
"""
from __future__ import annotations

import pytest

from app.services.reformulation_import import (
    _match_concept,
    apply_reformulation_plan,
    normalize_title,
    resolve_research_package,
)

ACTIVE_KINDS = (
    "DEMAND_REALITY_CHECK",
    "BUYER_BUDGET_CHECK",
    "CURRENT_ALTERNATIVE_CHECK",
    "DISTRIBUTION_ACCESS_CHECK",
    "COMPETITOR_EQUIVALENT_SEARCH",
    "GENERAL_AI_SUBSTITUTION_CHECK",
)


def _valid_brief() -> dict:
    """Opportunity Brief concreto (HIPÓTESIS, nunca evidencia)."""
    return {
        "specific_name": "Alertas de caducidad para farmacias de barrio",
        "user": "El responsable de compras de una farmacia independiente",
        "buyer": "El titular de la farmacia que paga el software de gestión",
        "situation": "Cada semana revisa manualmente fechas de caducidad en el lineal",
        "observable_problem": "Pierde ventas cuando un lote caduca antes de revisarlo",
        "current_alternative": "Hoja de cálculo revisada a mano los lunes por la mañana",
        "economic_or_time_cost": "Unas 3 horas semanales y mermas por lotes olvidados",
        "concrete_deliverable": "Informe semanal PDF con lotes en riesgo ordenados por prioridad",
        "measurable_outcome": "Reducir mermas por caducidad un 20% en tres meses",
        "revenue_model": "Suscripción mensual por farmacia",
        "expected_price_hypothesis": "29 EUR al mes como precio de prueba",
        "first_distribution_channel": "Contacto directo con 20 farmacias de la zona",
        "first_20_buyers_location": "Farmacias independientes de una ciudad media",
        "test_in_48_hours": "Preparar el informe a mano para 2 farmacias y pedir feedback",
        "generic_ai_limitation": "Requiere integración con el inventario real de cada farmacia",
        "compounding_asset": "Histórico de mermas por farmacia que mejora las alertas",
        "primary_risk": "El software de gestión ya ofrezca alertas incluidas",
        "assumptions": "Comprador, dolor y precio sin verificar: son hipótesis",
        "prohibited_claims": "Sin afirmar demanda ni citar clientes sin permiso",
    }


def _campaign_at_research_pending(container) -> tuple[str, str, list[dict]]:
    """Campaña real avanzada hasta RESEARCH_PENDING. Devuelve (run_id,
    discovery_campaign_id, conceptos reformulables)."""
    d = container.orchestrator.create_real_campaign()
    rid = d["run"]["id"]
    dcid = d["run"]["discovery_campaign_id"]
    container.orchestrator.advance(rid)
    concepts = container.discovery.campaign_detail(dcid).get("concepts") or []
    targets = [c for c in concepts if c["status"] == "NEEDS_REFORMULATION"]
    assert targets, "la campaña debe dejar direcciones reformulables"
    return rid, dcid, targets


def _plan_for(targets: list[dict]) -> dict:
    """Plan portable con concept_id FORÁNEOS (de una reproducción aislada)."""
    return {
        "briefs": [
            {"concept_id": f"foraneo-{i:04d}", "direccion_original": t["title"], "brief": _valid_brief()}
            for i, t in enumerate(targets[:2])
        ]
    }


# --------------------------------------------------------------- normalización
def test_normalize_title_stable():
    assert normalize_title("  Café   con Leche ") == normalize_title("cafe con leche")
    assert normalize_title("ÁRBOL") == "arbol"


def test_match_concept_requires_unambiguous_match():
    c1 = {"title": "Gestión X", "territory_key": "t", "archetype_key": "a", "lens_keys": ["l"]}
    c2 = {"title": "gestión x", "territory_key": "t", "archetype_key": "a", "lens_keys": ["l"]}
    entry = {"direccion_original": "Gestión X"}
    concept, why = _match_concept([c1, c2], entry)
    assert concept is None and why.startswith("AMBIGUO")

    concept, why = _match_concept([], entry)
    assert concept is None and why.startswith("SIN_COINCIDENCIA")

    # Refuerzo por territorio+lente+arquetipo cuando el título difiere.
    other = {"title": "Otra cosa", "territory_key": "t2", "archetype_key": "a2", "lens_keys": ["l2"]}
    meta_entry = {"concept_title": "no existe", "territorio": "T", "arquetipo": "A", "lente": "L"}
    concept, why = _match_concept([c1, other], meta_entry)
    assert concept is c1 and why == "territorio+lente+arquetipo"


# ------------------------------------------------------------------- plan
def test_plan_applies_with_local_ids_and_creates_missions(container):
    rid, dcid, targets = _campaign_at_research_pending(container)
    plan = _plan_for(targets)

    preview = apply_reformulation_plan(container, plan, run_id=rid, preview=True)
    assert preview["applied"] == 2 and preview["rejected"] == 0
    assert all(e["result"] == "APLICABLE" for e in preview["entries"])

    result = apply_reformulation_plan(container, plan, run_id=rid, preview=False)
    assert result["applied"] == 2
    assert result["state_after"] == "RESEARCH_PENDING"
    assert result["missions_created"] >= 6  # Fase 1 progresiva: 6 por candidata

    # Trazabilidad local: mission_id/concept_id reales; los foráneos jamás.
    db_concept_ids = {c["id"] for c in container.discovery.campaign_detail(dcid)["concepts"]}
    foreign_ids = {e["plan_concept_id"] for e in result["entries"]}
    assert foreign_ids and foreign_ids.isdisjoint(db_concept_ids)
    for m in result["missions"]:
        assert m["mission_id"] in {x["mission_id"] for x in container.repos.discovery.missions_by_campaign(dcid)}
        assert m["concept_id"] in db_concept_ids


def test_unknown_title_rejected_never_applied(container):
    rid, _, _ = _campaign_at_research_pending(container)
    plan = {"briefs": [{"concept_id": "x", "direccion_original": "Título que no existe en la BD local", "brief": _valid_brief()}]}
    out = apply_reformulation_plan(container, plan, run_id=rid, preview=False)
    assert out["applied"] == 0
    e = out["entries"][0]
    assert e["result"] == "RECHAZADO" and e["reason"].startswith("SIN_COINCIDENCIA")
    # Sin candidatas creadas artificialmente: nada cambió por este brief.
    assert out.get("missions_created", 0) in (0, None) or out.get("missions_created") == 0


def test_invalid_brief_fails_quality_gate(container):
    rid, _, targets = _campaign_at_research_pending(container)
    bad = {k: "" for k in _valid_brief()}  # vacío ⇒ no supera el Quality Gate
    plan = {"briefs": [{"concept_id": "y", "direccion_original": targets[0]["title"], "brief": bad}]}
    out = apply_reformulation_plan(container, plan, run_id=rid, preview=False)
    assert out["applied"] == 0 and out["rejected"] >= 1
    assert any(e["result"] == "RECHAZADO" for e in out["entries"])


def test_reapply_same_plan_is_idempotent(container):
    rid, dcid, targets = _campaign_at_research_pending(container)
    plan = _plan_for(targets)
    first = apply_reformulation_plan(container, plan, run_id=rid, preview=False)
    missions_first = len(first["missions"])

    second = apply_reformulation_plan(container, plan, run_id=rid, preview=False)
    assert second["skipped_idempotent"] == 2
    assert second["applied"] == 0
    # No se crean misiones nuevas al re-aplicar.
    active = [m for m in container.repos.discovery.missions_by_campaign(dcid)
              if m.get("status") != "SUPERSEDED_BY_SEMANTIC_QUALITY_GATE"]
    assert len(active) == missions_first


# ------------------------------------------------- paquete de investigación
def test_package_preview_matches_and_apply_verifies_strictly(container):
    rid, dcid, targets = _campaign_at_research_pending(container)
    plan = _plan_for(targets)
    applied = apply_reformulation_plan(container, plan, run_id=rid, preview=False)
    assert applied["missions_created"] >= 6
    title = next(e["local_title"] for e in applied["entries"] if e["result"] == "APLICADO")

    results = [
        {"concept_title": title, "mission_kind": kind,
         "evidences": [{
             "evidence_type": "demand_signal", "source_name": "Fuente",
             "source_url": "", "captured_at": "", "summary": "s",
             "raw_excerpt": "", "reliability_score": 0.5,
             "independence_group": "g1", "verified": True,
         }]}
        for kind in ACTIVE_KINDS
    ]
    package = {"results": results}

    preview = resolve_research_package(container, package, run_id=rid, apply=False)
    assert preview["matched"] == 6 and preview["ambiguous"] == 0
    assert all(r["status"] == "MATCHED" for r in preview["resolved"])
    # Vista previa no cambia el estado.
    assert container.repos.orchestrator.get_run(rid)["state"] != "RESEARCH_IMPORTED"

    out = resolve_research_package(container, package, run_id=rid, apply=True)
    assert out["matched"] == 6
    assert out["import_transition"]["to_state"] == "RESEARCH_IMPORTED"
    assert container.repos.orchestrator.get_run(rid)["state"] == "RESEARCH_IMPORTED"

    # Evidencia SIN url+fecha+fragmento ⇒ verified=false aunque venga marcada.
    missions = container.repos.discovery.missions_by_campaign(dcid)
    sample = next(m for m in missions
                  if (m.get("target") or {}).get("concept_title") == title)
    saved_rows = container.repos.discovery.mission_results(sample["mission_id"])
    assert saved_rows
    evs = saved_rows[-1]["evidences"]
    assert evs and evs[0]["verified"] is False


def test_package_unknown_title_reports_without_applying(container):
    rid, _, _ = _campaign_at_research_pending(container)
    package = {"results": [{"concept_title": "Nada que coincida", "mission_kind": "DEMAND_REALITY_CHECK"}]}
    out = resolve_research_package(container, package, run_id=rid, apply=True)
    assert out["matched"] == 0
    assert out["resolved"][0]["status"] == "SIN_MISION_LOCAL"
    assert out.get("import_transition") is None


# --------------------------------------------------------------------- API
def test_api_endpoints_return_honest_envelope(client, container):
    d = container.orchestrator.create_real_campaign()
    rid = d["run"]["id"]
    plan = {"version": 1, "briefs": [
        {"concept_id": "foraneo-smoke", "direccion_original": "titulo inexistente en la bd local", "brief": {}}
    ]}
    r = client.post("/api/orchestrator/reformulation-plan",
                    json={"plan": plan, "preview": True, "run_id": rid})
    assert r.status_code == 200
    body = r.json()
    assert body["real_money_moved"] is False
    assert body["entries"][0]["result"] == "RECHAZADO"

    r2 = client.post("/api/orchestrator/research-package",
                     json={"package": {"meta": "smoke", "results": []}, "apply": False, "run_id": rid})
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["real_money_moved"] is False
    assert body2["matched"] == 0
