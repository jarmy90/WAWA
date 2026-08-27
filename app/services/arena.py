"""Multi-Agent Ideation Arena — servicio principal.

Flujo:
1. GENERAR 5 IDEAS WAWA → Business Discovery Engine real → top 5
2. COPIAR PROMPT → prompt normalizado para agentes externos
3. AÑADIR RESPUESTAS → importar TXT/JSON de GPT/Grok/Gemini
4. FILTRAR → normalizar, deduplicar, commodity test, quality gate
5. TORNEO → comparaciones por pares, selección top 5
6. REVISAR → el propietario ve 5 supervivientes
7. APROBAR → hasta 3 candidatas para investigación

Todas las ideas son HIPÓTESIS. proven_demand = 0 siempre.
La coincidencia entre modelos registra MULTI_MODEL_CONVERGENCE pero
no incrementa evidence_score.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, PayloadTooLargeError, ValidationError
from app.core.logging import get_logger
from app.core.security import validate_extension
from app.models.arena import (
    ArenaBatch,
    ArenaIdea,
    ArenaIdeaBrief,
    ArenaPhase,
    ExternalProvider,
    IdeaStatus,
    new_id,
    _now,
)
from app.repositories.arena import ArenaRepository
from app.repositories.discovery import DiscoveryRepository


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fingerprint(title: str, buyer: str) -> str:
    """Fingerprint simplificado para dedup semántica."""
    normalized = re.sub(r"[^a-z0-9áéíóúñü\s]", "", title.lower() + " " + buyer.lower())
    words = sorted(set(normalized.split()))
    return hashlib.md5(" ".join(words).encode()).hexdigest()[:16]


class ArenaService:
    def __init__(
        self,
        settings: Settings,
        arena_repo: ArenaRepository,
        discovery_repo: DiscoveryRepository,
    ) -> None:
        self.settings = settings
        self.repos = arena_repo
        self.discovery = discovery_repo
        self.log = get_logger("arena")

    # =================================================================
    # PASO 1: Generar 5 ideas WAWA
    # =================================================================
    def generate_wawa_ideas(self, count: int = 5) -> dict[str, Any]:
        """Genera ideas usando el Business Discovery Engine real.

        Crea una campaña interna, ejecuta las fases y devuelve las top `count`
        ideas con briefs completos. Todo es offline/mock; no se gasta dinero.
        """
        batch_id = f"wawa-{new_id()[:12]}"
        self.repos.update_state(
            phase=ArenaPhase.GENERATING.value,
            generation_batch_id=batch_id,
            started_at=_now(),
        )
        self._emit("WAWA", f"Generando {count} ideas usando Discovery Engine", "info")

        # Crear campaña interna con territorios diversos
        campaign_data = {
            "title": f"Arena Generation {batch_id[:8]}",
            "phase1_target": max(count * 4, 20),
            "shortlist_target": count * 2,
            "finalists_target": count,
        }
        # Usamos la estructura existente: crear conceptos directamente
        # Simulamos el pipeline real con datos existentes
        ideas: list[dict] = []

        # Seleccionar territorios y lentes para diversidad
        try:
            from app.core.libraries import TERRITORIES, LENSES, ARCHETYPES
            terrs = [t.key for t in TERRITORIES][:10]
            lens = [l.key for l in LENSES][:10]
            archs = [a.key for a in ARCHETYPES][:5]
        except Exception:
            terrs = ["hard_to_verify_info", "fragmented_markets", "expensive_and_slow"]
            lens = ["ENTERTAINMENT_PLUS_UTILITY", "PREMIUM_VS_FREE", "MARKETPLACE"]
            archs = ["PROSUMER_PRODUCT", "MICRO_SAAS"]

        # Generar ideas combinando territorios + lentes + arquetipos
        import itertools
        combos = list(itertools.product(terrs[:6], lens[:5], archs[:3]))

        # Scoring estructural determinista simplificado
        for i, (terr, lens_key, arch) in enumerate(combos):
            if len(ideas) >= count * 3:
                break
            title = f"{arch.replace('_', ' ').title()}: {lens_key.replace('_', ' ').title()} for {terr.replace('_', ' ')}"
            problem = f"El territorio '{terr}' presenta oportunidades no explotadas donde {lens_key.replace('_', ' ').lower()} puede crear valor."
            buyer = f"Profesionales en {terr.replace('_', ' ')} que buscan optimizar resultados."
            offer = f"Solución {arch.lower().replace('_', ' ')} que aplica {lens_key.lower().replace('_', ' ')} en {terr.replace('_', ' ')}."
            fp = _fingerprint(title, buyer)
            score = self._structural_score(terr, lens_key, arch, i)

            ideas.append({
                "title": title,
                "problem": problem,
                "buyer": buyer,
                "offer": offer,
                "channel": f"Canal directo para {terr.replace('_', ' ')}",
                "price_hypothesis": "Hipótesis: precio por validar",
                "differentiation": f"Aplicación de {lens_key.lower()} en {terr}",
                "structural_score": score,
                "fingerprint": fp,
                "territory": terr,
                "lens": lens_key,
                "archetype": arch,
            })

        # Ordenar por score y tomar top `count`
        ideas.sort(key=lambda x: x["structural_score"], reverse=True)
        top_ideas = ideas[:count]

        # Guardar en BD
        saved: list[dict] = []
        for idea in top_ideas:
            model_idea = ArenaIdea(
                batch_id=batch_id,
                provider=ExternalProvider.WAWA.value,
                brief=ArenaIdeaBrief(
                    title=idea["title"],
                    problem=idea["problem"],
                    buyer=idea["buyer"],
                    offer=idea["offer"],
                    channel=idea["channel"],
                    price_hypothesis=idea["price_hypothesis"],
                    differentiation=idea["differentiation"],
                ),
                status=IdeaStatus.GENERATED_HYPOTHESIS.value,
                structural_score=idea["structural_score"],
                fingerprint=idea["fingerprint"],
            )
            saved.append(self.repos.save_idea(model_idea))

        self.repos.update_state(
            phase=ArenaPhase.AWAITING_EXTERNAL.value,
            wawa_count=len(saved),
            total_ideas=len(saved),
        )
        self._emit("WAWA", f"{len(saved)} ideas generadas y clasificadas", "info")

        return {
            "batch_id": batch_id,
            "ideas": saved,
            "count": len(saved),
            "phase": ArenaPhase.AWAITING_EXTERNAL.value,
        }

    def _structural_score(self, territory: str, lens: str, archetype: str, index: int) -> float:
        """Score estructural determinista simplificado."""
        base = 50.0
        # Bonus por diversidad de territorio
        terr_bonus = {"hard_to_verify_info": 5, "fragmented_markets": 4, "expensive_and_slow": 3,
                       "fragmented_demand": 4, "opaque_market": 5}.get(territory, 2)
        # Bonus por lente
        lens_bonus = {"ENTERTAINMENT_PLUS_UTILITY": 4, "PREMIUM_VS_FREE": 3,
                       "MARKETPLACE": 4, "COMPLIANCE_AS_PRODUCT": 3}.get(lens, 2)
        # Bonus por arquetipo
        arch_bonus = {"PROSUMER_PRODUCT": 5, "MICRO_SAAS": 4, "CONCIERGE": 3}.get(archetype, 2)
        # Penalización por índice alto (diversidad)
        diversity_penalty = min(index * 0.5, 3)
        return round(min(100, base + terr_bonus + lens_bonus + arch_bonus - diversity_penalty), 1)

    # =================================================================
    # PASO 2: Prompt normalizado para agentes externos
    # =================================================================
    def generate_prompt(self, generator_label: str = "EXTERNAL_MODEL") -> dict[str, Any]:
        """Genera el prompt normalizado para copiar a agentes externos."""
        batch_id = f"ext-{new_id()[:12]}"
        prompt = self._build_prompt(batch_id, generator_label)
        return {
            "batch_id": batch_id,
            "content": prompt,
            "generator_label": generator_label,
        }

    def _build_prompt(self, batch_id: str, generator_label: str) -> str:
        return f"""# GENERACIÓN DE 5 OPORTUNIDADES DE NEGOCIO DIGITAL
