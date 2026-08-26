#!/usr/bin/env python3
"""Benchmark reproducible de OX Alpha (iteración 018).

Ejecuta las 4 tareas del benchmark (reformulación, coherencia, red-team,
comparación de variantes) sobre expedientes FIJOS y puntúa con la rúbrica
determinista de ``app/scoring/ox_alpha_benchmark.py``:

- Brazo A: respuesta determinista local (baseline, sin llamadas).
- Brazo C: OX Alpha vía DeepReasoningService SOLO si la puerta está
  ``AVAILABLE`` (slug verificado + ventana abierta + gateway activo).
- B/D: estado del proveedor correspondiente (pending si no disponible).

Reglas:
- NUNCA fabrica respuestas para el brazo C: si la puerta está cerrada se
  registra el motivo y el veredicto es OX_ALPHA_UNVERIFIED/INCONCLUSIVE.
- Ningún resultado es evidencia de mercado.

Uso:  python3 scripts/benchmark_ox_alpha.py [--out deliverables/.../ox_alpha_benchmark_018.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.container import build_container  # noqa: E402
from app.core.ox_alpha import ox_alpha_status  # noqa: E402
from app.scoring.ox_alpha_benchmark import BENCHMARK_TASKS, benchmark_verdict, score_task_response  # noqa: E402

# Expedientes fijos y diversos (NO son evidencia de mercado; son inputs de test).
CONCEPTS = {
    "reformulation": {
        "title": "Capa de confianza para soledad invisible administrativa",
        "problem_hypothesis": "Personas con trabajo administrativo invisible no reciben reconocimiento ni tienen dónde externalizarlo.",
        "mechanism_hypothesis": "Plataforma que conecta a quien tiene tareas administrativas con quien puede hacerlas.",
        "buyer_hypothesis": "Profesionales sobrecargados.",
    },
    "coherence_check": {
        "title": "Gamificación para urgencias veterinarias",
        "problem_hypothesis": "Las urgencias veterinarias requieren triaje rápido.",
        "mechanism_hypothesis": "Sistema de gamificación de triaje.",
        "territory_key": "urgent_care",
        "lens_key": "GAMIFICATION",
        "archetype_key": "COMMUNITY_PLATFORM",
    },
    "red_team": {
        "title": "Cuaderno de cuotas y servicios para comunidades con administrador de fincas",
        "problem_hypothesis": "Las comunidades no pueden contrastar lo que cobra y entrega su administrador.",
        "buyer_hypothesis": "Juntas de comunidades de propietarios de 10-40 viviendas.",
        "outcome_hypothesis": "Dossier anual comparativo.",
        "brief": {
            "specific_name": "Cuaderno de cuotas para comunidades de propietarios",
            "buyer": "Presidentes de comunidades de 10-40 viviendas en España",
            "concrete_deliverable": "Cuaderno anual con cuota, servicios y facturas",
        },
    },
    "variation_comparison": [
        {"concept_id": "11111111111111111111111111111111", "title": "Benchmark de tarifas para clínicas dentales", "brief": {"buyer": "Gerentes de clínicas de 2-5 dentistas", "concrete_deliverable": "Informe de percentiles por provincia"}},
        {"concept_id": "22222222222222222222222222222222", "title": "Checklist RGPD para despachos pequeños", "brief": {"buyer": "Socios de despachos de 2-10 empleados", "concrete_deliverable": "Expediente documental RGPD"}},
        {"concept_id": "33333333333333333333333333333333", "title": "Preparación del modelo 232 para asesorías", "brief": {"buyer": "Asesorías de 1-5 personas", "concrete_deliverable": "Borradero del modelo 232 por cliente"}},
    ],
}


def _baseline(task: str) -> dict:
    """Brazo A: respuesta determinista local (reglas, no LLM)."""
    if task == "reformulation":
        return {"variants": [
            {
                "buyer": "Titulares de despachos de abogados con 2-10 empleados en España",
                "observable_problem": "No tienen el registro de actividades de tratamiento completo y arriesgan sanciones que no pueden afrontar.",
                "concrete_deliverable": "Checklist guiado que genera el registro y la política de privacidad.",
                "causal_chain": "La norma exige el registro; sin él hay sanción; el despacho no tiene quién lo haga.",
                "first_distribution_channel": "Colegios de abogados provinciales y asociaciones de despachos.",
                "test_in_48_hours": "Enviar la checklist por correo a 10 despachos y medir respuestas.",
                "generic_ai_limitation": "Requiere conocer el censo de despachos y su contexto normativo específico.",
                "assumptions": "Los despachos no tienen el registro; un checklist reduce el trabajo a una tarde.",
            },
            {
                "buyer": "Asesorías contables de 1-5 personas que llevan clientes con operaciones vinculadas",
                "observable_problem": "Preparan el modelo 232 con datos dispersos en Excel y pierden horas cada ejercicio.",
                "concrete_deliverable": "Checklist por cliente con plantilla de recogida de datos y borrador del modelo.",
                "causal_chain": "El modelo 232 es obligatorio cada ejercicio; sin una plantilla se pierden horas y hay errores.",
                "first_distribution_channel": "Colegios de gestores administrativos.",
                "test_in_48_hours": "Enviar la plantilla a 5 asesorías conocidas y pedir feedback.",
                "generic_ai_limitation": "Exige cruzar el padrón de socios del cliente con las operaciones declaradas.",
                "assumptions": "Las asesorías rellenan el 232 manualmente y querrían una plantilla.",
            },
        ]}
    if task == "coherence_check":
        return {"coherent": False, "causal_relation": None, "concrete_product": None,
                "why_pay": None, "discard_reason": "Triaje urgente y gamificación no tienen relación causal comercial."}
    if task == "red_team":
        return {"answers": [
            {"question": "¿Es solo una frase atractiva?", "verdict": "ok", "justification": "El cuaderno es un entregable concreto."},
            {"question": "¿Existe comprador identificable?", "verdict": "ok", "justification": "Presidentes de comunidades de 10-40 viviendas."},
            {"question": "¿Una IA generalista resuelve el 80%?", "verdict": "fatal", "justification": "Un prompt puede generar el cuaderno si se le dan los datos."},
            {"question": "¿Puede probarse por menos de 10 USD?", "verdict": "ok", "justification": "Plantilla por correo."},
            {"question": "¿Qué dato objetivo la descartaría?", "verdict": "ok", "justification": "Si las juntas ya comparan con un Excel propio."},
        ], "overall": "needs_reformulation", "cheapest_test": "Plantilla por correo a 5 presidentes."}
    if task == "variation_comparison":
        return {"selected": ["22222222222222222222222222222222"], "max_selected": 3,
                "rejected": [
                    {"id": "11111111111111111111111111111111", "reason": "Recopilar tarifas anónimas exige red de clínicas previa."},
                    {"id": "33333333333333333333333333333333", "reason": "Mercado estacional y concentrado."},
                ]}
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark reproducible de OX Alpha.")
    parser.add_argument("--out", default="deliverables/operacion_super_torneo_2026-08-26/ox_alpha_benchmark_018.json")
    args = parser.parse_args()

    settings = get_settings()
    container = build_container(settings)
    status = ox_alpha_status(settings)
    identity = status["identity"]
    deep = container.deep_reasoning
    arms: dict[str, dict] = {}

    for task in BENCHMARK_TASKS:
        arms.setdefault("A", {})[task] = {"status": "ok", "source": "baseline_determinista",
                                          **score_task_response(task, _baseline(task))}
        concept = CONCEPTS[task] if task != "variation_comparison" else {"title": "comparación"}
        if task == "variation_comparison":
            resp = deep.run_deep_task(task, concept, concepts_for_comparison=CONCEPTS[task])
        else:
            resp = deep.run_deep_task(task, concept)
        arms.setdefault("C", {})[task] = {
            "status": resp.get("status"),
            "gate": resp.get("state") or resp.get("status"),
            "used_model": resp.get("used_model"),
            "actual_model": resp.get("actual_model"),
            "call_id": resp.get("call_id"),
            "result": resp.get("result"),
            "reason": resp.get("reason"),
        }
        if resp.get("status") == "OK" and resp.get("result") is not None:
            arms["C"][task].update(score_task_response(task, resp["result"]))

    # B/D: estado de proveedores (sin llamadas si no están configurados).
    for arm, attr in (("B", "omniroute"), ("D", "openrouter")):
        prov = getattr(container.providers, attr, None)
        arms[arm] = {"available": bool(prov and prov.available()),
                     "note": f"proveedor {attr} {'disponible' if prov and prov.available() else 'no configurado/desactivado'}"}

    total_a = sum((arms["A"].get(t) or {}).get("percent") or 0 for t in BENCHMARK_TASKS) / len(BENCHMARK_TASKS)
    c_ok = [t for t in BENCHMARK_TASKS if (arms["C"].get(t) or {}).get("status") == "OK"]
    total_c = sum((arms["C"].get(t) or {}).get("percent") or 0 for t in c_ok) / len(c_ok) if c_ok else 0.0
    verdict = benchmark_verdict(identity, {"A": {"total_percent": total_a}, "C": {"total_percent": total_c, "status": "ok" if c_ok else "pending", "reason": f"{len(c_ok)}/{len(BENCHMARK_TASKS)} tareas respondidas"}})

    report = {
        "operacion": "benchmark_ox_alpha_018",
        "fecha": "2026-08-26",
        "identity": identity,
        "gateway_state": status["state"],
        "window_expires": status["expires_at"],
        "is_evidence": False,
        "arms": arms,
        "totals": {"A": round(total_a, 1), "C_ok_tasks": c_ok, "C": round(total_c, 1)},
        "verdict": verdict,
        "tasks": list(BENCHMARK_TASKS),
        "note": "Las respuestas de modelo son RAZONAMIENTO, nunca evidencia de mercado.",
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"identity": identity, "gateway_state": status["state"],
                      "tasks": len(BENCHMARK_TASKS), "C_ok": c_ok,
                      "A_percent": total_a, "C_percent": total_c,
                      "verdict": verdict["verdict"], "reason": verdict["reason"]}, indent=2))
    print(f"[OK] Reporte: {out}")
    container.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
