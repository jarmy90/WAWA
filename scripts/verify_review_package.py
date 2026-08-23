#!/usr/bin/env python3
"""Verifica un paquete de revisión (.zip.txt).

Comprueba (15 puntos):
1. El fichero existe.
2. Termina en `.zip.txt`.
3. Posee firma binaria ZIP (PK\\x03\\x04).
4. Puede abrirse como ZIP.
5. Supera la prueba de integridad (testzip).
6. Puede extraerse temporalmente.
7. No presenta path traversal.
8. No contiene rutas absolutas.
9. Incluye README.md.
10. Incluye AGENTS.md.
11. Incluye el manifiesto correcto (del número de iteración del nombre).
12. No contiene archivos prohibidos.
13. No contiene secretos detectables.
14. No contiene el propio paquete (deliverables/packages/).
15. El SHA-256 coincide con el registrado en el manifiesto interno.

Uso:
    python3 scripts/verify_review_package.py [--path ruta.zip.txt] [--iteration NNN]
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _review_common import (  # noqa: E402
    DELIVERABLES,
    PACKAGES_DIR,
    PROHIBITED_ENTRY_PARTS,
    ROOT,
    canonical_zip_hash,
    scan_text_for_secrets,
    sha256_of,
)

TEXT_EXTENSIONS = {".py", ".md", ".txt", ".toml", ".json", ".yml", ".yaml", ".cfg", ".ini", ".html", ".css", ".js", ".sh", ".example"}
FAILURES: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    status = "OK " if ok else "FAIL"
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILURES.append(label)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica un paquete de revisión.")
    parser.add_argument("--path", type=str, default=None, help="Ruta al .zip.txt (por defecto: el más reciente).")
    parser.add_argument("--iteration", type=int, default=None, help="Número de iteración esperado.")
    args = parser.parse_args()

    if args.path:
        package = Path(args.path)
    else:
        candidates = sorted(PACKAGES_DIR.glob("*.zip.txt")) if PACKAGES_DIR.exists() else []
        if not candidates:
            print("ERROR: no hay paquetes .zip.txt en deliverables/packages/.")
            return 1
        package = candidates[-1]

    print(f"Paquete: {package}")
    check(package.exists(), "1. El fichero existe")
    if not package.exists():
        return 1

    check(package.name.endswith(".zip.txt"), "2. Termina en .zip.txt")

    with open(package, "rb") as fh:
        head = fh.read(4)
    check(head == b"PK\x03\x04", "3. Firma binaria ZIP")

    check(zipfile.is_zipfile(package), "4. Puede abrirse como ZIP")

    # re.search (no re.match): el nombre empieza por el prefijo del proyecto.
    m = re.search(r"iteracion-(\d{3})_", package.name)
    iteration = args.iteration or (int(m.group(1)) if m else 0)
    expected_manifest = f"deliverables/ITERATION_{iteration:03d}_MANIFEST.md"

    try:
        with zipfile.ZipFile(package) as zf:
            check(zf.testzip() is None, "5. Integridad (testzip)")

            names = zf.namelist()

            traversal = [n for n in names if ".." in n.split("/")]
            check(not traversal, "7. Sin path traversal", f"{len(traversal)} entradas")

            absolute = [n for n in names if n.startswith("/") or re.match(r"^[A-Za-z]:", n)]
            check(not absolute, "8. Sin rutas absolutas", f"{len(absolute)} entradas")

            check("README.md" in names, "9. Incluye README.md")
            check("AGENTS.md" in names, "10. Incluye AGENTS.md")
            check(expected_manifest in names, "11. Incluye el manifiesto correcto", expected_manifest)

            prohibited = [n for n in names if any(p in n.split("/") for p in PROHIBITED_ENTRY_PARTS)]
            check(not prohibited, "12. Sin archivos prohibidos", f"{len(prohibited)} entradas")

            self_package = [n for n in names if n.startswith("deliverables/packages/")]
            check(not self_package, "14. No contiene paquetes anteriores/propios")

            # 6. Extracción temporal segura
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    zf.extractall(tmp)
                    check(True, "6. Extracción temporal OK")
            except Exception as exc:  # noqa: BLE001
                check(False, "6. Extracción temporal OK", str(exc))

            # 13. Escaneo de secretos sobre entradas de texto
            secret_hits: list[str] = []
            for name in names:
                if Path(name).suffix.lower() not in TEXT_EXTENSIONS:
                    continue
                try:
                    text = zf.read(name).decode("utf-8", errors="ignore")
                except Exception:  # noqa: BLE001
                    continue
                for hit in scan_text_for_secrets(text):
                    secret_hits.append(f"{name}: {hit}")
            check(not secret_hits, "13. Sin secretos detectables", f"{len(secret_hits)} coincidencias" if secret_hits else "")

            # 15. SHA-256 registrado vs real. El hash autoritativo está en el
            # manifiesto en disco (el del interior del ZIP se escribe después de
            # empaquetar, porque el hash depende del contenido del artefacto).
            recorded_hash = None
            disk_manifest = DELIVERABLES / f"ITERATION_{iteration:03d}_MANIFEST.md"
            if disk_manifest.exists():
                mh = re.search(r"SHA-256 del paquete[^\n]*[:：]\s*([0-9a-f]{64})", disk_manifest.read_text(encoding="utf-8", errors="ignore"))
                if mh:
                    recorded_hash = mh.group(1)
            if not recorded_hash:
                history = ROOT / "docs" / "ITERATION_HISTORY.md"
                if history.exists():
                    mh = re.search(rf"Iteración {iteration}.*?SHA-256[^`]*`([0-9a-f]{{64}})`", history.read_text(encoding="utf-8"), re.DOTALL)
                    if mh:
                        recorded_hash = mh.group(1)
            # Hash canónico: el manifiesto se autorrefiere (su hash no puede
            # ser el del archivo completo que lo contiene), así que se compara
            # el hash del contenido del ZIP excluyendo el manifiesto.
            real_hash = canonical_zip_hash(package, exclude=expected_manifest)
            if recorded_hash:
                check(recorded_hash == real_hash, "15. SHA-256 coincide con el registrado", f"{real_hash[:16]}…")
            else:
                check(False, "15. SHA-256 coincide con el registrado", "no hay hash registrado en el manifiesto/historial")
    except Exception as exc:  # noqa: BLE001
        check(False, "Apertura del ZIP", str(exc))
        return 1

    print(f"\nSHA-256 (canónico): {real_hash}")
    print(f"SHA-256 (archivo completo, referencia): {sha256_of(package)}")
    if FAILURES:
        print(f"\nRESULTADO: FALLO ({len(FAILURES)} comprobaciones fallidas)")
        for label in FAILURES:
            print(f"  - {label}")
        return 1
    print("\nRESULTADO: VÁLIDO (15/15 comprobaciones)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
