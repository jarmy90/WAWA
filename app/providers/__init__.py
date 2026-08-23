"""Abstracción de proveedores de IA.

- ``MockProvider``: determinista, offline, gratuito. Es el proveedor por defecto.
- ``GeminiProvider``: opcional. Solo se usa si GEMINI_API_KEY está configurado.
- ``ManualProvider``: asistido por humano/Freebuff (lee JSON de investigación).
- ``ProviderManager``: resolución de proveedor, fallback y control de costes.
"""
from app.providers.manager import ProviderManager
from app.providers.mock import MockProvider
from app.providers.gemini import GeminiProvider
from app.providers.manual import ManualProvider

__all__ = ["ProviderManager", "MockProvider", "GeminiProvider", "ManualProvider"]
