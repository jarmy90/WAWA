"""Proveedor Gemini (OPCIONAL).

- Solo se activa si ``GEMINI_API_KEY`` está configurado.
- Cualquier fallo (red, cuota 429, timeout, import) lanza
  ``ProviderUnavailableError`` y el sistema hace fallback al proveedor mock.
- Los outputs de Gemini NO se consideran evidencia verificada: la verificación
  es humana o de fuente externa contrastable.
"""
from __future__ import annotations

from typing import Any

from app.providers.base import BaseLLMProvider, LLMResponse, cost_from_chars, extract_json, raise_unavailable

# Tarifa aproximada (USD por carácter) para estimar coste. Documentada como estimación.
GEMINI_FLASH_RATE_PER_CHAR = 0.0000005  # ~0.5 USD por millón de caracteres (orden de magnitud)


class GeminiProvider(BaseLLMProvider):
    name = "gemini"

    def __init__(self, api_key: str | None, model: str = "gemini-1.5-flash", timeout: float = 60.0) -> None:
        self.api_key = api_key
        self.model_name = model
        self.timeout = timeout
        self._client = None

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        if not self.api_key:
            raise_unavailable(self.name, ValueError("GEMINI_API_KEY no configurado"))
        try:
            import google.generativeai as genai  # dependencia opcional

            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model_name)
        except Exception as exc:  # import fallido, modelo inválido, etc.
            raise_unavailable(self.name, exc)

    def available(self) -> bool:
        try:
            self._ensure_client()
            return True
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        task: str | None = None,
        output_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        try:
            self._ensure_client()
            payload = prompt if not system else f"{system}\n\n---\n{prompt}"
            gen_kwargs: dict[str, Any] = {}
            if temperature is not None:
                gen_kwargs["temperature"] = temperature
            response = self._client.generate_content(payload, **gen_kwargs)
            text = response.text or ""
            structured = extract_json(text) if output_schema else None
            cost, method = cost_from_chars(text, GEMINI_FLASH_RATE_PER_CHAR)
            return LLMResponse(
                text=text,
                structured=structured,
                model=self.model_name,
                method="gemini (API)",
                cost_estimate_usd=cost,
                cost_method=method,
                verified=False,
                notes="Salida de Gemini sin verificación externa: tratar como hipótesis, no como evidencia.",
            )
        except Exception as exc:
            raise_unavailable(self.name, exc)

    def health(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available(),
            "model": self.model_name,
            "configured": bool(self.api_key),
        }
