#!/usr/bin/env python3
"""Comando único de recuperación (iteración 017): aplica el plan de
reformulación a la campaña REAL local y deja las misiones listas.

    python3 scripts/apply_reformulation_plan.py --file reformulaciones_briefs.json [--preview]

Detecta automáticamente la campaña real activa (no pide identificadores),
localiza los conceptos LOCALES por título normalizado / territorio+lente+
arquetipo (los concept_id del plan son de una reproducción aislada y nunca se
insertan), exige coincidencia inequívoca, ejecuta Quality Gate + torneo (≤3)
y genera las misiones Fase 1 con IDs locales. Idempotente: re-ejecutar no
duplica nada. También importa paquetes de investigación portables:

    python3 scripts/apply_reformulation_plan.py --import-package research_package.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.container import build_container  # noqa: E402

from app.services.reformulation_import import apply_reformulation_plan, resolve_research_package  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Aplica el plan de reformulación a la campaña real local.")
    parser.add_argument("--file", help="Ruta al JSON del plan de reformulación.")
    parser.add_argument("--preview", action="store_true", help="Solo muestra coincidencias sin aplicar nada.")
    parser.add_argument("--import-package", dest="import_package",
                        help="Ruta a un paquete de investigación portable para importar en lote.")
    parser.add_argument("--apply-package", action="store_true",
                        help="Con --import-package: aplica la importación (sin esto solo vista previa).")
    args = parser.parse_args()

    if not args.file and not args.import_package:
        parser.error("Indica --file <plan.json> o --import-package <paquete.json>.")

    container = build_container(get_settings())
    try:
        if args.file:
            plan = json.loads(Path(args.file).read_text(encoding="utf-8"))
            result = apply_reformulation_plan(container, plan, preview=args.preview)
            print("=" * 72)
            print("PLAN DE REFORMULACIÓN — " + ("VISTA PREVIA" if args.preview else "APLICADO"))
            print(f"Ejecución: {result['run_id']}  Campaña discovery: {result['discovery_campaign_id']}")
            print(f"Briefs: {result['total_briefs']} · aplicados {result['applied']} · "
                  f"idempotentes {result['skipped_idempotent']} · rechazados {result['rejected']}")
            for e in result["entries"]:
                title = e.get("local_title") or "?"
                reason = f" ({e.get('reason')})" if e.get("reason") else ""
                score = f" · estructural={e['structural_score']:.2f}" if e.get("structural_score") else ""
                print(f"  [{e.get('result')}] {title}{score}{reason}")
            if not args.preview and result.get("missions_created"):
                print(f"Misiones Fase 1 creadas: {result['missions_created']} (IDs locales).")
                for m in result.get("missions") or []:
                    md = container.discovery.export_mission_markdown(m["mission_id"])
                    out = Path("data") / "missions_local" / f"{m['mission_id']}.md"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(md, encoding="utf-8")
                    print(f"  exportada: {out}")
            if result.get("next_action"):
                print(f"Próxima acción: {result['next_action']}")
        if args.import_package:
            package = json.loads(Path(args.import_package).read_text(encoding="utf-8"))
            res = resolve_research_package(container, package, apply=args.apply_package)
            mode = "IMPORTADO" if args.apply_package else "VISTA PREVIA"
            print("=" * 72)
            print(f"PAQUETE DE INVESTIGACIÓN ({mode}): "
                  f"{res['matched']} asociados · {res['ambiguous']} ambiguos · {res['unmatched']} sin misión local")
            for r in res["resolved"]:
                extra = f" -> {r['local_mission_id']}" if r.get("local_mission_id") else \
                        f" ({r.get('reason', '')})"
                print(f"  [{r['status']}] {r['candidate']} :: {r['mission_kind']}{extra}")
        return 0
    finally:
        container.close()


if __name__ == "__main__":
    raise SystemExit(main())
