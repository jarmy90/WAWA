#!/usr/bin/env python3
"""Prepara el workspace para una sesión Freebuff de una campaña.

NO llama a Freebuff mediante ninguna API. Prepara el estado persistente y
genera el prompt breve que el propietario puede dar a Freebuff en la sesión:

    python3 scripts/continue_campaign.py --campaign <id> --hours 5

Crea SESSION_PLAN.md, SESSION_STATE.json y SESSION_PROMPT.md dentro de
``data/sessions/<campaign_id>/<session_id>/`` y muestra el prompt breve.
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
    parser = argparse.ArgumentParser(description="Prepara una sesión Freebuff para una campaña.")
    parser.add_argument("--campaign", required=True, help="ID de la campaña Freebuff-first.")
    parser.add_argument("--hours", type=int, default=3, help="Horas objetivo de la sesión (2-6).")
    parser.add_argument("--actor", default="human", help="Actor que inicia la sesión.")
    args = parser.parse_args()

    container = build_container(get_settings())
    try:
        session = container.campaigns.prepare_session(args.campaign, args.hours, actor=args.actor)
    except (NotFoundError, ConflictError, ValidationError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    print("=" * 72)
    print("SESIÓN PREPARADA (FREEBUFF SESSION — sin API, sin 24/7)")
    print("=" * 72)
    print(f"Campaña     : {session['campaign_id']}")
    print(f"Sesión      : {session['session_id']}")
    print(f"Horas       : {session['time_budget_hours']}")
    print(f"Etapa       : {session['stage_start']}")
    print(f"Plan        : {session.get('plan_path', '')}")
    print(f"Estado      : {session.get('state_path', '')}")
    print(f"Prompt      : {session.get('plan_path', '').rsplit('/', 1)[0]}/SESSION_PROMPT.md")
    print()
    print("PROMPT BREVE PARA FREEBUFF (pégalo tal cual en la nueva sesión):")
    print("-" * 72)
    print(session["short_prompt"])
    print("-" * 72)
    print("Al terminar la sesión ejecuta: python3 scripts/finalize_session.py --session "
          + session["session_id"])
    container.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
