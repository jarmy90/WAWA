"""Logs estructurados (JSON) a consola y archivo rotativo.

Uso: ``from app.core.logging import get_logger; log = get_logger("scout")``.
Nunca se registran claves ni secretos (ver ``redact``).
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.core.config import get_settings

_RESERVED = {
    "message", "timestamp", "level", "logger",
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_text", "exc_info", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName",
}


class JsonFormatter(logging.Formatter):
    """Formatea cada registro como una línea JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def _setup_logger(name: str, settings) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:  # ya inicializado
        return logger

    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    logger.setLevel(settings.log_level.upper())
    formatter = JsonFormatter()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    file_handler = RotatingFileHandler(
        settings.logs_dir / "app.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger estructurado para el módulo dado."""
    return _setup_logger(f"abl.{name}", get_settings())


def redact(value: Any) -> Any:
    """Elimina secretos conocidos de un valor antes de loguearlo."""
    if isinstance(value, dict):
        return {k: ("***" if "key" in k.lower() or "token" in k.lower() or "secret" in k.lower() else redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value
