"""Carga las oportunidades de demostración (MQL5) y las evalúa.

Uso: python3 scripts/seed_demo.py [--no-evaluate]
"""
from __future__ import annotations

import argparse
import json
import sys

from app.core.container import build_container
from app.workflows.demo import DemoSeeder


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga la demo de Autonomous Business Lab.")
    parser.add_argument("--no-evaluate", action="store_true", help="No ejecutar el pipeline sobre la demo.")
    args = parser.parse_args()

    container = build_container()
    try:
        summary = DemoSeeder(container.settings, container.repos, container.pipeline).seed(evaluate=not args.no_evaluate)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    finally:
        container.close()


if __name__ == "__main__":
    sys.exit(main())