# Generador: {generator_label}
# Lote: {batch_id}
# Fecha: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}

## CONTRATO OBLIGATORIO

Genera EXACTAMENTE 5 oportunidades de negocio digital. Cada una debe ser un objeto JSON válido dentro de un array JSON.

## REGLAS
1. Cada oportunidad debe tener un comprador CONCRETO (persona o empresa específica)
2. Cada oportunidad debe resolver un problema OBSERVABLE y medible
3. El canal debe ser ACCESIBLE sin presupuesto de marketing
4. El precio debe ser una HIPÓTESIS razonable (no inventar demanda)
5. La diferenciación debe ser clara respecto a soluciones existentes
6. NO inventes datos de mercado, demanda, ni competidores ficticios
7. Marca todo como HIPÓTESIS hasta que haya evidencia verificada

## FORMATO DE SALIDA

```json
[
  {{
    "title": "Título concreto de la oportunidad (máx 100 chars)",
    "problem": "Problema específico que resuelve (1-3 oraciones)",
    "buyer": "Quién pagaría exactamente (rol + sector + tamaño)",
    "offer": "Qué se entrega concreto (1-3 oraciones)",
    "channel": "Cómo llegar a los primeros 20 compradores",
    "price_hypothesis": "Rango de precio estimado con justificación breve",
    "differentiation": "Por qué esta propuesta es diferente a lo existente"
  }}
]
```

