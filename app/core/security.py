"""Utilidades de seguridad transversales.

- Límites de tamaño de payloads.
- Lista blanca de extensiones para importaciones.
- Validación de identificadores (UUID) para evitar path traversal.
- Nunca se ejecuta código generado; no hay operaciones financieras.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.core.errors import PayloadTooLargeError, ValidationError

UUID_RE = re.compile(r"^[0-9a-fA-F]{32}$")


def validate_payload_size(size_bytes: int, max_bytes: int) -> None:
    """Rechaza payloads mayores que el límite configurado."""
    if size_bytes > max_bytes:
        raise PayloadTooLargeError(
            f"El payload supera el límite de {max_bytes} bytes.",
            details={"size_bytes": size_bytes, "max_bytes": max_bytes},
        )


def validate_extension(filename: str, allowed: tuple[str, ...]) -> str:
    """Comprueba que la extensión esté en la lista blanca. Devuelve la extensión."""
    ext = Path(filename or "").suffix.lower()
    if ext not in allowed:
        raise ValidationError(
            f"Extensión '{ext or '(sin extensión)'}' no permitida. Permitidas: {', '.join(allowed)}",
            details={"filename": filename},
        )
    return ext


def validate_uuid(value: str, field: str = "id") -> str:
    """Valida un identificador de 32 hex (uuid4 sin guiones). Evita inyección de rutas."""
    if not UUID_RE.match(value):
        raise ValidationError(f"Identificador inválido para '{field}'.")
    return value


def safe_text(value: str | None, *, max_len: int = 20_000) -> str | None:
    """Acota textos a un tamaño máximo razonable."""
    if value is None:
        return None
    value = value.strip()
    return value[:max_len]


def ensure_numeric_range(value: float, lo: float, hi: float, field: str) -> float:
    if not (lo <= value <= hi):
        raise ValidationError(f"'{field}' debe estar entre {lo} y {hi}.")
    return value
