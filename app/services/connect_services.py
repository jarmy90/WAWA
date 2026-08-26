"""Asistente CONECTAR SERVICIOS (iteración 022).

Permite al propietario introducir o comprobar las credenciales de la
oportunidad ganadora en una sola pantalla, sin editar `.env` a mano.

Reglas:

- Los secretos se guardan en el archivo de credenciales LOCAL (`.env`,
  fuera de Git); nunca se devuelven por la API, nunca se loguean y nunca
  entran en los paquetes.
- La API expone SOLO estado (CONNECTED / INVALID / MISSING / EXPIRED) y,
  cuando es seguro, los últimos 4 caracteres de la clave.
- La comprobación es local (presencia + formato conocido): la conexión real
  se confirma en el lanzamiento con el proveedor.
- GitHub permanece CONNECTED (el repositorio actual es el de WAWA).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

SERVICE_SPECS: list[dict[str, Any]] = [
    {
        "id": "stripe",
        "name": "Stripe (cobro)",
        "env_vars": ["STRIPE_SECRET_KEY"],
        "purpose": "Primer pago real (checkout, precio hipótesis 60 EUR)",
        "format_hint": "sk_...",
        "validate": lambda v: bool(v) and v.startswith("sk_"),
    },
    {
        "id": "email",
        "name": "Email transaccional",
        "env_vars": ["EMAIL_API_KEY"],
        "purpose": "Confirmación de pedido y entrega del informe",
        "format_hint": "clave larga (al menos 12 caracteres)",
        "validate": lambda v: bool(v) and len(v) >= 12,
    },
    {
        "id": "hosting",
        "name": "Hosting",
        "env_vars": ["HOSTING_URL"],
        "purpose": "Despliegue de landing y checkout (URL del proyecto)",
        "format_hint": "https://...",
        "validate": lambda v: bool(v) and v.startswith(("https://", "http://")),
        "optional_secret": "HOSTING_TOKEN",
    },
    {
        "id": "domain",
        "name": "Dominio / subdominio",
        "env_vars": ["DOMAIN"],
        "purpose": "URL pública del producto",
        "format_hint": "ejemplo.com o sub.ejemplo.com",
        "validate": lambda v: bool(v) and re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$", v, re.IGNORECASE) is not None,
    },
    {
        "id": "analytics",
        "name": "Analytics",
        "env_vars": ["ANALYTICS_API_KEY"],
        "purpose": "Eventos visits/leads/checkouts/payments",
        "format_hint": "clave larga (al menos 12 caracteres)",
        "validate": lambda v: bool(v) and len(v) >= 12,
    },
    {
        "id": "github",
        "name": "GitHub (repositorio)",
        "env_vars": [],
        "purpose": "Repositorio actual WAWA (los artefactos de producto viven en product/)",
        "format_hint": None,
        "validate": None,
        "always_connected": True,
    },
]


class ConnectServicesService:
    """Estado y guardado local de credenciales del asistente."""

    def __init__(self, settings) -> None:
        self.settings = settings
        self.env_path: Path = getattr(settings, "credentials_env_path", Path(".env"))

    # ------------------------------------------------------------------ status
    def status(self) -> dict[str, Any]:
        env = self._read_env()
        items = []
        for spec in SERVICE_SPECS:
            values = {k: env.get(k) for k in spec["env_vars"]}
            present = [v for v in values.values() if v]
            last4 = None
            if present:
                raw = present[0]
                last4 = raw[-4:] if len(raw) >= 4 else "****"
            state = "CONNECTED"
            if spec.get("always_connected"):
                state = "CONNECTED"
            elif not present:
                state = "MISSING"
            else:
                validator = spec.get("validate")
                if validator is not None and not all(validator(v) for v in present):
                    state = "INVALID"
                if spec.get("optional_secret") and not env.get(spec["optional_secret"]) and state == "CONNECTED":
                    state = "PARTIAL"
            items.append({
                "id": spec["id"],
                "name": spec["name"],
                "env_vars": spec["env_vars"],
                "purpose": spec["purpose"],
                "format_hint": spec.get("format_hint"),
                "status": state,
                "last4": last4,
                "has_value": bool(present),
            })
        return {
            "items": items,
            "note": "Solo se expone estado y últimos 4 caracteres; los valores nunca salen del archivo local de credenciales (.env, fuera de Git).",
            "github_connected": True,
        }

    def save(self, payload: dict[str, str]) -> dict[str, Any]:
        """Guarda credenciales en el archivo local (merge, nunca borra claves
        no indicadas). Devuelve SOLO estados, nunca valores."""
        keys = {k for spec in SERVICE_SPECS for k in spec["env_vars"]}
        keys.add("HOSTING_TOKEN")
        updates: dict[str, str] = {}
        for key, value in (payload or {}).items():
            key = str(key).strip().upper()
            if not key or not key.isidentifier():
                continue
            value = str(value).strip()
            if not value:
                continue
            # Solo acepta variables conocidas del asistente (allowlist estricta).
            if key in keys:
                updates[key] = value
        if not updates:
            return {"saved": False, "message": "No se recibió ninguna credencial conocida para guardar."}
        self._merge_env(updates)
        return {
            "saved": True,
            "message": f"{len(updates)} credencial(es) guardada(s) localmente (fuera de Git).",
            "updated_keys": sorted(updates),
        }

    def check(self, payload: dict[str, str]) -> dict[str, Any]:
        """Comprobación local de formato para las claves indicadas."""
        results = []
        env = self._read_env()
        for key, value in (payload or {}).items():
            key = str(key).strip().upper()
            spec = next((s for s in SERVICE_SPECS if key in s["env_vars"]), None)
            if spec is None:
                results.append({"key": key, "state": "UNKNOWN", "message": "Variable no gestionada por el asistente."})
                continue
            validator = spec.get("validate")
            stored = env.get(key)
            candidate = value if value else stored
            if not candidate:
                results.append({"key": key, "state": "MISSING", "message": "No hay credencial guardada."})
            elif validator is None or validator(candidate):
                results.append({"key": key, "state": "OK", "message": "Formato correcto (conexión real se confirma en el lanzamiento)."})
            else:
                results.append({"key": key, "state": "INVALID", "message": f"Formato incorrecto (se esperaba: {spec.get('format_hint')})."})
        return {"results": results, "note": "Comprobación local de presencia/formato; sin llamadas externas ni revelación de secretos."}

    # ---------------------------------------------------------------- helpers
    def _read_env(self) -> dict[str, str]:
        env: dict[str, str] = {}
        if not self.env_path.exists():
            return env
        try:
            for raw in self.env_path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                if key:
                    env[key] = value
        except OSError:
            return env
        return env

    def _merge_env(self, updates: dict[str, str]) -> None:
        existing = self._read_env()
        lines: list[str] = []
        if self.env_path.exists():
            try:
                lines = self.env_path.read_text(encoding="utf-8").splitlines()
            except OSError:
                lines = []
        seen: set[str] = set()
        merged: list[str] = []
        for raw in lines:
            line = raw.rstrip()
            key = line.partition("=")[0].strip()
            if key in updates:
                merged.append(f"{key}={updates[key]}")
                seen.add(key)
            else:
                merged.append(line)
        for key, value in updates.items():
            if key not in seen:
                merged.append(f"{key}={value}")
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        self.env_path.write_text("\n".join(merged).rstrip("\n") + "\n", encoding="utf-8")