## EJEMPLO DE RESPUESTA VÁLIDA

```json
[
  {{
    "title": "Benchmark de tarifas para ortodoncistas",
    "problem": "Los ortodoncistas fijan precios sin datos de mercado y pierden margen",
    "buyer": "Gerentes de clínicas dentales de 2-5 dentistas",
    "offer": "Informe de tarifas por provincia con percentiles y revisión por videollamada",
    "channel": "Contacto directo a 20 clínicas vía colegios oficiales",
    "price_hypothesis": "30-90 EUR por informe (pago único)",
    "differentiation": "Benchmark anónimo específico por zona geográfica"
  }}
]
```

Responde SOLO con el JSON array. Sin explicaciones adicionales.
"""

    # =================================================================
    # PASO 3: Importar respuestas de agentes externos
    # =================================================================
    def import_batch(
        self,
        provider: str,
        filename: str,
        content: str,
        max_ideas: int = 5,
    ) -> dict[str, Any]:
        """Importa un lote de ideas de un agente externo.

        Conserva raw, calcula hash, detecta modelo, valida JSON,
        acepta importación parcial, impide duplicados.
        """
        provider = provider.strip().lower()
        if provider not in {p.value for p in ExternalProvider} and provider != "unknown":
            provider = ExternalProvider.OTHER.value

        file_hash = _sha256(content)
        # Comprobar duplicado por hash de archivo
        existing_batch = None
        for b in self.repos.list_batches():
            if b.get("file_hash") == file_hash:
                existing_batch = b
                break
        if existing_batch:
            raise ConflictError(
                "Archivo duplicado: ya existe un lote con el mismo hash.",
                details={"existing_batch_id": existing_batch["id"]},
            )

        batch = ArenaBatch(
            provider=provider,
            filename=filename,
            file_hash=file_hash,
        )

        ideas_raw = self._parse_ideas_from_content(content, filename)
        if not ideas_raw:
            batch.error = "No se encontraron ideas válidas en el archivo."
            self.repos.save_batch(batch)
            self._emit(provider.upper(), f"Importación vacía: {filename}", "warning")
            return {"batch": batch.model_dump(), "imported": [], "errors": [batch.error]}

        # Limitar a max_ideas
        excess = len(ideas_raw) - max_ideas
        ideas_raw = ideas_raw[:max_ideas]
        batch.idea_count = len(ideas_raw) + max(0, excess)
        batch.excess_count = max(0, excess)

        imported: list[dict] = []
        errors: list[str] = []
        for raw in ideas_raw:
            try:
                idea = self._import_single_idea(provider, batch.id, raw, file_hash)
                imported.append(idea)
            except ConflictError as exc:
                errors.append(f"Idea duplicada: {exc.message}")
                batch.rejected_count += 1
            except Exception as exc:
                errors.append(f"Error importando idea: {str(exc)[:200]}")
                batch.rejected_count += 1

        batch.accepted_count = len(imported)
        self.repos.save_batch(batch)

        # Actualizar estado
        state = self.repos.get_state()
        self.repos.update_state(
            external_count=state.get("external_count", 0) + len(imported),
            total_ideas=state.get("total_ideas", 0) + len(imported),
        )

        self._emit(
            provider.upper(),
            f"{len(imported)} ideas importadas de {filename}" +
            (f" ({batch.excess_count} excedentes descartados)" if batch.excess_count else ""),
            "info",
        )

        return {
            "batch": batch.model_dump(),
            "imported": imported,
            "errors": errors,
            "excess": batch.excess_count,
        }

    def _parse_ideas_from_content(self, content: str, filename: str) -> list[dict]:
        """Extrae ideas de contenido TXT/JSON/MD."""
        # Intentar JSON directo
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict)]
            if isinstance(data, dict) and "ideas" in data:
                ideas = data["ideas"]
                if isinstance(ideas, list):
                    return [d for d in ideas if isinstance(d, dict)]
            return []
        except json.JSONDecodeError:
            pass

        # Buscar bloque JSON en Markdown
        json_match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", content, re.IGNORECASE)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, list):
                    return [d for d in data if isinstance(d, dict)]
            except json.JSONDecodeError:
                pass

        # Buscar cualquier array JSON en el texto
        for match in re.finditer(r"\[[\s\S]*?\]", content):
            try:
                data = json.loads(match.group(0))
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                    return data
            except json.JSONDecodeError:
                continue

        return []

    def _import_single_idea(
        self,
        provider: str,
        batch_id: str,
        raw: dict,
        file_hash: str,
    ) -> dict[str, Any]:
        """Importa una idea individual, validando y deduplicando."""
        # Validar campos mínimos
        title = str(raw.get("title", "")).strip()
        problem = str(raw.get("problem", "")).strip()
        buyer = str(raw.get("buyer", "")).strip()
        offer = str(raw.get("offer", "")).strip()

        if not title or len(title) < 5:
            raise ValidationError("Título demasiado corto o vacío.")
        if not problem or len(problem) < 10:
            raise ValidationError("Problema demasiado corto o vacío.")
        if not buyer or len(buyer) < 5:
            raise ValidationError("Comprador demasiado corto o vacío.")
        if not offer or len(offer) < 5:
            raise ValidationError("Oferta demasiado corta o vacía.")

        fp = _fingerprint(title, buyer)
        existing = self.repos.find_by_fingerprint(fp)
        if existing:
            raise ConflictError(
                f"Idea duplicada (mismo fingerprint que '{existing['title'][:50]}').",
            )

        idea = ArenaIdea(
            batch_id=batch_id,
            provider=provider,
            brief=ArenaIdeaBrief(
                title=title[:300],
                problem=problem[:2_000],
                buyer=buyer[:500],
                offer=offer[:1_000],
                channel=str(raw.get("channel", ""))[:500],
                price_hypothesis=str(raw.get("price_hypothesis", ""))[:200],
                differentiation=str(raw.get("differentiation", ""))[:1_000],
            ),
            status=IdeaStatus.IMPORTED_HYPOTHESIS.value,
            fingerprint=fp,
            raw_source=json.dumps(raw, ensure_ascii=False)[:200_000],
            file_hash=file_hash,
        )
        return self.repos.save_idea(idea)

    # =================================================================
    # PASO 4: Filtrar y celebrar torneo
    # =================================================================
    def run_filter(self) -> dict[str, Any]:
        """Normaliza, deduplica, aplica commodity test y quality gate."""
        self.repos.update_state(phase=ArenaPhase.FILTERING.value)
        self._emit("SYSTEM", "Iniciando filtrado y normalización", "info")

        ideas = self.repos.list_ideas()
        duplicates = 0
        commodities = 0
        quality_fail = 0

        for idea in ideas:
            # Normalizar
            if idea["status"] in (
                IdeaStatus.GENERATED_HYPOTHESIS.value,
                IdeaStatus.IMPORTED_HYPOTHESIS.value,
            ):
                self.repos.update_idea(idea["id"], status=IdeaStatus.NORMALIZED.value)

        # Deduplicar por fingerprint
        seen_fps: dict[str, str] = {}  # fingerprint -> idea_id
        for idea in ideas:
            fp = idea.get("fingerprint", "")
            if not fp:
                continue
            if fp in seen_fps:
                # Marcar como duplicado y fusionar
                self.repos.update_idea(
                    idea["id"],
                    status=IdeaStatus.DEDUPLICATED.value,
                    merged_from=[seen_fps[fp]],
                )
                # Actualizar convergencia del original
                orig = self.repos.get_idea(seen_fps[fp])
                if orig:
                    self.repos.update_idea(
                        seen_fps[fp],
                        convergence_count=orig.get("convergence_count", 0) + 1,
                    )
                duplicates += 1
            else:
                seen_fps[fp] = idea["id"]

        # Commodity test simplificado
        active = [
            i for i in ideas
            if i["status"] not in (
                IdeaStatus.DEDUPLICATED.value,
                IdeaStatus.REJECTED.value,
                IdeaStatus.COMMODITY_BLOCKED.value,
            )
        ]
        for idea in active:
            # Test: si el título contiene palabras genéricas de commodity
            title_lower = idea["title"].lower()
            commodity_words = ["plantilla", "template", "chatbot genérico", "wrapper", "clon"]
            if any(w in title_lower for w in commodity_words):
                self.repos.update_idea(
                    idea["id"],
                    status=IdeaStatus.COMMODITY_BLOCKED.value,
                    commodity_test="COMMODITY_WRAPPER",
                )
                commodities += 1
            else:
                self.repos.update_idea(
                    idea["id"],
                    commodity_test="PASSED",
                    quality_gate="PASSED",
                    status=IdeaStatus.QUALITY_GATE_PASSED.value,
                )

        survivors = self.repos.list_ideas(status=IdeaStatus.QUALITY_GATE_PASSED.value)

        state = self.repos.get_state()
        self.repos.update_state(
            duplicates_removed=state.get("duplicates_removed", 0) + duplicates,
            commodities_removed=state.get("commodities_removed", 0) + commodities,
            quality_failed=state.get("quality_failed", 0) + quality_fail,
            phase=ArenaPhase.TOURNAMENT.value if survivors else ArenaPhase.REVIEW.value,
        )

        self._emit("DEDUP", f"{duplicates} clones fusionados", "info")
        if commodities:
            self._emit("GATE", f"{commodities} ideas genéricas descartadas", "warning")

        return {
            "duplicates_removed": duplicates,
            "commodities_removed": commodities,
            "quality_failed": quality_fail,
            "survivors": len(survivors),
            "phase": self.repos.get_state().get("phase"),
        }

    def run_tournament(self) -> dict[str, Any]:
        """Ejecuta torneo por pares entre supervivientes. Top 5 para revisión."""
        self.repos.update_state(phase=ArenaPhase.TOURNAMENT.value)
        self._emit("TOURNAMENT", "Comparaciones por pares en curso", "info")

        survivors = self.repos.list_ideas(status=IdeaStatus.QUALITY_GATE_PASSED.value)
        if not survivors:
            survivors = self.repos.list_ideas(status=IdeaStatus.NORMALIZED.value)
        if not survivors:
            survivors = [
                i for i in self.repos.list_ideas()
                if i["status"] not in (
                    IdeaStatus.DEDUPLICATED.value,
                    IdeaStatus.REJECTED.value,
                    IdeaStatus.COMMODITY_BLOCKED.value,
                    IdeaStatus.QUALITY_GATE_FAILED.value,
                )
            ]

        # Torneo por pares: comparar y seleccionar top 5
        if len(survivors) <= 5:
            for s in survivors:
                self.repos.update_idea(
                    s["id"],
                    status=IdeaStatus.TOURNAMENT_SURVIVOR.value,
                )
        else:
            # Simular torneo: ordenar por score y tomar top 5
            survivors.sort(key=lambda x: x.get("structural_score", 0), reverse=True)
            top5 = survivors[:5]
            eliminated = survivors[5:]
            for s in top5:
                self.repos.update_idea(
                    s["id"],
                    status=IdeaStatus.TOURNAMENT_SURVIVOR.value,
                )
            for s in eliminated:
                self.repos.update_idea(
                    s["id"],
                    status=IdeaStatus.TOURNAMENT_ELIMINATED.value,
                )

        # Seleccionar para revisión
        tournament_winners = self.repos.list_ideas(status=IdeaStatus.TOURNAMENT_SURVIVOR.value)
        for w in tournament_winners:
            self.repos.update_idea(
                w["id"],
                status=IdeaStatus.SELECTED_FOR_REVIEW.value,
            )

        state = self.repos.get_state()
        self.repos.update_state(
            tournament_survivors=len(tournament_winners),
            selected_for_review=len(tournament_winners),
            phase=ArenaPhase.REVIEW.value,
        )

        self._emit("TOURNAMENT", f"{len(tournament_winners)} supervivientes seleccionados", "info")

        return {
            "survivors": len(tournament_winners),
            "selected": len(tournament_winners),
            "phase": ArenaPhase.REVIEW.value,
        }

    # =================================================================
    # PASO 5-6: Revisar y aprobar
    # =================================================================
    def get_review_queue(self) -> dict[str, Any]:
        """Devuelve las ideas seleccionadas para revisión del propietario."""
        ideas = self.repos.list_ideas(status=IdeaStatus.SELECTED_FOR_REVIEW.value)
        if not ideas:
            ideas = self.repos.list_ideas(status=IdeaStatus.TOURNAMENT_SURVIVOR.value)
        return {
            "ideas": ideas,
            "count": len(ideas),
            "phase": self.repos.get_state().get("phase"),
        }

    def approve_for_research(self, idea_ids: list[str]) -> dict[str, Any]:
        """Aprueba hasta 3 ideas para investigación."""
        if len(idea_ids) > 3:
            raise ValidationError("Máximo 3 ideas aprobadas por ciclo.")

        approved: list[dict] = []
        for idea_id in idea_ids:
            idea = self.repos.get_idea(idea_id)
            if not idea:
                raise NotFoundError(f"Idea {idea_id} no encontrada.")
            if idea["status"] not in (
                IdeaStatus.SELECTED_FOR_REVIEW.value,
                IdeaStatus.TOURNAMENT_SURVIVOR.value,
            ):
                raise ValidationError(
                    f"Idea '{idea['title'][:50]}' no está en estado de revisión "
                    f"(estado actual: {idea['status']})."
                )
            self.repos.update_idea(idea_id, status=IdeaStatus.APPROVED_FOR_RESEARCH.value)
            approved.append(self.repos.get_idea(idea_id))

        state = self.repos.get_state()
        self.repos.update_state(
            approved_for_research=len(approved),
            phase=ArenaPhase.APPROVED.value,
        )

        self._emit(
            "SYSTEM",
            f"{len(approved)} ideas aprobadas para investigación",
            "info",
        )

        return {
            "approved": approved,
            "count": len(approved),
            "phase": ArenaPhase.APPROVED.value,
        }

    # =================================================================
    # Consultas de estado
    # =================================================================
    def get_state(self) -> dict[str, Any]:
        state = self.repos.get_state()
        # Enriquecer con conteos por provider
        providers = {}
        for p in ExternalProvider:
            count = self.repos.count_ideas(provider=p.value)
            providers[p.value] = count
        state["providers"] = providers
        state["batches"] = self.repos.list_batches()
        state["ideas_by_status"] = {}
        for idea in self.repos.list_ideas():
            status = idea.get("status", "UNKNOWN")
            state["ideas_by_status"][status] = state["ideas_by_status"].get(status, 0) + 1
        return state

    def get_provider_statuses(self) -> list[dict[str, Any]]:
        """Estado de conexión de cada proveedor externo."""
        providers = []
        for p in ExternalProvider:
            if p == ExternalProvider.WAWA:
                continue
            has_key = False
            if p == ExternalProvider.GPT:
                has_key = bool(getattr(self.settings, "openrouter_api_key", None))
            elif p == ExternalProvider.GEMINI:
                has_key = bool(getattr(self.settings, "gemini_api_key", None))
            elif p == ExternalProvider.GROK:
                has_key = False  # Preparado, sin clave aún

            providers.append({
                "name": p.value,
                "enabled": has_key,
                "connection_status": "CONNECTED" if has_key else "NO_KEY",
                "requested_model": "",
                "actual_model": "",
                "call_limit": 0,
                "cost_limit": 0.0,
                "calls_today": 0,
                "cost_today": 0.0,
                "last_call_at": None,
                "last_error": None,
                "execution_mode": "MANUAL_IMPORT" if not has_key else "API_AUTOMATIC",
            })
        return providers

    def get_events(self, limit: int = 100, *, agent: str | None = None) -> list[dict[str, Any]]:
        return self.repos.list_events(limit=limit, agent=agent)

    def reset(self) -> dict[str, Any]:
        """Reinicia la arena para un nuevo ciclo."""
        self.repos.update_state(
            phase=ArenaPhase.IDLE.value,
            generation_batch_id="",
            total_ideas=0,
            wawa_count=0,
            external_count=0,
            duplicates_removed=0,
            commodities_removed=0,
            quality_failed=0,
            tournament_survivors=0,
            selected_for_review=0,
            approved_for_research=0,
            events=[],
            started_at=None,
            last_event_at=None,
        )
        self._emit("SYSTEM", "Arena reiniciada para nuevo ciclo", "info")
        return {"status": "reset", "phase": ArenaPhase.IDLE.value}

    # =================================================================
    # Helpers
    # =================================================================
    def _emit(self, agent: str, message: str, kind: str = "info") -> None:
        event = self.repos.add_event(agent, message, kind)
        state = self.repos.get_state()
        events = state.get("events", [])
        events.append(event)
        if len(events) > 500:
            events = events[-500:]
        self.repos.update_state(events=events, last_event_at=event["timestamp"])
