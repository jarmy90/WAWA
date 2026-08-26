"""Importación operativa de la macrooperación (iteración 017).

Dos operaciones públicas:

1. :func:`apply_reformulation_plan` — aplica un plan de reformulación
   (``reformulaciones_briefs.json``) a la campaña REAL local. Los
   ``concept_id`` del plan pertenecen a una reproducción aislada y NUNCA se
   insertan directamente: los conceptos locales se localizan por título
   normalizado y, como refuerzo, por territorio/lente/arquetipo. Se exige
   coincidencia inequívoca: 0 o ≥1 candidatas ambiguas ⇒ rechazo registrado,
   nunca aplicación dudosa. Después deja que el orquestador haga lo suyo
   (Quality Gate ya aplicado por brief, torneo ≤3, misiones Fase 1 con IDs
   LOCALES). Es idempotente: re-aplicar el mismo plan no duplica nada.

2. :func:`resolve_research_package` — asocia un paquete de investigación
   portable (generado fuera, p. ej. en Freebuff) con las misiones locales vía
   MAPEO ESTABLE (título de concepto normalizado + mission_kind + phase +
   ordinal), nunca por mission_id foráneo. Modo preview devuelve las
   asociaciones sin aplicar; modo apply delega en
   ``CampaignOrchestrator.import_research`` (que conserva raw, deduplica y
   solo verifica con URL+fecha+fragmento).

100% offline: ninguna función llama a la red.
"""
from __future__ import annotations

import unicodedata
from typing import Any

PHASE1_KINDS = (
    "DEMAND_REALITY_CHECK",
    "BUYER_BUDGET_CHECK",
    "CURRENT_ALTERNATIVE_CHECK",
    "DISTRIBUTION_ACCESS_CHECK",
    "COMPETITOR_EQUIVALENT_SEARCH",
    "GENERAL_AI_SUBSTITUTION_CHECK",
)


