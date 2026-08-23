"""Proveedor OmniRoute (OPCIONAL, AISLADO — iteración 008).

OmniRoute es un gateway local OpenAI-compatible que agrega proveedores y
tiers gratuitos. Se ejecuta como SERVICIO SEPARADO (p. ej.
``infra/omniroute/docker-compose.omniroute.yml``) y NO se mezcla con WAWA.

Reglas:
- Desactivado por defecto (``OMNIROUTE_ENABLED=false``). Solo se usa cuando
  el propietario lo activa explícitamente.
- Endpoint OpenAI-compatible: ``{base_url}/chat/completions`` (base_url ya
  incluye ``/v1``, p. ej. ``http://127.0.0.1:20128/v1``).
- Autenticación local: ``Authorization: Bearer <key>`` si hay clave y
  ``x-omniroute-cli-token`` si hay token. Ambos viven SOLO en el gestor de
  secretos; nunca en logs ni en el repositorio.
- Modelo ``auto`` (routing automático de OmniRoute: ``auto/coding``,
  ``auto/cheap``, ``auto/free:reliable``, ...) se pasa tal cual.
- Reintentos SOLO transitorios (429/5xx/red/timeout), acotados a
  ``max_retries``; nunca infinitos.
- Errores sanitizados: no se propagan secretos, cabeceras ni cuerpos crudos.
- Costes honestos: ``reported_cost`` solo si el proveedor lo devuelve;
  si no, ``None`` con ``cost_source`` UNKNOWN/FREE_TIER y estimación
  etiquetada. ``billing_verified=false`` siempre en esta fase.
- Sin fabricación: si falla, el llamador registra la ausencia como NEUTRAL
  (nunca se sustituye por una respuesta mock).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from app.providers.base import BaseLLMProvider, LLMResponse, extract_json, raise_unavailable

_TRANSIENT_STATUS = {429, 500, 502, 503, 504}
_BACKOFF_BASE_SECONDS = 0.5
_RATE_PER_CHAR = 0.0000005  # estimación grosera LOCAL_ESTIMATE

_REVIEW_TASKS = {"external_review", "external_committee", "auto_review", "synthesis_review"}
_DISCOVERY_TASKS = {"discovery", "classification", "clustering", "evidence_extraction",
                    "solution_generation", "skeptic_review", "summarization"}


class OmniRouteProvider(BaseLLMProvider):
    name = "omniroute"

    def __init__(
        self,
        *,
        enabled: bool = False,
        base_url: str = "http://127.0.0.1:20128/v1",
        api_key: str | None = None,
        cli_token: str | None = None,
        review_model: str = "auto",
        discovery_model: str = "auto",
        fallback_model: str = "auto",
        timeout: float = 60.0,
        max_retries: int = 1,
        max_input_tokens: int | None = None,
        max_output_tokens: int | None = None,
        allow_free_only: bool = True,
        require_model_id: bool = True,
    ) -> None:
        self.enabled = enabled
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.cli_token = cli_token
        self.review_model = review_model
        self.discovery_model = discovery_model
        self.fallback_model = fallback_model
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.allow_free_only = allow_free_only
        self.require_model_id = require_model_id
        self.last_heartbeat_at: str | None = None
        self.last_incident: str | None = None

    # ------------------------------------------------------------------
    def available(self) -> bool:
        """Disponible = activado por configuración (sin red)."""
        return self.enabled and bool(self.base_url)

    def _resolve_model(self, task: str | None, model: str | None) -> str:
        requested = model or (self.review_model if (task or "").lower() in _REVIEW_TASKS else self.discovery_model)
        requested = requested or "auto"
        if requested.lower() in ("auto", ""):
            return "auto"
        if not self.require_model_id:
            return requested
        return requested

    def _truncate_prompt(self, prompt: str) -> str:
        if not self.max_input_tokens:
            return prompt
        max_chars = self.max_input_tokens * 4
        if len(prompt) <= max_chars:
            return prompt
        return prompt[: max_chars - 80] + "\n\n[TRUNCADO por límite de tokens de entrada.]"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "autonomous-business-lab/0.1",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.cli_token:
            headers["x-omniroute-cli-token"] = self.cli_token
        return headers

    def _chat(self, messages: list[dict[str, str]], temperature: float | None,
              model: str, output_schema: dict[str, Any] | None) -> tuple[dict[str, Any], int]:
        body: dict[str, Any] = {"model": model, "messages": messages}
        if temperature is not None:
            body["temperature"] = temperature
        if self.max_output_tokens:
            body["max_tokens"] = self.max_output_tokens
        if output_schema is not None:
            body["response_format"] = {"type": "json_object"}
        url = f"{self.base_url}/chat/completions"
        retries = 0
        while True:
            request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                             headers=self._headers(), method="POST")
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read().decode("utf-8")
                    self.last_heartbeat_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    try:
                        return json.loads(raw), retries
                    except json.JSONDecodeError as exc:
                        raise_unavailable(self.name, RuntimeError(f"JSON inválido en la respuesta: {str(exc)[:120]}"))
            except urllib.error.HTTPError as exc:
                transient = exc.code in _TRANSIENT_STATUS
                if not transient or retries >= self.max_retries:
                    self.last_incident = f"HTTP {exc.code}"
                    detail = exc.read().decode("utf-8", errors="replace")[:200]
                    # Sanitizar: solo el código y un fragmento corto del mensaje de error.
                    raise_unavailable(self.name, RuntimeError(f"HTTP {exc.code}: {_sanitize(detail)}"))
            except (urllib.error.URLError, TimeoutError) as exc:
                self.last_incident = f"red/timeout: {_sanitize(str(exc))[:120]}"
                if retries >= self.max_retries:
                    raise_unavailable(self.name, RuntimeError(self.last_incident))
            retries += 1
            time.sleep(_BACKOFF_BASE_SECONDS * retries)

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        task: str | None = None,
        output_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        if not self.available():
            raise_unavailable(self.name, ValueError("OMNIROUTE_ENABLED=false o base_url vacía"))
        model = self._resolve_model(task, None)
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": self._truncate_prompt(prompt)})

        started = time.monotonic()
        payload, retries = self._chat(messages, temperature, model, output_schema)
        latency_ms = int((time.monotonic() - started) * 1000)

        actual_model = payload.get("model") or model
        actual_provider = payload.get("provider") or payload.get("_provider") \
            or (payload.get("usage") or {}).get("provider") or None
        try:
            text = payload["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise_unavailable(self.name, RuntimeError(f"respuesta inesperada: {str(payload)[:200]}"))
        if not text.strip():
            raise_unavailable(self.name, RuntimeError("respuesta vacía del gateway"))

        usage = payload.get("usage") or {}
        reported_cost: float | None = None
        cost_source = "UNKNOWN"
        for key in ("total_cost", "cost"):
            raw = usage.get(key)
            if isinstance(raw, (int, float)):
                reported_cost = float(raw)
                cost_source = "PROVIDER_RESPONSE"
                break
        if reported_cost is None and (model.lower().endswith(":free") or "free" in model.lower()):
            cost_source = "FREE_TIER"
        estimated = round(len(text) * _RATE_PER_CHAR, 6) if text else None
        structured = extract_json(text) if output_schema else None

        return LLMResponse(
            text=text,
            structured=structured,
            model=model,  # solicitado
            method="omniroute (OpenAI-compatible)",
            cost_estimate_usd=estimated or 0.0,
            cost_method="estimated_api",
            verified=False,
            notes=(
                "Salida de OmniRoute (gateway local) sin verificación externa: hipótesis, nunca evidencia. "
                f"Proveedor real: {actual_provider or 'desconocido'}. Coste: reported={reported_cost} "
                f"fuente={cost_source} billing_verified=False."
            ),
            actual_model=actual_model,
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

    def list_models(self) -> dict[str, Any]:
        """GET {base_url}/models — catálogo (solo si el servicio responde)."""
        if not self.available():
            raise_unavailable(self.name, ValueError("OMNIROUTE_ENABLED=false"))
        url = f"{self.base_url}/models"
        request = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise_unavailable(self.name, RuntimeError(f"HTTP {exc.code} al listar modelos"))
        except (urllib.error.URLError, TimeoutError) as exc:
            raise_unavailable(self.name, exc)

    def health(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "available": self.available(),
            "endpoint": self.base_url,
            "configured": bool(self.api_key or self.cli_token),
            "review_model": self.review_model,
            "discovery_model": self.discovery_model,
            "fallback_model": self.fallback_model,
            "last_heartbeat_at": self.last_heartbeat_at,
            "last_incident": self.last_incident,
        }


def _sanitize(text: str) -> str:
    """Elimina posibles secretos del texto de error (bearer tokens, claves)."""
    import re

    text = re.sub(r"(?i)(bearer\s+)[a-z0-9._-]+", r"\1***", text)
    text = re.sub(r"(?i)(api[_-]?key[\"']?\s*[:=]\s*[\"']?)[a-z0-9._-]+", r"\1***", text)
    return text[:300]
