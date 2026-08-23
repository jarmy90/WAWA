"""Allowlist de conexiones OmniRoute (iteración 008).

Ninguna conexión puede usarse en PRODUCCIÓN hasta registrar: proveedor,
método de autenticación, términos de servicio, permiso de automatización,
permiso de uso comercial, política de entrenamiento, retención de datos,
región, tipo de datos permitido, fecha de revisión y estado.

Estados: ALLOWED | TEST_ONLY | BLOCKED | UNKNOWN.
Por defecto, UNKNOWN = BLOQUEADO para producción.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

CONNECTION_STATUS = ("ALLOWED", "TEST_ONLY", "BLOCKED", "UNKNOWN")


@dataclass(frozen=True)
class ConnectionPolicy:
    provider: str
    auth_method: str = "api_key"  # api_key | cli_token | web_cookie | oauth | none | unknown
    tos_url: str | None = None
    automation_permitted: bool | None = None
    commercial_use_permitted: bool | None = None
    training_policy: str | None = None  # opcional | prohibido | desconocido
    data_retention: str | None = None
    region: str | None = None
    allowed_data_types: tuple[str, ...] = ("non_personal", "non_confidential")
    review_date: str | None = None
    status: str = "UNKNOWN"
    notes: str = ""


# Registro inicial: TODAS en UNKNOWN/BLOCKED por defecto (nada entra en
# producción sin revisión del propietario). TEST_ONLY solo para pruebas.
OMNIROUTE_CONNECTIONS: dict[str, ConnectionPolicy] = {
    "default": ConnectionPolicy(
        provider="default",
        auth_method="unknown",
        status="UNKNOWN",
        notes="Sin revisión: BLOQUEADO para producción hasta completar el registro.",
    ),
    "omniroute-gateway": ConnectionPolicy(
        provider="omniroute-gateway",
        auth_method="api_key",  # o cli_token si el gateway lo exige
        status="TEST_ONLY",
        review_date=date.today().isoformat(),
        notes="El gateway local de OmniRoute (127.0.0.1) puede PROBARSE; bloqueado para producción "
              "hasta revisar los términos de los proveedores upstream que vaya a usar.",
    ),
    "api-key-providers": ConnectionPolicy(
        provider="api-key-providers",
        auth_method="api_key",
        status="TEST_ONLY",
        review_date=date.today().isoformat(),
        notes="Tiers gratuitos por API key: permitidos SOLO en pruebas hasta revisar ToS de cada proveedor.",
    ),
    "web-cookie-providers": ConnectionPolicy(
        provider="web-cookie-providers",
        auth_method="web_cookie",
        status="BLOCKED",
        notes="Sesiones/cookies de cuentas web: riesgo de ToS y de credenciales. Bloqueado.",
    ),
}


def connection_policy(provider: str | None) -> ConnectionPolicy:
    if not provider:
        return OMNIROUTE_CONNECTIONS["default"]
    key = provider if provider in OMNIROUTE_CONNECTIONS else "default"
    return OMNIROUTE_CONNECTIONS[key]


def is_connection_allowed(provider: str | None, *, production: bool = False) -> tuple[bool, str]:
    """¿Puede usarse esta conexión? production=True exige ALLOWED."""
    policy = connection_policy(provider)
    if policy.status == "ALLOWED":
        return True, "ALLOWED"
    if policy.status == "TEST_ONLY":
        if production:
            return False, "TEST_ONLY: bloqueado para producción"
        return True, "TEST_ONLY: permitido solo en pruebas"
    if policy.status == "BLOCKED":
        return False, "BLOCKED"
    return False, "UNKNOWN: bloqueado para producción (falta revisión)"
