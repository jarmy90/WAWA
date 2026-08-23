#!/usr/bin/env python3
"""Crea el paquete de revisión de una iteración.

Flujo:
1. Determina el número de iteración (auto: último manifiesto; o --iteration).
2. Comprueba que existe el manifiesto.
3. Aplica exclusiones (secretos, cachés, paquetes previos).
4. Detecta posibles secretos y aborta si encuentra algo no permitido.
5. Crea un ZIP completo del repositorio (sin .git).
6. Evita incluirse a sí mismo y paquetes anteriores.
7. Renombra el ZIP a `.zip.txt` (contenido binario intacto).
8. Calcula SHA-256 y lo escribe en el manifiesto y en el historial.
9. Muestra ruta, tamaño y hash.

Uso:
    python3 scripts/package_for_review.py [--iteration NNN] [--allow-secrets]
"""
from __future__ import annotations

import argparse
import os
import sys
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _review_common import (  # noqa: E402
    DELIVERABLES,
    PACKAGES_DIR,
    ROOT,
    find_manifest,
    latest_iteration,
    scan_text_for_secrets,
    sha256_of,
    should_exclude,
)

TEXT_EXTENSIONS = {".py", ".md", ".txt", ".toml", ".json", ".yml", ".yaml", ".cfg", ".ini", ".html", ".css", ".js", ".sh", ".example"}


def _set_field(text: str, label: str, value: str) -> str:
    """Reemplaza la línea '- **<label>**: <cualquier valor>' por el nuevo valor."""
    import re as _re

    pattern = _re.compile(rf"^- \*\*{_re.escape(label)}\*\*:.*$", _re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(f"- **{label}**: {value}", text)
    return text + f"\n- **{label}**: {value}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Empaqueta el repositorio para revisión externa.")
    parser.add_argument("--iteration", type=int, default=None, help="Número de iteración (por defecto: última + contexto).")
    parser.add_argument("--allow-secrets", action="store_true", help="Solo para depuración: no abortar por secretos detectados.")
    args = parser.parse_args()

    iteration = args.iteration or latest_iteration()
    if iteration == 0:
        print("ERROR: no hay manifiestos. Crea deliverables/ITERATION_001_MANIFEST.md primero.")
        return 1

    manifest = find_manifest(iteration)
    if not manifest.exists():
        print(f"ERROR: no existe el manifiesto {manifest}. Créalo antes de empaquetar.")
        return 1

    today = date.today().isoformat()
    base_name = f"autonomous-business-lab_iteracion-{iteration:03d}_{today}.zip"
    PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = PACKAGES_DIR / base_name
    final_path = zip_path.with_suffix(".zip.txt")

    # --- Escaneo previo de secretos sobre archivos de texto -----------------
    secret_hits: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if should_exclude(rel):
            continue
        if path.suffix.lower() in TEXT_EXTENSIONS and path.stat().st_size < 2_000_000:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for hit in scan_text_for_secrets(text):
                secret_hits.append(f"{rel}: {hit}")
    if secret_hits and not args.allow_secrets:
        print("ERROR: posibles secretos detectados. Corrige antes de empaquetar:")
        for hit in secret_hits[:10]:
            print(f"  - {hit}")
        print(f"  ({len(secret_hits)} en total)")
        return 1

    # --- Crear el ZIP ---------------------------------------------------------
    n_files = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(ROOT.rglob("*")):
            rel = path.relative_to(ROOT)
            if should_exclude(rel):
                continue
            if path.is_file():
                zf.write(path, rel.as_posix())
                n_files += 1
    zip_size = zip_path.stat().st_size

    # --- Renombrar a .zip.txt (solo extensión; binario intacto) --------------
    if final_path.exists():
        final_path.unlink()
    os.rename(zip_path, final_path)
    digest = sha256_of(final_path)

    # --- Actualizar manifiesto con nombre/tamaño/hash ------------------------
    manifest_text = manifest.read_text(encoding="utf-8")
    for label, value in [
        ("Nombre del paquete", final_path.name),
        ("Tamaño del paquete", f"{final_path.stat().st_size} bytes"),
        ("SHA-256 del paquete", digest),
    ]:
        manifest_text = _set_field(manifest_text, label, value)
    manifest.write_text(manifest_text, encoding="utf-8")

    # --- Registrar en el historial -------------------------------------------
    history = ROOT / "docs" / "ITERATION_HISTORY.md"
    if history.exists():
        text = history.read_text(encoding="utf-8")
        entry = (
            f"\n- **Iteración {iteration}** · {datetime.now(timezone.utc).isoformat()} · "
            f"paquete: `{final_path.name}` · tamaño: {final_path.stat().st_size} bytes · "
            f"SHA-256: `{digest}`\n"
        )
        if "HASH_PENDING" in text:
            text = text.replace("HASH_PENDING", digest)
            history.write_text(text, encoding="utf-8")
        else:
            history.write_text(text.rstrip() + entry, encoding="utf-8")

    print("PAQUETE CREADO")
    print(f"  Ruta   : {final_path}")
    print(f"  Tamaño : {final_path.stat().st_size} bytes")
    print(f"  SHA-256: {digest}")
    print(f"  Archivos incluidos: {n_files}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
