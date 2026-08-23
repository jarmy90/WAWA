"""Exportaciones descargables de ideas de una campaña (iteración 010).

Archivos:
- business_ideas_campaign_<NNN>.csv         (una fila por idea)
- business_ideas_campaign_<NNN>.json        (completo)
- business_ideas_campaign_<NNN>.md          (legible)
- business_ideas_campaign_<NNN>_finalists.md (resumen de finalistas)
- business_ideas_campaign_<NNN>_research_packets.zip (paquetes de investigación)

No se ocultan ideas descartadas: el CSV/MD incluyen TODAS las ideas con su
motivo de descarte y el aprendizajes.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone

from app.models.orchestrator import RESEARCH_MISSION_KINDS

CSV_COLUMNS = (
    "campaign_id", "concept_id", "title", "territory", "lens", "archetype",
    "problem_hypothesis", "buyer_hypothesis", "proposed_mechanism", "why_now",
    "ai_substitution_class", "ai_substitution_label", "ai_resistance_score",
    "structural_concept_score", "evidence_backed_venture_score", "venture_score",
    "demand_score", "distribution_score", "validation_speed_score", "margin_score",
    "defensibility_score", "originality_score", "evidence_groups", "verified_evidence_count",
    "status", "status_meaning", "current_stage", "passed_dedup", "passed_ai_filter",
    "passed_structural_filter", "entered_shortlist", "tournament_position", "finalist",
    "rejection_stage", "rejection_reason", "blockers", "missing_evidence", "next_action",
    "synthetic_or_real",
)

# Estados que significan que la idea superó un filtro (para las columnas
# passed_* del CSV, sin ambigüedad).
_STRUCTURAL_OK = (
    "STRUCTURAL_FILTER_PASSED", "RESEARCH_CANDIDATE", "RESEARCH_PENDING",
    "EVIDENCE_INSUFFICIENT", "SHORTLISTED_WITH_EVIDENCE", "FINALIST", "EXPERIMENT_READY",
)
_AI_OK = ("AI_FILTER_PASSED",) + _STRUCTURAL_OK
_SHORTLIST_OK = ("RESEARCH_CANDIDATE", "RESEARCH_PENDING", "EVIDENCE_INSUFFICIENT",
                 "SHORTLISTED_WITH_EVIDENCE", "FINALIST", "EXPERIMENT_READY")
_FINALIST_OK = ("FINALIST", "EXPERIMENT_READY")


def _concept_row(campaign_id: str, concept: dict, *, synthetic: bool) -> dict:
    sub = concept.get("substitution") or {}
    ven = concept.get("venture") or {}
    ven_scores = ven.get("scores") or {}
    status = concept.get("status") or "GENERATED_HYPOTHESIS"
    return {
        "campaign_id": campaign_id,
        "concept_id": concept.get("id"),
        "title": concept.get("title"),
        "territory": concept.get("territory_key"),
        "lens": ", ".join(concept.get("lens_keys") or []),
        "archetype": concept.get("archetype_key"),
        "problem_hypothesis": concept.get("problem_hypothesis"),
        "buyer_hypothesis": concept.get("buyer_hypothesis"),
        "proposed_mechanism": concept.get("mechanism"),
        "why_now": concept.get("why_now"),
        "ai_substitution_class": sub.get("classification"),
        "ai_substitution_label": concept.get("ai_substitution_label") or sub.get("classification"),
        "ai_resistance_score": sub.get("ai_resistance_score"),
        "structural_concept_score": concept.get("structural_concept_score"),
        "evidence_backed_venture_score": concept.get("evidence_backed_venture_score"),
        "venture_score": ven.get("final_score"),
        "demand_score": ven_scores.get("proven_demand"),
        "distribution_score": ven_scores.get("distribution"),
        "validation_speed_score": ven_scores.get("validation_speed"),
        "margin_score": ven_scores.get("gross_margin"),
        "defensibility_score": ven_scores.get("defensibility"),
        "originality_score": ven_scores.get("originality"),
        "evidence_groups": concept.get("evidence_groups"),
        "verified_evidence_count": concept.get("verified_evidence_count"),
        "status": status,
        "status_meaning": concept.get("status_meaning"),
        "current_stage": concept.get("phase"),
        "passed_dedup": "yes" if status != "CONCEPTUAL_CLONE" else "no",
        "passed_ai_filter": "yes" if status in _AI_OK else "no",
        "passed_structural_filter": "yes" if status in _STRUCTURAL_OK else "no",
        "entered_shortlist": "yes" if status in _SHORTLIST_OK else "no",
        "tournament_position": concept.get("tournament_rank"),
        "finalist": "yes" if status in _FINALIST_OK else "no",
        "rejection_stage": concept.get("rejection_stage"),
        "rejection_reason": concept.get("rejection_reason"),
        "blockers": "; ".join(concept.get("blockers") or []),
        "missing_evidence": concept.get("missing_evidence"),
        "next_action": concept.get("next_action"),
        "synthetic_or_real": "synthetic" if synthetic else "real",
    }


def _concepts(detail: dict) -> list[dict]:
    return detail.get("concepts") or []


def build_csv(detail: dict, *, synthetic: bool) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    campaign_id = (detail.get("campaign") or {}).get("id", "")
    for concept in _concepts(detail):
        writer.writerow(_concept_row(campaign_id, concept, synthetic=synthetic))
    return buf.getvalue()


def build_json(detail: dict, *, synthetic: bool, run: dict | None = None) -> str:
    campaign = detail.get("campaign") or {}
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "campaign": campaign,
        "run": run,
        "synthetic_or_real": "synthetic" if synthetic else "real",
        "summary": {
            "total": len(_concepts(detail)),
            "blocked": sum(1 for c in _concepts(detail) if c.get("status") in ("COMMODITY_BLOCKED", "RECOMBINATION_INCOHERENT")),
            "needs_reformulation": sum(1 for c in _concepts(detail) if c.get("status") == "NEEDS_REFORMULATION"),
            "shortlisted": sum(1 for c in _concepts(detail) if c.get("status") in _SHORTLIST_OK),
            "finalists": sum(1 for c in _concepts(detail) if c.get("status") in _FINALIST_OK),
        },
        "concepts": _concepts(detail),
        "comparisons": detail.get("comparisons") or [],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_markdown(detail: dict, *, synthetic: bool) -> str:
    campaign = detail.get("campaign") or {}
    concepts = _concepts(detail)
    blocked = [c for c in concepts if c.get("status") in ("COMMODITY_BLOCKED", "RECOMBINATION_INCOHERENT", "CONCEPTUAL_CLONE", "DIVERSITY_ELIMINATED")]
    reform = [c for c in concepts if c.get("status") == "NEEDS_REFORMULATION"]
    shortlisted = [c for c in concepts if c.get("status") in _SHORTLIST_OK]
    finalists = [c for c in concepts if c.get("status") in _FINALIST_OK]
    lines: list[str] = []
    lines.append(f"# Ideas de campaña — {campaign.get('title', 'Sin título')}")
    lines.append("")
    lines.append("## 1. Resumen de campaña")
    lines.append(f"- Campaña: `{campaign.get('id')}` · fase: {campaign.get('phase')} · diversidad: {campaign.get('diversity', 0.0):.2f}")
    lines.append(f"- Origen: {'SINTÉTICO (prueba)' if synthetic else 'REAL'}")
    lines.append("")
    lines.append("## 2. Embudo")
    lines.append(f"- Conceptos iniciales: {len(concepts)}")
    lines.append(f"- Bloqueados/descartados: {len(blocked)}")
    lines.append(f"- Necesitan reformulación: {len(reform)}")
    lines.append(f"- Candidatas concretas / shortlist: {len(shortlisted)}")
    lines.append(f"- Finalistas: {len(finalists)}")
    lines.append("")
    lines.append("## 3. Todas las ideas")
    for i, c in enumerate(concepts, 1):
        sub = c.get("substitution") or {}
        ven = c.get("venture") or {}
        lines.append(f"{i}. **{c.get('title')}** `[{c.get('status')}]`")
        lines.append(f"   - Problema (hipótesis): {c.get('problem_hypothesis')}")
        lines.append(f"   - Comprador (hipótesis): {c.get('buyer_hypothesis')}")
        lines.append(f"   - Mecanismo: {c.get('mechanism')}")
        lines.append(f"   - Territorio: {c.get('territory_key')} · lente(s): {', '.join(c.get('lens_keys') or [])} · arquetipo: {c.get('archetype_key')}")
        lines.append(f"   - Sustitución IA: {c.get('ai_substitution_label') or sub.get('classification')} (resistencia {sub.get('ai_resistance_score')})")
        lines.append(f"   - Puntuación estructural: {c.get('structural_concept_score')} · Puntuación con evidencia: {c.get('evidence_backed_venture_score')}")
        lines.append(f"   - Qué significa: {c.get('status_meaning')}")
        if c.get('rejection_reason'):
            lines.append(f"   - Motivo: {c.get('rejection_reason')}")
        if c.get('missing_evidence') and c.get('missing_evidence') != '—':
            lines.append(f"   - Qué falta: {c.get('missing_evidence')}")
        if c.get('next_action'):
            lines.append(f"   - Próxima acción: {c.get('next_action')}")
    lines.append("")
    lines.append("## 4. Ideas descartadas y motivo")
    if blocked:
        for c in blocked:
            lines.append(f"- **{c.get('title')}** `[{c.get('status')}]` — motivo: {c.get('rejection_reason') or 'bloqueador interno'}")
    else:
        lines.append("- Ninguna descartada.")
    lines.append("")
    lines.append("## 4b. Ideas que necesitan reformulación")
    if reform:
        for c in reform:
            lines.append(f"- **{c.get('title')}** — falta: {c.get('missing_evidence') or 'brief concreto'}")
    else:
        lines.append("- Ninguna.")
    lines.append("")
    lines.append("## 5. Shortlist")
    for c in shortlisted:
        lines.append(f"- {c.get('title')} (estado {c.get('status')})")
    lines.append("")
    lines.append("## 6. Finalistas")
    if finalists:
        for c in finalists:
            lines.append(f"- **{c.get('title')}** — estructural {c.get('structural_concept_score')} · con evidencia {c.get('evidence_backed_venture_score')}")
    else:
        lines.append("- Ninguno (0 finalistas es un resultado válido: no se fuerzan).")
    lines.append("")
    lines.append("## 7. Comparación (torneo)")
    for cmp_ in (detail.get("comparisons") or [])[:20]:
        lines.append(f"- {cmp_.get('winner_title')} > {cmp_.get('loser_title')} ({cmp_.get('criteria')})")
    lines.append("")
    lines.append("## 8. Recomendación y próximo paso")
    lines.append("- Pendiente de investigación externa real (RESEARCH_PENDING) antes de promover finalistas.")
    lines.append("")
    return "\n".join(lines) + "\n"


def build_finalists_markdown(detail: dict, *, synthetic: bool, committee: list[dict] | None = None) -> str:
    concepts = [c for c in _concepts(detail) if c.get("status") in _FINALIST_OK]
    lines: list[str] = []
    lines.append("# Finalistas — resumen")
    lines.append("")
    for i, c in enumerate(concepts, 1):
        ven = c.get("venture") or {}
        lines.append(f"## {i}. {c.get('title')}")
        lines.append(f"- Problema (hipótesis): {c.get('problem_hypothesis')}")
        lines.append(f"- Comprador (hipótesis): {c.get('buyer_hypothesis')}")
        lines.append(f"- Mecanismo: {c.get('mechanism')}")
        lines.append(f"- Venture Score: {ven.get('final_score')} · Resistencia IA: {(c.get('substitution') or {}).get('ai_resistance_score')}")
        lines.append("")
    if committee:
        lines.append("## Comité")
        for row in committee:
            syn = row.get("synthesis") or {}
            lines.append(f"- {row.get('title')}: score interno {row.get('final_score')} · revisiones {row.get('reviews_count')} · consenso {syn.get('consensus_level')}")
        lines.append("")
    if not concepts:
        lines.append("- Sin finalistas: ninguna idea superó los umbrales (aprendizaje conservado).")
    return "\n".join(lines) + "\n"


def build_research_packets_zip(detail: dict, missions_by_concept: dict[str, list[dict]], missions_markdown: dict[str, str]) -> bytes:
    """Zip con los paquetes de investigación de cada candidata."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for concept_id, missions in missions_by_concept.items():
            for m in missions:
                md = missions_markdown.get(m.get("mission_id"), "")
                if md:
                    zf.writestr(f"candidate_{concept_id}/{m.get('kind', 'mission')}.md", md)
    return buf.getvalue()
