from __future__ import annotations

import tempfile
from collections import Counter
from pathlib import Path

from app.core.config import Settings
from app.core.container import build_container

tmp = Path(tempfile.mkdtemp())
settings = Settings(
    data_dir=tmp, database_path=tmp / "test.db", logs_dir=tmp / "logs",
    manual_research_dir=tmp / "manual_research", frontend_dir=Path("frontend"),
    credentials_env_path=tmp / "env_local.txt",
    llm_provider="mock",
)
c = build_container(settings)
created = c.orchestrator.create_real_campaign()
run = created["run"]
advanced = c.orchestrator.advance(run["id"])
run2 = advanced["run"]
print("run state:", run2["state"])
cid = run2["discovery_campaign_id"]
detail = c.discovery.campaign_detail(cid)
concepts = detail.get("concepts") or []
print("total concepts:", len(concepts))
print("status counts:", dict(Counter(x.get("status") for x in concepts)))
promoted = [
    x for x in concepts
    if x.get("status") in ("RESEARCH_CANDIDATE", "FINALIST", "SHORTLISTED_WITH_EVIDENCE")
]
print("promoted:", len(promoted))
for p in promoted:
    print(" -", p["title"])
# Buscar títulos parecidos a los del paquete
for needle in ("ortodoncia", "gestor", "placa", "solar"):
    hits = [x["title"] for x in concepts if needle.lower() in x["title"].lower()]
    print(f"contains '{needle}':", hits[:5])
missions = c.repos.discovery.missions_by_campaign(cid)
print("missions:", len(missions), "statuses:", Counter(m.get("status") for m in missions))
for m in missions[:4]:
    print("  mission:", m["kind"], (m.get("target") or {}).get("concept_title"))
c.close()
