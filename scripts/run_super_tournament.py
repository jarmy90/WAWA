#!/usr/bin/env python3
"""Super-torneo (iteración 018): de todas las candidatas y reformulaciones a
un máximo de 3 prioridades de investigación.

Ejecuta el torneo 100 % determinista (sin LLM) sobre la campaña activa local:

    python3 scripts/run_super_tournament.py [--out-dir deliverables/operacion_super_torneo_2026-08-26]

Salidas:
- super_torneo_018_resultado.json     — resultado completo (ganadoras, descartes).
- plan_investigacion_portable_018.json — briefs ganadores + 6 misiones Fase 1
  por candidata, con consultas ES/EN, fuentes, contradicciones y kill
  conditions. Los IDs son LOCALES; nunca contiene identificadores foráneos.

Garantías:
- La puntuación es prioridad de investigación; proven_demand y
  evidence_backed_venture_score NO cambian.
- Cero ganadoras es un resultado válido y se registra.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.container import build_container  # noqa: E402
from app.services.discovery import RESEARCH_PHASE1_KINDS  # noqa: E402

MISSION_SPECS: dict[str, dict[str, object]] = {
    "DEMAND_REALITY_CHECK": {
        "queries_es": ['"{problema}" foro OR reddit', '"{síntoma}" quejas "{sector}"', '"{dolor}" sin solución 2026'],
        "queries_en": ['"{problem}" forum OR reddit complaints', '"{pain point}" small business "{sector}"', 'who pays to solve "{problem}"'],
        "primary_sources": ["foros sectoriales", "grupos de colegios profesionales", "reviews de la alternativa actual"],
        "contradictions_to_seek": ["la alternativa actual funciona bien", "el problema no aparece en ninguna fuente primaria"],
        "kill_condition": "0 manifestaciones independientes con URL+fecha+fragmento tras 3 consultas distintas.",
    },
    "BUYER_BUDGET_CHECK": {
        "queries_es": ['"{comprador}" presupuesto "{servicio}"', 'cuánto cobran por "{servicio}" "{sector}"', 'honorarios "{comprador}"'],
        "queries_en": ['"{buyer}" budget "{service}"', 'how much do "{buyer}" pay for "{service}"', 'pricing benchmark "{sector}"'],
        "primary_sources": ["tarifarios públicos", "anuncios de servicios", "encuestas sectoriales"],
        "contradictions_to_seek": ["el pago sale de un presupuesto inexistente", "el servicio se paga con dinero de la casa del profesional"],
        "kill_condition": "Ningún comprador real con presupuesto identificable; solo usuarios sin dinero.",
    },
    "CURRENT_ALTERNATIVE_CHECK": {
        "queries_es": ['alternativas a "{servicio}" "{sector}"', 'cómo se hace hoy "{tarea}" sin herramienta', 'plantillas "{tarea}" gratis'],
        "queries_en": ['alternative to "{service}" "{sector}"', 'how do people do "{task}" manually today', 'free template "{task}"'],
        "primary_sources": ["herramientas existentes", "plantillas", "profesionales que documentan su método"],
        "contradictions_to_seek": ["ya existe una herramienta gratis que resuelve el 80%", "el método manual es rápido y barato"],
        "kill_condition": "Existe alternativa gratuita que cubre el caso principal sin fricción.",
    },
    "DISTRIBUTION_ACCESS_CHECK": {
        "queries_es": ['canal para llegar a "{comprador}"', 'asociaciones de "{comprador}" España', 'colegios profesionales "{sector}"'],
        "queries_en": ['where do "{buyer}" gather online', 'associations "{buyer}" "{country}"', 'communities "{sector}" professionals'],
        "primary_sources": ["colegios/asociaciones", "grupos de LinkedIn/WhatsApp", "eventos sectoriales"],
        "contradictions_to_seek": ["el comprador no está accesible sin pago/permiso", "no existe canal de bajo coste"],
        "kill_condition": "No hay forma de llegar a 20 compradores sin coste relevante o spam.",
    },
    "COMPETITOR_EQUIVALENT_SEARCH": {
        "queries_es": ['competidores "{servicio}" "{sector}"', 'empresas que hacen "{servicio}" para "{comprador}"', 'precios "{servicio}" "{sector}"'],
        "queries_en": ['competitors "{service}" "{sector}"', 'companies offering "{service}" to "{buyer}"', 'pricing "{service}"'],
        "primary_sources": ["competidores directos", "marketplaces de servicios", "directorios"],
        "contradictions_to_seek": ["un competidor dominante con foso", "el mercado ya está saturado de ofertas idénticas"],
        "kill_condition": "Existen 3+ competidores directos con oferta equivalente y tracción.",
    },
    "GENERAL_AI_SUBSTITUTION_CHECK": {
        "queries_es": ['ChatGPT para "{tarea}" "{sector}"', 'hacer "{tarea}" con IA gratis', 'prompt para "{tarea}"'],
        "queries_en": ['ChatGPT "{task}" "{sector}" workflow', 'can AI do "{task}" for free', 'automate "{task}" prompt'],
        "primary_sources": ["pruebas reales de prompt", "documentación de integraciones", "foros de usuarios de IA"],
        "contradictions_to_seek": ["un prompt resuelve el 80% sin workflow", "no hay parte que requiera memoria/integración"],
        "kill_condition": "Una IA generalista resuelve el caso principal con un único prompt.",
    },
}


def _build_portable_plan(container: Any, result: dict[str, Any]) -> dict[str, Any]:
    plan = {
        "operacion": "super_torneo_018",
        "fecha": date.today().isoformat(),
        "origen": "WAWA iteración 018 — torneo determinista",
        "advertencia": (
            "Los concept_id de este plan pertenecen a la instalación LOCAL que lo "
            "generó. Si se aplica a otra instalación, localizar por título "
            "normalizado + territorio + lente + arquetipo (nunca insertar IDs)."
        ),
        "winners": [],
        "briefs": [],
    }
    for w in result.get("winners", []):
        cid = w.get("concept_id")
        concept = container.repos.discovery.get_concept(cid) if cid else None
        brief = (concept or {}).get("brief") or {}
        winner = {
            "local_concept_id": cid,
            "title": w.get("title"),
            "status": w.get("status"),
            "super_tournament_score": w.get("super_tournament_score"),
            "score_is_priority_not_evidence": True,
            "brief": brief,
            "missions_fase1": [],
        }
        for i, kind in enumerate(RESEARCH_PHASE1_KINDS, start=1):
            spec = MISSION_SPECS.get(kind, {})
            winner["missions_fase1"].append({
                "kind": kind,
                "phase": 1,
                "ordinal": i,
                "objective": spec.get("objective") or f"Misión {kind} para {w.get('title')}",
                "queries_es": spec.get("queries_es"),
                "queries_en": spec.get("queries_en"),
                "primary_sources": spec.get("primary_sources"),
                "contradictions_to_seek": spec.get("contradictions_to_seek"),
                "kill_condition": spec.get("kill_condition"),
                "no_invention_rule": "NO inventar demanda, precios, competidores ni estadísticas. Sin dato ⇒ null y DESCONOCIDO.",
                "evidence_requires": "URL + fecha de consulta + fragmento exacto.",
            })
        plan["winners"].append(winner)
        plan["briefs"].append({
            "concept_id": cid,  # solo trazabilidad; el importador nunca lo inserta
            "direccion_original": concept.get("title") if concept else w.get("title"),
            "territorio": (concept or {}).get("territory_key"),
            "lente": ((concept or {}).get("lens_keys") or [None])[0] if isinstance((concept or {}).get("lens_keys"), list) else None,
            "arquetipo": (concept or {}).get("archetype_key"),
            "brief": brief,
        })
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Super-torneo determinista (iteración 018).")
    parser.add_argument("--out-dir", default="deliverables/operacion_super_torneo_2026-08-26")
    args = parser.parse_args()

    container = build_container(get_settings())
    result = container.super_tournament.run(actor="system")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "super_torneo_018_resultado.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    plan = _build_portable_plan(container, result)
    (out_dir / "plan_investigacion_portable_018.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "ok": result["ok"],
        "campaign": result.get("campaign_title"),
        "entries": result.get("total_entries"),
        "winners": [(w["title"], w["super_tournament_score"]) for w in result.get("winners", [])],
        "rejected_incomplete_brief": len(result.get("rejected_incomplete_brief", [])),
        "rejected_low_score": len(result.get("rejected_low_score", [])),
        "eliminated_over_slots": len(result.get("eliminated_over_slots", [])),
        "challengers_without_brief": result.get("challengers_without_brief_count"),
        "zero_winners_is_valid": result.get("zero_winners_is_valid"),
    }, ensure_ascii=False, indent=2))
    print(f"[OK] Resultado: {out_dir / 'super_torneo_018_resultado.json'}")
    print(f"[OK] Plan portable: {out_dir / 'plan_investigacion_portable_018.json'}")
    container.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
