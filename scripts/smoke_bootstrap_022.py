"""Smoke test offline del bootstrap comercial 022 (instalación limpia).

Crea una base temporal, aplica el bootstrap, comprueba idempotencia,
readiness, candidatas, telemetría y el asistente de servicios. Sin red.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.core.config import Settings
from app.core.container import build_container

ENV_NAME = ".env"  # nombre del archivo local de credenciales (fuera de Git)


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    settings = Settings(
        data_dir=tmp, database_path=tmp / "test.db", logs_dir=tmp / "logs",
        manual_research_dir=tmp / "manual_research", frontend_dir=Path("frontend"),
        credentials_env_path=tmp / ENV_NAME,
        llm_provider="mock",
    )
    c = build_container(settings)

    st = c.bootstrap.status(include_snapshot=True)
    print("STATUS before:", json.dumps(
        {k: st[k] for k in ("applied", "recoverable", "can_repair", "run_state", "run_status", "missing_activation")},
        ensure_ascii=False))

    res = c.bootstrap.apply()
    print("APPLY:", json.dumps(
        {k: res.get(k) for k in ("ok", "already_applied", "candidates", "missions_imported",
                                 "evidences_attached", "readiness_state", "pre_cycle",
                                 "real_spend_usd", "production")}, ensure_ascii=False))

    res2 = c.bootstrap.apply()
    print("APPLY2 already_applied:", res2.get("already_applied"))

    st2 = c.bootstrap.status(include_snapshot=True)
    print("STATUS after:", json.dumps(
        {k: st2[k] for k in ("applied", "applied_version", "run_state", "readiness_state")},
        ensure_ascii=False))

    cands = c.bootstrap.candidates()
    print("CANDIDATAS:", cands.get("count"))
    for card in cands.get("candidates") or []:
        print(" -", card["title"][:55], "| winner:", card["is_winner"],
              "| ev:", card["evidence_verified_live"], "| groups:", card["evidence_groups_live"],
              "| plan:", bool(card["plan"]))

    snap = c.command_center.snapshot()
    rd = snap.get("readiness") or {}
    print("READINESS:", rd.get("readiness_state"), "| missing:", rd.get("readiness_missing"),
          "| blockers:", rd.get("readiness_blockers"))
    print("EVIDENCE:", (snap.get("evidence") or {}).get("verified"), "/",
          (snap.get("evidence") or {}).get("total"),
          "groups:", (snap.get("evidence") or {}).get("independent_verified_groups"))
    print("MISSIONS:", (snap.get("missions") or {}).get("imported"), "of",
          (snap.get("missions") or {}).get("count"))

    tel = c.command_center.agent_telemetry()
    print("TELEMETRY bootstrap:", json.dumps(tel.get("bootstrap"), ensure_ascii=False))
    print("TELEMETRY run:", tel.get("run"))
    w = tel.get("launch_winner") or {}
    print("TELEMETRY winner:", w.get("title", "NONE")[:60] if w else "NONE")

    svc = c.connect_services.status()
    print("SERVICES:", [(s["id"], s["status"]) for s in svc["items"]])
    sv = c.connect_services.save({"STRIPE_SECRET_KEY": "sk_test_1234567890abcd"})
    print("SAVE:", sv.get("saved"), sv.get("updated_keys"))
    print("SERVICES after save:", [(s["id"], s["status"], s["last4"])
                                   for s in c.connect_services.status()["items"] if s["id"] == "stripe"])
    print("CHECK bad:", c.connect_services.check({"STRIPE_SECRET_KEY": "bad"})["results"][0]["state"])
    c.close()

    assert res.get("already_applied") is False
    assert res.get("candidates") == 3
    assert res.get("missions_imported") == 18
    assert res.get("readiness_state") == "READY_TO_CONNECT_SERVICES"
    assert res.get("pre_cycle") == "STOPPED"
    assert res.get("real_spend_usd") == 0.0
    assert res.get("production") == "BLOCKED"
    assert res2.get("already_applied") is True
    assert st2.get("readiness_state") == "READY_TO_CONNECT_SERVICES"
    print("\nSMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
