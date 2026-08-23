"""Lógica compartida por los scripts de empaquetado/verificación.

- Exclusiones de directorios/archivos (secretos, cachés, paquetes previos).
- Detección de secretos por patrones de formato reales de credenciales.
- Utils de rutas y hashing.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERABLES = ROOT / "deliverables"
PACKAGES_DIR = DELIVERABLES / "packages"

EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "packages",  # paquetes de iteraciones anteriores (dentro de deliverables/)
    "external_reviews",  # expedientes generados en runtime (datos, no código)
    "freebuff_sessions",  # sesiones Freebuff generadas en runtime (datos, no código)
    ".idea",
    ".vscode",
}

EXCLUDED_FILE_SUFFIXES = {".pyc", ".pyo", ".db", ".db-wal", ".db-shm", ".log", ".sqlite", ".sqlite3", ".zip"}
EXCLUDED_FILE_PREFIXES = {".env"}

# Patrones de credenciales reales (formatos conocidos). No se incluye un
# patrón genérico "clave=..." para evitar falsos positivos en tests/docs.
SECRET_PATTERNS = [
    re.compile(r"BEGIN (RSA |EC |OPENSSH |DSA |)PRIVATE KEY"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}\b"),  # Google API key
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),  # AWS access key
    re.compile(r"\bsk-[0-9A-Za-z]{20,}\b"),  # OpenAI-style
    re.compile(r"\bghp_[0-9A-Za-z]{30,}\b"),  # GitHub PAT
    re.compile(r"\bgithub_pat_[0-9A-Za-z_]{20,}\b"),
    re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b"),  # Slack
    re.compile(r"\beyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),  # JWT
    # Construido por partes para que el patrón no coincida consigo mismo.
    re.compile(r"-----BEGIN PGP " + r"PRIVATE KEY BLOCK-----"),
    re.compile(r"(?:api[_-]?key|secret|password|passwd|private[_-]?key|access[_-]?token)\s*[=:]\s*[\"'][A-Za-z0-9_\-./+]{24,}[\"']", re.IGNORECASE),
]

PROHIBITED_ENTRY_PARTS = {".git", "node_modules", ".venv", "__pycache__", ".env", "venv"}


def should_exclude(rel: Path) -> bool:
    """¿Debe excluirse este archivo/ruta del paquete?"""
    parts = rel.parts
    if any(part in EXCLUDED_DIRS for part in parts):
        return True
    name = rel.name
    if any(name.startswith(p) for p in EXCLUDED_FILE_PREFIXES):
        return True
    if any(name.endswith(s) for s in EXCLUDED_FILE_SUFFIXES):
        return True
    if name in (".gitignore",):  # se mantiene fuera por higiene (puede revelar estructura)
        return False
    return False


def scan_text_for_secrets(text: str) -> list[str]:
    """Devuelve las coincidencias sospechosas (hasta 3 por archivo)."""
    hits: list[str] = []
    for pattern in SECRET_PATTERNS:
        for match in pattern.findall(text):
            if isinstance(match, tuple):
                match = "".join(match)
            snippet = str(match)[:80]
            if snippet and snippet not in hits:
                hits.append(snippet)
            if len(hits) >= 3:
                return hits
    return hits


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_zip_hash(zip_path: Path, *, exclude: str | None = None) -> str:
    """Hash canónico del contenido de un ZIP (nombres + bytes de cada miembro).

    El manifiesto se autorrefiere: su campo SHA-256 no puede ser el hash del
    archivo completo que lo contiene (dependencia circular). Este hash se
    calcula sobre el contenido de todos los miembros EXCEPTO el manifiesto
    (parámetro ``exclude``), por lo que el valor registrado es siempre
    autoconsistente y detecta cualquier manipulación del resto del paquete.
    No depende del orden de los miembros ni de la compresión.
    """
    import zipfile

    h = hashlib.sha256()
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if exclude and name == exclude:
                continue
            h.update(name.encode("utf-8"))
            h.update(b"\x00")
            h.update(zf.read(name))
    return h.hexdigest()


def find_manifest(iteration: int) -> Path:
    return DELIVERABLES / f"ITERATION_{iteration:03d}_MANIFEST.md"


def latest_iteration() -> int:
    """Detecta la última iteración por manifiestos existentes."""
    if not DELIVERABLES.exists():
        return 0
    nums = []
    for manifest in DELIVERABLES.glob("ITERATION_*_MANIFEST.md"):
        try:
            nums.append(int(manifest.stem.split("_")[1]))
        except (IndexError, ValueError):
            continue
    return max(nums) if nums else 0