def normalize_title(title: str) -> str:
    """Título normalizado estable: minúsculas, sin acentos, espacios colapsados."""
    text = unicodedata.normalize("NFKD", str(title or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().split())


def _concept_keys(concept: dict[str, Any]) -> set[str]:
    keys = {normalize_title(concept.get("title") or "")}
    lens = concept.get("lens_keys")
    if isinstance(lens, str):
        import json as _json

        try:
            lens = _json.loads(lens)
        except Exception:  # noqa: BLE001
            lens = []
    for lens_key in lens or []:
        keys.add(normalize_title(f"{concept.get('territory_key')}|{lens_key}|{concept.get('archetype_key')}"))
    return {k for k in keys if k}


# --------------------------------------------------------------------------
# BLOQUE 1: aplicar el plan de reformulación a la campaña REAL local
# --------------------------------------------------------------------------

def _find_active_run(container: Any, run_id: str | None) -> dict[str, Any]:
    if run_id:
        run = container.repos.orchestrator.get_run(run_id)
        if run is None:
            raise ValueError(f"Ejecución desconocida: {run_id}")
        return run
    run = container.orchestrator.current_run()
    if run is None:
        raise ValueError("No existe una campaña real activa. Pulsa INICIAR CAMPAÑA REAL primero.")
    return run


def _match_concept(concepts: list[dict[str, Any]], entry: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """Devuelve (concepto, motivo). Coincidencia INEQUÍVoca o None."""
    wanted_title = normalize_title(entry.get("direccion_original") or entry.get("concept_title") or "")
    by_title = [c for c in concepts if normalize_title(c.get("title") or "") == wanted_title] if wanted_title else []
    if len(by_title) > 1:
        return None, f"AMBIGUO: {len(by_title)} conceptos comparten el título normalizado"
    if len(by_title) == 1:
        return by_title[0], "title"
    # Refuerzo: territorio + lente + arquetipo exactos.
    territory = normalize_title(entry.get("territorio") or "")
    archetype = normalize_title(entry.get("arquetipo") or "")
    lens = normalize_title(entry.get("lente") or "")
    meta_hits: list[dict[str, Any]] = []
    for c in concepts:
        c_lens = c.get("lens_keys")
        if isinstance(c_lens, str):
            import json as _json

            try:
                c_lens = _json.loads(c_lens)
            except Exception:  # noqa: BLE001
                c_lens = []
        if (
            territory
            and normalize_title(c.get("territory_key") or "") == territory
            and archetype
            and normalize_title(c.get("archetype_key") or "") == archetype
            and lens
            and any(normalize_title(str(k)) == lens for k in (c_lens or []))
        ):
            meta_hits.append(c)
    if len(meta_hits) == 1:
        return meta_hits[0], "territorio+lente+arquetipo"
    if len(meta_hits) > 1:
        return None, f"AMBIGUO: {len(meta_hits)} conceptos comparten territorio+lente+arquetipo"
    return None, "SIN_COINCIDENCIA: ningún concepto local coincide de forma inequívoca"


def apply_reformulation_plan(
    container: Any,
    plan: dict[str, Any],
    *,
    run_id: str | None = None,
    preview: bool = False,
) -> dict[str, Any]:
    """Aplica (o previsualiza) un plan de reformulación sobre la campaña local.

    Nunca usa los concept_id del plan: son de una reproducción aislada.
    """
    briefs = (plan or {}).get("briefs")
    if not isinstance(briefs, list) or not briefs:
        raise ValueError("El plan no contiene 'briefs' (lista).")

    run = _find_active_run(container, run_id)
    dcid = run["discovery_campaign_id"]
    concepts = container.repos.discovery.concepts_by_campaign(dcid)

    report_entries: list[dict[str, Any]] = []
    applied = skipped = rejected = 0
    for entry in briefs:
        concept, how = _match_concept(concepts, entry)
        item: dict[str, Any] = {
            "plan_concept_id": entry.get("concept_id"),  # solo trazabilidad, NUNCA se inserta
            "matched_by": None,
            "local_concept_id": None,
            "local_title": None,
            "result": None,
        }
        if concept is None:
            rejected += 1
            item.update(result="RECHAZADO", reason=how)
            report_entries.append(item)
            continue
        item["matched_by"] = how
        item["local_concept_id"] = concept["id"]
        item["local_title"] = concept["title"]
        incoming = {k: str(v).strip() for k, v in (entry.get("brief") or {}).items() if str(v).strip()}
        stored = {k: str(v).strip() for k, v in (concept.get("brief") or {}).items() if str(v).strip()}
        if stored:
            # El concepto ya tiene Opportunity Brief: idempotente si es IDÉNTICO
            # (cualquier estado posterior: RESEARCH_CANDIDATE/RESEARCH_PENDING…);
            # distinto ⇒ rechazo honesto, nunca sobrescritura silenciosa.
            if stored == incoming:
                skipped += 1
                item["result"] = "YA_APLICADO_IDEMPOTENTE"
            else:
                rejected += 1
                item["result"] = "RECHAZADO"
                item["reason"] = "El concepto ya tiene un Opportunity Brief distinto"
            report_entries.append(item)
            continue
        if preview:
            applied += 1
            item["result"] = "APLICABLE"
            report_entries.append(item)
            continue
        try:
            res = container.discovery.complete_opportunity_brief(concept["id"], entry.get("brief") or {})
            applied += 1
            item["result"] = "APLICADO"
            item["structural_score"] = ((res.get("venture") or {}).get("final_score"))
        except Exception as exc:  # noqa: BLE001
            rejected += 1
            item["result"] = "RECHAZADO"
            item["reason"] = f"Quality Gate: {exc}"
        report_entries.append(item)

    outcome: dict[str, Any] = {
        "run_id": run["id"],
        "discovery_campaign_id": dcid,
        "preview": preview,
        "total_briefs": len(briefs),
        "applied": applied,
        "skipped_idempotent": skipped,
        "rejected": rejected,
        "entries": report_entries,
    }
    if preview or (applied == 0 and rejected + skipped == len(briefs)):
        return outcome

    # El orquestador hace el resto de forma determinista: torneo (≤3),
    # promoción y misiones Fase 1 con IDs LOCALES.
    detail = container.orchestrator.advance(run["id"])
    planned_missions: list[dict[str, Any]] = []
    for t in container.repos.orchestrator.transitions_for(run["id"]):
        if t.get("to_state") == "RESEARCH_PLANNED":
            outs = t.get("outputs") or {}
            ms = outs.get("missions") or []
            if len(ms) >= len(planned_missions):
                planned_missions = list(ms)
    outcome.update(
        state_after=detail["run"]["state"],
        next_action=detail.get("next_action"),
        selected_candidates=(detail.get("outputs") or {}).get("selected_candidates")
        or [e["local_concept_id"] for e in report_entries if e.get("result") == "APLICADO"],
        missions_created=len(planned_missions),
        missions=planned_missions,
    )
    return outcome


# --------------------------------------------------------------------------
# BLOQUE 3: resolver un paquete de investigación portable contra misiones locales
# --------------------------------------------------------------------------

def _stable_key(concept_title: str, kind: str, phase: str = "phase1", ordinal: int = 1) -> str:
    return f"{normalize_title(concept_title)}|{kind}|{phase}|{ordinal}"


def resolve_research_package(
    container: Any,
    package: dict[str, Any],
    *,
    run_id: str | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    """Asocia resultados del paquete portable a misiones LOCALES por mapeo
    estable (concept title normalizado + mission_kind + phase + ordinal).
    Asociaciones ambiguas se rechazan; nunca se adivina."""
    run = _find_active_run(container, run_id)
    dcid = run["discovery_campaign_id"]
    missions = [
        m for m in container.repos.discovery.missions_by_campaign(dcid)
        if m.get("status") != "SUPERSEDED_BY_SEMANTIC_QUALITY_GATE"
    ]
    by_key: dict[str, list[dict[str, Any]]] = {}
    for m in missions:
        target = m.get("target") or {}
        key = _stable_key(target.get("concept_title") or "", m.get("kind") or "")
        by_key.setdefault(key, []).append(m)

    resolved: list[dict[str, Any]] = []
    payloads: list[dict[str, Any]] = []
    matched = ambiguous = unmatched = 0
    for entry in (package or {}).get("results") or []:
        title = entry.get("concept_title") or (entry.get("candidate") or {}).get("specific_name")
        kind = entry.get("mission_kind")
        phase = entry.get("phase", "phase1")
        ordinal = int(entry.get("ordinal", 1))
        key = _stable_key(title or "", kind or "", phase, ordinal)
        hits = by_key.get(key, [])
        item: dict[str, Any] = {"stable_key": key, "mission_kind": kind, "candidate": title}
        if len(hits) == 1:
            matched += 1
            mission = hits[0]
            item.update(status="MATCHED", local_mission_id=mission["mission_id"])
            if apply:
                payloads.append({
                    "mission_id": mission["mission_id"],
                    "evidences": entry.get("evidences") or [],
                    "competitors": entry.get("competitors") or [],
                    "buyer_confirmed": entry.get("buyer_confirmed"),
                    "notes": entry.get("notes"),
                })
        elif len(hits) > 1:
            ambiguous += 1
            item.update(status="RECHAZADO_AMBIGUO", reason=f"{len(hits)} misiones comparten la clave estable")
        else:
            unmatched += 1
            item.update(status="SIN_MISION_LOCAL", reason="Ninguna misión local con esa clave estable")
        resolved.append(item)

    outcome: dict[str, Any] = {
        "run_id": run["id"],
        "preview": not apply,
        "total_results": len(resolved),
        "matched": matched,
        "ambiguous": ambiguous,
        "unmatched": unmatched,
        "resolved": resolved,
    }
    if apply and payloads:
        transition = container.orchestrator.import_research(run["id"], payloads)
        outcome["import_transition"] = {
            "to_state": transition.get("to_state"),
            "reason": transition.get("reason"),
        }
        outcome["state_after"] = container.repos.orchestrator.get_run(run["id"])["state"]
    elif apply and not payloads:
        outcome["note"] = "Nada aplicable: ninguna coincidencia inequívoca."
    return outcome
