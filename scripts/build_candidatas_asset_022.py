"""Genera el activo empaquetado candidatas.json del bootstrap 022.

Combina la investigación portable (evidencias/competidores por candidata) con
los campos canónicos de concepto y Opportunity Brief de la reproducción 021
(base data/abl.db). El resultado es el contrato inmutable que el bootstrap
materializa en instalaciones locales SIN insertar IDs foráneos (resolución por
título normalizado).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

BASE = Path("resources/bootstrap/commercial_021")
RESEARCH = json.loads((BASE / "investigacion_fase1_021.json").read_text(encoding="utf-8"))
payloads = RESEARCH["payloads"]

con = sqlite3.connect("data/abl.db")
con.row_factory = sqlite3.Row
rows = con.execute(
    "SELECT * FROM discovery_concepts WHERE status='RESEARCH_PENDING' ORDER BY title"
).fetchall()
con.close()

by_title = {}
for r in rows:
    d = dict(r)
    d["lens_keys"] = json.loads(d["lens_keys"])
    d["brief"] = json.loads(d["brief"])
    d.pop("fingerprint", None)
    by_title[d["title"]] = d

EXTRA = {
    "Benchmark anónimo de tarifas para clínicas dentales que deciden su precio de ortodoncia": {
        "role": "WINNER",
        "winner_reason": ("Ganadora determinista (torneo 018: 77.5 + evidencia verificada 11/31). "
                          "Única con low_launch_cost=2/2 y concierge_delivery=2/2. No indica demanda "
                          "validada: no existe pago real."),
        "buyer": "HIPÓTESIS: gerentes de clínicas dentales de 2-5 dentistas",
        "problem": "Las clínicas dentales pequeñas fijan el precio de ortodoncia sin un comparativo de tarifas de su zona y pierden margen o pacientes.",
        "offer": "Informe de benchmark anónimo de tarifas de ortodoncia por provincia (rangos y percentiles) + revisión por videollamada (concierge).",
        "price": "HIPÓTESIS: 30-90 EUR (midpoint 60 EUR) — sin comprador real todavía",
        "channel": "Contacto directo autorizado a 20 clínicas identificadas vía colegios y directorios oficiales; LinkedIn y colegios provinciales",
        "contradictions": "Dispersión real documentada (2.900-8.100 EUR según fuentes públicas); la urgencia de compra no está demostrada; guías gratuitas pueden suplir parte del valor.",
        "risks": ["Guías de precios gratuitas como sustituto (cubierto por kill condition)",
                  "Dominio sanitario: nunca usar datos de pacientes (informe anónimo agregado)",
                  "Urgencia no demostrada: sin evento de compra claro"],
        "kill_condition": "Sin señal de pago tras 14 días de contacto activo; cierre en 30 días sin pivote viable.",
        "status": "RESEARCH_PENDING -> READY_TO_CONNECT_SERVICES (tras bootstrap)",
    },
    "Benchmark de honorarios para gestorías que deciden su tarifa mensual": {
        "role": "CANDIDATE",
        "winner_reason": "No seleccionada: torneo 018 = 72.5 (por debajo de 77.5) y sin ventaja concierge/low-launch-cost plena. Se conserva como candidata investigada.",
        "buyer": "HIPÓTESIS: gestorías y asesorías contables que fijan su tarifa mensual",
        "problem": "Las gestorías fijan honorarios mensuales sin comparativa de mercado; precios opacos y clientes sin forma de comparar.",
        "offer": "Benchmark anónimo de honorarios de gestorías por tamaño de cartera/región.",
        "price": "HIPÓTESIS: sin precio fijado — pendiente de experimento",
        "channel": "Colegios/registros de gestores administrativos; asociaciones profesionales; LinkedIn",
        "contradictions": "Sector con precios tradicionalmente opacos; fuentes públicas limitadas.",
        "risks": ["Opacidad de precios reales del sector", "Comprador (gestoría) poco habituado a pagar por datos de mercado"],
        "kill_condition": "Sin señal de pago tras experimento de 30 días.",
        "status": "RESEARCH_PENDING -> investigada con evidencia (no ganadora)",
    },
    "Benchmark de costes de instalación para empresas de placas solares que deciden presupuesto": {
        "role": "CANDIDATE",
        "winner_reason": "No seleccionada: torneo 018 = 72.5 y coste de lanzamiento/entrega concierge inferiores a la ganadora. Se conserva como candidata investigada.",
        "buyer": "HIPÓTESIS: empresas instaladoras de placas solares que deciden presupuesto",
        "problem": "Las instaladoras fijan presupuestos sin referencia de coste por kW y pierden margen o clientes.",
        "offer": "Benchmark de costes de instalación fotovoltaica por kW y zona.",
        "price": "HIPÓTESIS: sin precio fijado — pendiente de experimento",
        "channel": "Asociaciones (UNEF y afines); directorios de instaladores; LinkedIn sectorial",
        "contradictions": "Costes muy dependientes de zona/tipo de cubierta; datos públicos fragmentados.",
        "risks": ["Volatilidad de precios de componentes", "Comprador con alternativas gratuitas de cálculo"],
        "kill_condition": "Sin señal de pago tras experimento de 30 días.",
        "status": "RESEARCH_PENDING -> investigada con evidencia (no ganadora)",
    },
}


def card_for(payload, concept_row, extra):
    sources, competitors, groups, verified = [], [], set(), 0
    for m in payload["missions"]:
        for ev in m.get("evidences") or []:
            if ev.get("verified"):
                verified += 1
                if ev.get("independence_group"):
                    groups.add(ev["independence_group"])
            nm = ev.get("source_name")
            if nm and nm not in sources:
                sources.append(nm)
        for c in m.get("competitors") or []:
            competitors.append({"name": c.get("name"), "offer": c.get("offer"), "observed_price": c.get("observed_price")})
    return {
        "title": payload["title"],
        **extra,
        "evidence_verified": verified,
        "evidence_groups": len(groups),
        "main_sources": sources,
        "competitors": competitors,
        "concept": {
            "title": concept_row["title"],
            "territory_key": concept_row["territory_key"],
            "lens_keys": concept_row["lens_keys"],
            "archetype_key": concept_row["archetype_key"],
            "problem_hypothesis": concept_row["problem_hypothesis"],
            "mechanism": concept_row["mechanism"],
            "buyer_hypothesis": concept_row["buyer_hypothesis"],
            "outcome_hypothesis": concept_row["outcome_hypothesis"],
            "why_now": concept_row["why_now"],
            "general_ai_risk": concept_row["general_ai_risk"],
            "asset_potential": concept_row["asset_potential"],
        },
        "brief": concept_row["brief"],
    }


cards = []
for payload in payloads:
    concept_row = by_title.get(payload["title"])
    if concept_row is None:
        # Los títulos del paquete están sin acentos; busca por normalización.
        import unicodedata, re

        def norm(t):
            t = unicodedata.normalize("NFKD", t.lower())
            t = "".join(c for c in t if not unicodedata.combining(c))
            return re.sub(r"[^a-z0-9]+", " ", t).strip()

        target = norm(payload["title"])
        for t, row in by_title.items():
            if norm(t) == target:
                concept_row = row
                break
    if concept_row is None:
        raise SystemExit(f"NO HAY CONCEPTO CANÓNICO PARA: {payload['title']}")
    cards.append(card_for(payload, concept_row, EXTRA[concept_row["title"]]))

out = {
    "operacion": "activacion_comercial_021",
    "fecha": "2026-08-26",
    "note": ("Tarjetas de candidatas del bootstrap comercial. Precios y compradores son HIPÓTESIS "
             "(no hay pago ni entrevista real). La ganadora NO tiene demanda validada: es ganadora "
             "determinista PARA EXPERIMENTO. Los campos concept/brief son los canónicos de la "
             "reproducción 021 (base de referencia), materializables localmente sin IDs foráneos."),
    "candidates": cards,
}
(BASE / "candidatas.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("candidatas.json regenerado con concept + brief canónicos")
for c in cards:
    print("-", c["title"][:55], "| role:", c["role"], "| ev:", c["evidence_verified"],
          "| groups:", c["evidence_groups"], "| concept:", bool(c.get("concept")), "| brief:", bool(c.get("brief")))
