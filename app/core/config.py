"""Configuración centralizada del proyecto.

Todas las opciones se pueden sobreescribir con variables de entorno o un
archivo ``.env`` (ver ``.env.example``). Ningún valor es obligatorio:
el sistema arranca y funciona sin ninguna clave de API.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SCORING_WEIGHTS: dict[str, float] = {
    "pain": 0.20,
    "demand": 0.20,
    "customer_reach": 0.15,
    "automation": 0.15,
    "margin": 0.10,
    "build_speed": 0.10,
    "differentiation": 0.05,
    "safety": 0.05,
}

DEFAULT_DECISION_BANDS: list[dict[str, Any]] = [
    {"min_score": 75, "decision": "approved"},
    {"min_score": 60, "decision": "needs_more_research"},
    {"min_score": 40, "decision": "deferred"},
    {"min_score": 0, "decision": "rejected"},
]


class Settings(BaseSettings):
    """Configuración central. Se lee de variables de entorno y de `.env`."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Identidad -----------------------------------------------------
    app_name: str = "Autonomous Business Lab"
    version: str = "0.1.0"
    log_level: str = "INFO"

    # --- Rutas ---------------------------------------------------------
    data_dir: Path = PROJECT_ROOT / "data"
    database_path: Path = PROJECT_ROOT / "data" / "abl.db"
    logs_dir: Path = PROJECT_ROOT / "data" / "logs"
    manual_research_dir: Path = PROJECT_ROOT / "data" / "manual_research"
    frontend_dir: Path = PROJECT_ROOT / "frontend"

    # --- Proveedores LLM ------------------------------------------------
    llm_provider: Literal["auto", "mock", "gemini", "manual", "openrouter"] = "auto"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"
    gemini_request_timeout: float = 60.0
    openrouter_api_key: str | None = None
    # Modelo FIJO del comité (comparabilidad entre revisiones).
    openrouter_review_model: str = "openai/gpt-4o-mini"
    # Router gratuito como fallback; el modelo real usado puede variar por llamada
    # (se registra siempre `actual_model` en el log de llamadas).
    openrouter_fallback_model: str = "openrouter/free"
    openrouter_timeout_seconds: float = 60.0
    openrouter_max_retries: int = 2
    openrouter_max_input_tokens: int = 6_000
    openrouter_max_output_tokens: int = 2_000
    openrouter_daily_request_limit: int = 30
    openrouter_daily_cost_limit_usd: float = 0.50
    openrouter_monthly_cost_limit_usd: float = 5.00
    openrouter_max_reviews_per_opportunity: int = 1
    openrouter_circuit_breaker_failures: int = 5
    openrouter_circuit_breaker_cooldown_seconds: int = 300

    # --- OmniRoute (OPCIONAL, AISLADO, desactivado por defecto; iteración 008) -
    # Gateway local OpenAI-compatible, servicio separado. NO sustituye a
    # OpenRouter; nunca se usa para Discovery general hasta pasar un A/B.
    omniroute_enabled: bool = False
    omniroute_base_url: str = "http://127.0.0.1:20128/v1"
    omniroute_api_key: str | None = None  # clave del gateway local (gestor de secretos)
    omniroute_cli_token: str | None = None  # header x-omniroute-cli-token (authz local)
    omniroute_review_model: str = "auto"
    omniroute_discovery_model: str = "auto"
    omniroute_fallback_model: str = "auto"
    omniroute_timeout_seconds: float = 60.0
    omniroute_max_retries: int = 1
    omniroute_max_input_tokens: int | None = None
    omniroute_max_output_tokens: int | None = None
    omniroute_daily_request_limit: int = 20
    omniroute_daily_cost_limit_usd: float = 0.0
    omniroute_monthly_cost_limit_usd: float = 0.0
    omniroute_allow_free_only: bool = True
    omniroute_require_model_id: bool = True

    # --- BudgetGuard ----------------------------------------------------
    free_mode: bool = True
    simulation_mode: bool = True
    daily_budget_usd: float = 0.50
    per_opportunity_budget_usd: float = 0.20
    max_deep_evaluations_per_day: int = 5

    # --- Puntuación -----------------------------------------------------
    scoring_weights_json: str | None = None
    decision_bands_json: str | None = None

    # --- Modo de operación (ver docs/OPERATING_MODES.md) ------------------
    # AUTONOMOUS_PRODUCTION está DESACTIVADO por defecto y bloqueado por una
    # regla explícita de capacidad (production_capability_available=false).
    # Una variable de entorno puede, como máximo, llevar al sistema a
    # PRODUCTION_ARMED. La activación final sigue bloqueada en esta iteración
    # (no existe economía real ni integración financiera verificada).
    operating_mode: Literal[
        "development_and_review", "simulation", "shadow_mode", "production_armed", "autonomous_production", "safe_pause"
    ] = "development_and_review"
    engine_activation_key: str | None = None

    # --- Capacidad de producción (regla explícita, auditable) -------------
    # false => AUTONOMOUS_PRODUCTION inaccesible aunque exista clave.
    production_capability_available: bool = False
    production_block_reason: str = "Real financial execution is not implemented or verified"

    # --- Economía (fase AUTONOMOUS_PRODUCTION; por defecto todo desactivado)
    # El capital es un LÍMITE MÁXIMO DE RIESGO, no una obligación de gasto.
    base_currency: str = "USD"
    money_decimals: int = 2
    capital_total_usd: float = 0.0
    reserve_intocable_usd: float = 0.0
    operating_budget_usd: float = 0.0
    max_daily_spend_usd: float = 0.0
    max_per_experiment_usd: float = 0.0
    max_simultaneous_experiments: int = 1
    initial_cycle_days: int = 20
    report_period: Literal["daily", "weekly", "monthly", "disabled"] = "weekly"
    alerts_mode: Literal["critical_only", "all", "disabled"] = "critical_only"

    # --- Umbrales de supervivencia (deterministas, configurables) ----------
    survival_watch_days: float = 7.0
    survival_critical_days: float = 3.0

    # --- Seguridad / límites --------------------------------------------
    max_upload_bytes: int = 1_000_000
    allowed_import_extensions: tuple[str, ...] = (".json",)
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # --- Comité de contraste (revisiones externas, iteración 005) -----------
    # Las revisiones de modelos son OPINIÓN, nunca evidencia. Los umbrales
    # son configurables y deterministas; la ausencia de revisión es NEUTRAL.
    external_reviews_dir: Path = PROJECT_ROOT / "data" / "external_reviews"
    # Sesiones Freebuff-first (iteración 006): checkpoints persistentes.
    freebuff_sessions_dir: Path = PROJECT_ROOT / "data" / "freebuff_sessions"
    review_min_internal_score: float = 72.0
    review_max_finalists_per_week: int = 3
    review_window_hours: int = 48
    review_continue_without_review: bool = True
    review_required_for_sensitive_activities: bool = True
    review_max_file_bytes: int = 200_000
    review_allowed_extensions: tuple[str, ...] = (".txt", ".md", ".markdown")
    # Iteración 009: mínimo de GRUPOS de evidencia independientes para entrar
    # en el comité (además del umbral interno). Deterministica y configurable.
    review_min_evidence_groups: int = 3
    review_packet_version: str = "1"

    # --- Ciclo económico inicial (iteración 009) --------------------------
    # 30 días y 50 USD de capital máximo. La vía A exige 50 USD de ingresos
    # CONFIRMADOS reales; la vía B exige >=1 pago real confirmado + condiciones
    # y concede UNA prórroga de 14 días. Ningún ingreso simulado cuenta.
    cycle_length_days: int = 30
    cycle_capital_usd: float = 50.0
    cycle_extension_days: int = 14
    cycle_max_extensions: int = 1

    # ------------------------------------------------------------------
    def scoring_weights(self) -> dict[str, float]:
        """Pesos de los 8 criterios (0..1, deben sumar 1)."""
        if self.scoring_weights_json:
            try:
                data = json.loads(self.scoring_weights_json)
            except json.JSONDecodeError:
                return dict(DEFAULT_SCORING_WEIGHTS)
            merged = dict(DEFAULT_SCORING_WEIGHTS)
            merged.update({k: float(v) for k, v in data.items() if k in merged})
            return merged
        return dict(DEFAULT_SCORING_WEIGHTS)

    def decision_bands(self) -> list[dict[str, Any]]:
        """Banda de decisión: [(min_score, decision)] ordenadas descendentemente."""
        if self.decision_bands_json:
            try:
                data = json.loads(self.decision_bands_json)
            except json.JSONDecodeError:
                data = []
            if isinstance(data, list) and data:
                return sorted(data, key=lambda b: -float(b.get("min_score", 0)))
        return list(DEFAULT_DECISION_BANDS)

    def ensure_dirs(self) -> None:
        """Crea los directorios de datos necesarios (idempotente)."""
        for d in (
            self.data_dir,
            self.logs_dir,
            self.manual_research_dir / "requests",
            self.manual_research_dir / "responses",
            self.frontend_dir,
            self.external_reviews_dir,
            self.freebuff_sessions_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Singleton de configuración (cacheado)."""
    settings = Settings()
    settings.ensure_dirs()
    return settings
