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
from app.providers.omniroute import OmniRouteProvider
from app.providers.openrouter import OpenRouterProvider


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
        self.openrouter = OpenRouterProvider(
            settings.openrouter_api_key,
            review_model=settings.openrouter_review_model,
            fallback_model=settings.openrouter_fallback_model,
            timeout=settings.openrouter_timeout_seconds,
            max_retries=settings.openrouter_max_retries,
            max_input_tokens=settings.openrouter_max_input_tokens,
            max_output_tokens=settings.openrouter_max_output_tokens,
        )
        # OmniRoute: proveedor AISLADO. Nunca entra en la resolución automática;
        # solo se usa cuando OMNIROUTE_ENABLED=true y una política de tarea lo
        # permite explícitamente (p. ej. external_committee como 2º revisor).
        self.omniroute = OmniRouteProvider(
            enabled=settings.omniroute_enabled,
            base_url=settings.omniroute_base_url,
            api_key=settings.omniroute_api_key,
            cli_token=settings.omniroute_cli_token,
            review_model=settings.omniroute_review_model,
            discovery_model=settings.omniroute_discovery_model,
            fallback_model=settings.omniroute_fallback_model,
            timeout=settings.omniroute_timeout_seconds,
            max_retries=settings.omniroute_max_retries,
            max_input_tokens=settings.omniroute_max_input_tokens,
            max_output_tokens=settings.omniroute_max_output_tokens,
            allow_free_only=settings.omniroute_allow_free_only,
            require_model_id=settings.omniroute_require_model_id,
        )

    # ------------------------------------------------------------------
    def resolve_primary(self) -> BaseLLMProvider:
        mode = self.settings.llm_provider
        if mode == "mock":
            return self.mock
        if mode == "manual":
            return self.manual
        if mode == "gemini":
            return self.gemini
        if mode == "openrouter":
            return self.openrouter
        # auto: OpenRouter o Gemini si están disponibles; si no, mock.
        if self.openrouter.available():
            return self.openrouter
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
            "openrouter": self.openrouter.health(),
            "omniroute": self.omniroute.health(),
            "gemini": self.gemini.health(),
            "mock": self.mock.health(),
            "manual": self.manual.health(),
        }
