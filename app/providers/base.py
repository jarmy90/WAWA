"""Contrato común de proveedores de IA."""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import ProviderUnavailableError


class LLMResponse(BaseModel):
    """Respuesta normalizada de cualquier proveedor."""

    model_config = ConfigDict(extra="forbid")

    text: str
    structured: dict[str, Any] | None = None
    model: str
    method: str
    cost_estimate_usd: float = 0.0
    cost_method: str = "zero (offline)"
    verified: bool | None = None
    notes: str | None = None
    # --- Rastro honesto de coste/uso (iteración 007) -------------------------
    actual_model: str | None = None  # modelo realmente usado (p. ej. router :free)
    usage: dict[str, Any] | None = None  # prompt/completion/total tokens si el proveedor los da
    latency_ms: int | None = None
    retry_count: int = 0
    reported_cost: float | None = None  # coste explícito del proveedor (None si no verificable)
    cost_source: str = "UNKNOWN"  # PROVIDER_RESPONSE | LOCAL_ESTIMATE | FREE_TIER | UNKNOWN | BILLING_RECONCILIATION
    billing_verified: bool = False  # solo true tras reconciliación con facturación


class BaseLLMProvider(ABC):
    """Interfaz común de proveedores. Nunca lanza errores de red no controlados."""

    name: str = "base"

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        task: str | None = None,
        output_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Genera una respuesta. Lanza ``ProviderUnavailableError`` si no puede servir."""

    @abstractmethod
    def available(self) -> bool:
        """Indica si el proveedor puede servir peticiones ahora mismo."""

    def health(self) -> dict[str, Any]:
        """Diagnóstico para el dashboard."""
        return {"name": self.name, "available": self.available()}


def extract_json(text: str) -> dict[str, Any] | None:
    """Extrae el primer objeto JSON de un texto (robusto ante markdown)."""
    if not text:
        return None
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    # Buscar el bloque JSON más externo (p. ej. dentro de ```json ... ```)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return None


def cost_from_chars(text: str, rate_per_char: float) -> tuple[float, str]:
    """Estimación grosera de coste API por caracteres (documentada como estimación)."""
    if not text:
        return 0.0, "estimated_api"
    return round(len(text) * rate_per_char, 6), "estimated_api"


def raise_unavailable(provider: str, error: Exception) -> None:
    raise ProviderUnavailableError(
        f"El proveedor '{provider}' no está disponible: {error}",
        details={"provider": provider, "reason": str(error)[:500]},
    ) from error
