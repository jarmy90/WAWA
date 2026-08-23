#!/usr/bin/env python3
"""Finaliza una sesión Freebuff de una campaña.

    python3 scripts/finalize_session.py --session <id>

Valida outputs, importa resultados (con deduplicación), actualiza la campaña,
persiste aprendizajes, genera SESSION_REPORT.md y NEXT_SESSION.md y ejecuta
los filtros deterministas. No avanza de etapa si faltan entregables.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.container import build_container  # noqa: E402
from app.core.errors import ConflictError, NotFoundError, ValidationError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Finaliza una sesión Freebuff.")
    parser.add_argument("--session", required=True, help="ID de la sesión a finalizar.")
    args = parser.parse_args()

    container = build_container(get_settings())
    try:
        result = container.campaigns.finalize_session(args.session)
    except (NotFoundError, ConflictError, ValidationError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    print("=" * 72)
    print("SESIÓN FINALIZADA")
    print("=" * 72)
    print(f"Sesión   : {result['session']['session_id']}")
    print(f"Estado   : {result['session']['status']}")
    print(f"Etapa    : {result['session'].get('stage_start')} -> {result['session'].get('stage_end')}")
    print(f"Conceptos: {result['session'].get('concepts_created', 0)} creados / "
          f"{result['session'].get('concepts_rejected', 0)} rechazados")
    if result.get("next_session_path"):
        print(f"NEXT     : {result['next_session_path']}")
    campaign_detail = result.get("campaign", {}).get("campaign", {})
    print()
    print("PRÓXIMA ACCIÓN RECOMENDADA:")
    print("-" * 72)
    print(campaign_detail.get("next_recommended_action") or "(sin acción pendiente)")
    print("-" * 72)
    if result.get("report_path"):
        print(f"Informe  : {result['report_path']}")
    container.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
