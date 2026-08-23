"""Gestor de proveedores: resolución, fallback y registro de costes.

Flujo de ``generate``:
1. Resuelve el proveedor principal según configuración (auto/mock/gemini/manual).
2. Comprueba presupuesto (BudgetGuard). Si excede, lanza ``BudgetExceededError``
   (nunca se gasta más de lo permitido).
3. Intenta generar. Si el proveedor lanza ``ProviderUnavailableError`` (fallo,
   cuota, no configurado), hace fallback al proveedor mock determinista y lo
   registra como error en el resultado (NO silencioso).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings
from app.core.errors import BudgetExceededError, ProviderUnavailableError
from app.providers.base import BaseLLMProvider, LLMResponse
from app.providers.gemini import GeminiProvider
from app.providers.manual import ManualProvider
from app.providers.mock import MockProvider


@dataclass
class ProviderCall:
    response: LLMResponse
    provider: str
    fallback_used: bool = False
    errors: list[str] = field(default_factory=list)


class ProviderManager:
    """Punto único de acceso a proveedores de IA."""

    def __init__(self, settings: Settings, budget_guard: Any | None = None) -> None:
        self.settings = settings
        self.budget = budget_guard
        self.mock = MockProvider()
        self.gemini = GeminiProvider(settings.gemini_api_key, settings.gemini_model, settings.gemini_request_timeout)
        self.manual = ManualProvider(settings.manual_research_dir)

    # ------------------------------------------------------------------
    def resolve_primary(self) -> BaseLLMProvider:
        mode = self.settings.llm_provider
        if mode == "mock":
            return self.mock
        if mode == "manual":
            return self.manual
        if mode == "gemini":
            return self.gemini
        # auto: Gemini si está disponible; si no, mock.
        return self.gemini if self.gemini.available() else self.mock

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        task: str | None = None,
        output_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
        opportunity_id: str | None = None,
        action: str = "llm_call",
    ) -> ProviderCall:
        primary = self.resolve_primary()

        # Control de costes antes de gastar.
        if self.budget is not None:
            self.budget.check(action=action, opportunity_id=opportunity_id, estimated=0.0)

        errors: list[str] = []
        fallback_used = False
        try:
            response = primary.generate(prompt, system=system, task=task, output_schema=output_schema, temperature=temperature)
        except ProviderUnavailableError as exc:
            errors.append(str(exc))
            fallback_used = True
            response = self.mock.generate(prompt, system=system, task=task, output_schema=output_schema, temperature=temperature)

        # Registrar coste estimado (0 en offline/free).
        if self.budget is not None:
            self.budget.spend(
                action=action,
                opportunity_id=opportunity_id,
                provider=f"{primary.name}{' (fallback: mock)' if fallback_used else ''}",
                estimated_usd=response.cost_estimate_usd,
                cost_method=response.cost_method,
            )
        return ProviderCall(response=response, provider=primary.name, fallback_used=fallback_used, errors=errors)

    def health(self) -> dict[str, Any]:
        primary = self.resolve_primary()
        return {
            "mode": self.settings.llm_provider,
            "primary": primary.health(),
            "gemini": self.gemini.health(),
            "mock": self.mock.health(),
            "manual": self.manual.health(),
        }
