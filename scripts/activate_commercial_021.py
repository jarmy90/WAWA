#!/usr/bin/env python3
"""Iteración 021 — Importación de investigación Fase 1 REAL (URL+fecha+fragmento).

Lee ``deliverables/operacion_activacion_comercial_2026-08-26/investigacion_fase1_021.json``
e importa cada resultado contra su misión local por ``concept_id + kind``,
adjunta la evidencia verificada a la oportunidad promovida, persiste
``opportunity_id`` en el ``target`` de la misión y reevalúa las candidatas
con evidencia. Reutilizable e idempotente por misión.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.container import build_container  # noqa: E402
from app.models.discovery import MissionIn  # noqa: E402


def main() -> int:
    data_path = Path("deliverables/operacion_activacion_comercial_2026-08-26/investigacion_fase1_021.json")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    campaign_id = data["campaign_id"]

    container = build_container(get_settings())
    discovery = container.discovery
    repos = container.repos

    missions_by_concept_kind: dict[tuple[str, str], str] = {}
    for mission in repos.discovery.missions_by_campaign(campaign_id):
        target = mission.get("target") or {}
        cid = target.get("concept_id")
        kind = mission.get("kind") or target.get("kind")
        if cid and kind and mission.get("status") not in ("SUPERSEDED_BY_SEMANTIC_QUALITY_GATE", "CANCELLED"):
            missions_by_concept_kind[(cid, kind)] = mission["mission_id"]

    summary = []
    for concept in data["payloads"]:
        concept_id = concept["concept_id"]
        opp_id = concept["opportunity_id"]
        imported, attached, skipped = 0, 0, []
        for mission in concept["missions"]:
            kind = mission["kind"]
            mission_id = missions_by_concept_kind.get((concept_id, kind))
            if mission_id is None:
                skipped.append(f"{kind}:sin_mission")
                continue
            payload = {
                "mission_id": mission_id,
                "evidences": mission.get("evidences") or [],
                "competitors": mission.get("competitors") or [],
                "buyer_confirmed": mission.get("buyer_confirmed"),
                "notes": mission.get("notes"),
                "verified": False,
            }
            result = discovery.import_mission_result(mission_id, MissionIn(**payload))
            attach = discovery.attach_mission_evidence(opp_id, mission_id)
            imported += 1
            attached += attach.get("evidences_attached", 0)
            # Persistir el vínculo oportunidad en el target (readiness inequívoco).
            row = repos.discovery.get_mission(mission_id)
            target = dict(row.get("target") or {})
            target["opportunity_id"] = opp_id
            repos.discovery.update_mission_target(mission_id, target)
        # Reevaluación con evidencia (determinista, sin LLM).
        concept_row = repos.discovery.get_concept(concept_id)
        venture = discovery._evaluate_venture(concept_row, campaign_id)  # type: ignore[attr-defined]
        summary.append(
            {
                "title": concept["title"][:70],
                "concept_id": concept_id,
                "opportunity_id": opp_id,
                "missions_imported": imported,
                "evidences_attached": attached,
                "skipped": skipped,
                "structural": venture.get("venture", {}).get("structural_concept_score"),
                "evidence_backed": venture.get("venture", {}).get("evidence_backed_venture_score"),
                "has_verified_evidence": venture.get("venture", {}).get("has_verified_evidence"),
                "blockers": venture.get("venture", {}).get("blockers"),
            }
        )

    print(json.dumps({"campaign_id": campaign_id, "summary": summary}, ensure_ascii=False, indent=1))
    container.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
