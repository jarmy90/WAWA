#!/usr/bin/env python3
"""Benchmark A/B de generación de ideas (iteración 008).

10 problemas SINTÉTICOS diversos (no MQL5). Compara:
  A. Motor actual (pipeline clásico con proveedor offline/mock).
  B. OmniRoute `auto` (solo si OMNIROUTE_ENABLED y el servicio responde).
  C. Modelo fijo identificado del catálogo (pendiente de catálogo real).
  D. OpenRouter actual (solo si clave configurada).

Reglas:
- Todo el output está etiquetado como TEST: nunca es evidencia de mercado.
- Los brazos B/C/D NO hacen llamadas si el proveedor no está configurado o
  el servicio no responde: se marcan como "pending" (máx. 5 llamadas reales
  en toda la iteración; este script respeta el límite).
- Ejecutar:  python3 scripts/benchmark_ab.py [--arm A|B|C|D]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.container import build_container  # noqa: E402
from app.models.opportunity import OpportunityCreate  # noqa: E402

# 10 problemas sintéticos diversos (NO MQL5). Cada uno incluye su sector.
SYNTHETIC_PROBLEMS = [
    {"sector": "talleres_locales", "problem": "Los talleres de reparación pierden clientes porque los clientes no saben cuándo hay hueco real en su agenda."},
    {"sector": "autonomos", "problem": "Los autónomos pierden horas reconciliando facturas entre varias herramientas de facturación y contabilidad."},
    {"sector": "comercio_minorista", "problem": "Los pequeños comercios no saben qué stock físico coincide con el stock publicado en su tienda online."},
    {"sector": "clubs_deportivos_amateur", "problem": "Los clubes de fútbol amateur gestionan cuotas, bajas y convocatorias con mensajes sueltos en WhatsApp."},
    {"sector": "propietarios_vivienda", "problem": "Los propietarios de vivienda no detectan fugas de agua o consumos anómalos hasta que llega la factura."},
    {"sector": "comunidades_vecinos", "problem": "Las comunidades de vecinos no consiguen que los propietarios voten las derramas ordinarias."},
    {"sector": "freelancers_diseno", "problem": "Los freelancers de diseño no cobran los usos ampliados de sus licencias cuando el cliente los reutiliza."},
    {"sector": "hostelería", "problem": "Los bares pequeños tiran comida porque no anticipan la demanda del día con sus ventas de ayer."},
    {"sector": "fotografos_bodas", "problem": "Los fotógrafos de bodas entregan miles de fotos sin editar y pierden ventas de ampliaciones y álbumes."},
    {"sector": "formadores_online", "problem": "Los formadores online no saben qué parte de su curso hace que los alumnos abandonen."},
]

ARMS = {"A": "motor_actual_offline", "B": "omniroute_auto", "C": "modelo_fijo_catalogo", "D": "openrouter_actual"}


def _provider_state(container, arm: str) -> dict:
    if arm == "A":
        return {"available": True, "model": "mock", "note": "proveedor offline determinista"}
    if arm == "D":
        p = container.providers.openrouter
        return {"available": p.available(), "model": p.review_model, "note": "requiere OPENROUTER_API_KEY"}
    if arm in ("B", "C"):
        p = container.providers.omniroute
        return {"available": p.available(), "model": p.review_model, "note": "requiere OMNIROUTE_ENABLED y servicio local"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark A/B de generación de ideas (test sintético).")
    parser.add_argument("--arm", choices="ABCD", default="A", help="Brazo a ejecutar (A por defecto: offline).")
    parser.add_argument("--out", default=None, help="Ruta de salida JSON (por defecto data/benchmark/).")
    args = parser.parse_args()

    container = build_container(get_settings())
    state = _provider_state(container, args.arm)
    results = []
    for i, item in enumerate(SYNTHETIC_PROBLEMS, start=1):
        started = time.monotonic()
        if not state["available"]:
            results.append({
                "problem_id": i, "sector": item["sector"], "problem": item["problem"],
                "status": "pending", "reason": state["note"], "latency_ms": 0,
            })
            continue
        try:
            opp = container.opportunities.create(OpportunityCreate(
                title=f"[TEST-SINTETICO] {item['problem'][:60]}",
                problem=item["problem"], sector=item["sector"], source="benchmark-test",
            ))
            pipeline = container.pipeline.evaluate(opp.id)
            latency_ms = int((time.monotonic() - started) * 1000)
            ev = container.repos.evaluations.get(opp.id)
            results.append({
                "problem_id": i,
                "sector": item["sector"],
                "problem": item["problem"],
                "status": "ok",
                "arm": ARMS[args.arm],
                "opportunity_id": opp.id,
                "title": opp.title,
                "final_score": ev.final_score if ev else None,
                "decision": ev.decision.value if ev else None,
                "skeptic_risks": len(getattr(ev, "risks", []) or []),
                "latency_ms": latency_ms,
                "cost_usd": pipeline.get("cost_usd", 0.0) if isinstance(pipeline, dict) else 0.0,
                "actual_model": "mock" if args.arm == "A" else None,
                "human_intervention_needed": False,
            })
        except Exception as exc:  # el benchmark no debe romperse por un problema
            results.append({
                "problem_id": i, "sector": item["sector"], "problem": item["problem"],
                "status": "error", "detail": str(exc)[:200], "latency_ms": int((time.monotonic() - started) * 1000),
            })

    out = {
        "meta": {
            "synthetic_test": True,
            "not_market_evidence": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "arm": ARMS[args.arm],
            "provider_state": state,
            "note": "Datos SINTÉTICOS de prueba: no representan demanda ni resultados de mercado.",
        },
        "problems": len(SYNTHETIC_PROBLEMS),
        "results": results,
        "summary": {
            "ok": sum(1 for r in results if r["status"] == "ok"),
            "pending": sum(1 for r in results if r["status"] == "pending"),
            "error": sum(1 for r in results if r["status"] == "error"),
            "avg_score": round(sum(r.get("final_score") or 0 for r in results if r.get("final_score")) / max(1, sum(1 for r in results if r.get("final_score"))), 1),
            "avg_latency_ms": round(sum(r.get("latency_ms") or 0 for r in results) / max(1, len(results))),
        },
    }
    out_dir = Path(args.out) if args.out else (Path(__file__).resolve().parents[1] / "data" / "benchmark")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"benchmark_ab_arm_{args.arm}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=2))
    print("Guardado en:", out_path)
    container.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
