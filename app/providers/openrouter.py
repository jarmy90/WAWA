"""Proveedor OpenRouter (OPCIONAL, iteración 007 — comité de contraste).

- Solo se activa si ``OPENROUTER_API_KEY`` está configurado (``sk-or-v1-...``).
- ``review_model`` es el modelo FIJO del comité (comparabilidad); si falla se
  puede usar ``fallback_model`` (router gratuito ``openrouter/free``), cuyo
  modelo real por llamada puede variar: SIEMPRE se registra
  ``requested_model`` y ``actual_model`` en ``llm_call_log``.
- Reintentos SOLO ante errores transitorios (429/5xx/red/timeout), acotados a
  ``max_retries``; errores permanentes (401/403/400) no reintentan.
- Topes de tokens de entrada/salida configurables.
- Costes honestos: ``reported_cost`` solo si el proveedor lo devuelve
  (``PROVIDER_RESPONSE``); si no, ``reported_cost=None`` con ``cost_source``
  ``FREE_TIER``/``UNKNOWN`` y una estimación etiquetada. ``billing_verified``
  es siempre ``False`` en esta fase (no hay reconciliación con facturación).
  Un coste desconocido NUNCA se convierte en cero.
- La salida NO es evidencia: ``verified=False`` siempre.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from app.providers.base import BaseLLMProvider, LLMResponse, extract_json, raise_unavailable

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_RATE_PER_CHAR = 0.0000005  # estimación grosera solo para LOCAL_ESTIMATE
# Códigos HTTP considerados transitorios (se reintentan) frente a permanentes.
_TRANSIENT_STATUS = {429, 500, 502, 503, 504}
_BACKOFF_BASE_SECONDS = 0.5


class OpenRouterProvider(BaseLLMProvider):
    name = "openrouter"

    def __init__(
        self,
        api_key: str | None,
        review_model: str = "openai/gpt-4o-mini",
        fallback_model: str = "openrouter/free",
        timeout: float = 60.0,
        max_retries: int = 2,
        max_input_tokens: int = 6_000,
        max_output_tokens: int = 2_000,
        base_url: str = OPENROUTER_BASE_URL,
    ) -> None:
        self.api_key = api_key
        self.review_model = review_model
        self.fallback_model = fallback_model
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.base_url = base_url

    def available(self) -> bool:
        return bool(self.api_key and self.review_model)

    # ------------------------------------------------------------------
    def _truncate_prompt(self, prompt: str) -> str:
        """Acota a ``max_input_tokens`` (estimación 4 caracteres ≈ 1 token)."""
        max_chars = self.max_input_tokens * 4
        if len(prompt) <= max_chars:
            return prompt
        return prompt[: max_chars - 80] + "\n\n[TRUNCADO por límite de tokens de entrada.]"

    def _chat(self, messages: list[dict[str, str]], temperature: float | None) -> tuple[dict[str, Any], int]:
        """Ejecuta la llamada con reintentos acotados. Devuelve (payload, retries)."""
        body: dict[str, Any] = {
            "model": self.review_model,
            "messages": messages,
        }
        if temperature is not None:
            body["temperature"] = temperature
        body["max_tokens"] = self.max_output_tokens

        retries = 0
        while True:
            request = urllib.request.Request(
                self.base_url,
                data=json.dumps(body).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/jarmy90/WAWA",
                    "X-Title": "Autonomous Business Lab",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8")), retries
            except urllib.error.HTTPError as exc:
                transient = exc.code in _TRANSIENT_STATUS
                if not transient or retries >= self.max_retries:
                    detail = exc.read().decode("utf-8", errors="replace")[:300]
                    raise_unavailable(self.name, RuntimeError(f"HTTP {exc.code}: {detail}"))
            except (urllib.error.URLError, TimeoutError):
                if retries >= self.max_retries:
                    raise_unavailable(self.name, RuntimeError("red/timeout tras reintentos"))
            retries += 1
            time.sleep(_BACKOFF_BASE_SECONDS * retries)

    def _cost_from_payload(self, payload: dict[str, Any], actual_model: str | None) -> tuple[float | None, float | None, str, str]:
        """(reported_cost, estimated_cost, cost_source, nota) honestos."""
        usage = payload.get("usage") or {}
        reported: float | None = None
        source = CostSourceChoices.unknown
        note = "El proveedor no devolvió un coste explícito; coste desconocido (no se asume cero)."
        # OpenRouter puede incluir el coste en usage (total_cost/cost).
        for key in ("total_cost", "cost", "completion_cost", "prompt_cost"):
            raw = usage.get(key)
            if isinstance(raw, (int, float)):
                reported = float(raw)
                source = CostSourceChoices.provider_response
                note = "Coste devuelto por el proveedor en la respuesta (sin reconciliar con facturación)."
                break
        text_used = str(payload.get("choices", [{}])[0].get("message", {}).get("content") or "")
        estimated = round(len(text_used) * OPENROUTER_RATE_PER_CHAR, 6) if text_used else None
        if reported is None:
            if actual_model and (actual_model.endswith(":free") or actual_model.startswith("openrouter/")):
                source = CostSourceChoices.free_tier
                note = "Router gratuito / modelo :free: no se espera cargo, pero no está verificado contra facturación."
            else:
                source = CostSourceChoices.unknown
        return reported, estimated, source, note

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        task: str | None = None,
        output_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        if not self.api_key:
            raise_unavailable(self.name, ValueError("OPENROUTER_API_KEY no configurado"))
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": self._truncate_prompt(prompt)})

        started = time.monotonic()
        try:
            payload, retries = self._chat(messages, temperature)
        except Exception as exc:
            raise_unavailable(self.name, exc)
        latency_ms = int((time.monotonic() - started) * 1000)

        actual_model = payload.get("model") or self.review_model
        usage = payload.get("usage") or {}
        try:
            text = payload["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise_unavailable(self.name, RuntimeError(f"respuesta inesperada: {str(payload)[:200]}"))

        reported_cost, estimated_cost, cost_source, cost_note = self._cost_from_payload(payload, actual_model)
        structured = extract_json(text) if output_schema else None
        notes = (
            "Salida de OpenRouter sin verificación externa: tratar como hipótesis, nunca como evidencia. "
            f"Coste: {cost_note}"
        )
        return LLMResponse(
            text=text,
            structured=structured,
            model=self.review_model,  # solicitado (fijo, comparabilidad)
            actual_model=actual_model,  # realmente usado (puede variar en router :free)
            method="openrouter (API)",
            cost_estimate_usd=estimated_cost or 0.0,
            cost_method="estimated_api",
            verified=False,
            notes=notes,
            usage={
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
            latency_ms=latency_ms,
            retry_count=retries,
            reported_cost=reported_cost,
            cost_source=cost_source,
            billing_verified=False,
        )

    def health(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available(),
            "review_model": self.review_model,
            "fallback_model": self.fallback_model,
            "configured": bool(self.api_key),
        }


class CostSourceChoices:
    provider_response = "PROVIDER_RESPONSE"
    local_estimate = "LOCAL_ESTIMATE"
    billing_reconciliation = "BILLING_RECONCILIATION"
    free_tier = "FREE_TIER"
    unknown = "UNKNOWN"
