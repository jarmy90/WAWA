"""Errores de dominio del sistema.

La capa de API traduce estos errores a respuestas HTTP con códigos
apropiados. Mantenerlos aquí centraliza el contrato de errores.
"""
from __future__ import annotations


class AppError(Exception):
    """Error base de la aplicación."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class ProviderUnavailableError(AppError):
    """El proveedor de IA no está disponible, agotó cuota o falló."""

    status_code = 503
    code = "provider_unavailable"


class BudgetExceededError(AppError):
    """El BudgetGuard bloqueó la acción por límite de coste."""

    status_code = 429
    code = "budget_exceeded"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


class ModeBlockedError(AppError):
    """El modo de operación actual bloquea la acción (pausa, apagado, sombra)."""

    status_code = 409
    code = "mode_blocked"
