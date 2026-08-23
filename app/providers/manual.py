"""Proveedor asistido por humano / Freebuff.

Flujo: el sistema escribe una "solicitud de investigación" en
``data/manual_research/requests/`` y el humano (o una sesión de Freebuff)
deposita la respuesta en ``data/manual_research/responses/`` como JSON con
``{"request_id": ..., "content": {...}, "verified": true, "notes": ...}``.

- Si la respuesta existe: se usa como evidencia **verificada** (método manual).
- Si no existe: la tarea devuelve un resultado "pendiente/desconocido" y el
  pipeline continúa sin romperse (el dato queda marcado como desconocido).
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from app.providers.base import BaseLLMProvider, LLMResponse


class ManualProvider(BaseLLMProvider):
    name = "manual"

    def __init__(self, research_dir: Path) -> None:
        self.requests_dir = research_dir / "requests"
        self.responses_dir = research_dir / "responses"
        self.requests_dir.mkdir(parents=True, exist_ok=True)
        self.responses_dir.mkdir(parents=True, exist_ok=True)

    def available(self) -> bool:
        return True  # siempre puede aceptar aportación humana

    def _find_response(self, request_id: str) -> dict[str, Any] | None:
        for f in sorted(self.responses_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if str(data.get("request_id", "")) == request_id:
                return data
        return None

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        task: str | None = None,
        output_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        request_id = uuid.uuid4().hex
        request = {
            "request_id": request_id,
            "task": task,
            "prompt": prompt[:8_000],
            "output_schema": output_schema,
            "how_to_respond": "Crea un JSON en data/manual_research/responses/ con {request_id, content, verified, notes}. content debe seguir el esquema esperado para la tarea.",
        }
        self.requests_dir.mkdir(parents=True, exist_ok=True)
        (self.requests_dir / f"{request_id}.json").write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")

        response = self._find_response(request_id)
        if response is not None:
            content = response.get("content") or {}
            return LLMResponse(
                text=str(content),
                structured=content if isinstance(content, dict) else {"data": content},
                model="manual (humano / Freebuff)",
                method="manual (verificado por humano)",
                cost_estimate_usd=0.0,
                cost_method="free_mode",
                verified=bool(response.get("verified", True)),
                notes=str(response.get("notes", ""))[:2_000],
            )
        return LLMResponse(
            text="Pendiente de investigación manual: la respuesta aún no se ha depositado.",
            structured={
                "pending": True,
                "unknown": True,
                "request_id": request_id,
                "note": "Deposita la investigación en data/manual_research/responses/ y vuelve a evaluar.",
            },
            model="manual (pendiente)",
            method="manual (pendiente — dato desconocido)",
            cost_estimate_usd=0.0,
            cost_method="free_mode",
        )

    def health(self) -> dict[str, Any]:
        pending = len(list(self.requests_dir.glob("*.json")))
        answered = len(list(self.responses_dir.glob("*.json")))
        return {"name": self.name, "available": True, "pending_requests": pending, "responses": answered}
