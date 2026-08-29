#!/usr/bin/env python3
"""Generate a focused WAWA_WINDOWS_INSTALLER.zip with only runtime files."""
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'deliverables', 'packages', 'WAWA_WINDOWS_INSTALLER.zip')

# Only include directories essential for running WAWA
INCLUDE_DIRS = {'app', 'frontend', 'scripts', 'tests', 'data/demo', 'data/manual_research'}

SKIP_DIRS = {
    '.git', '.venv', '__pycache__', 'caches', '.pytest_cache',
    'autonomous_business_lab.egg-info', 'node_modules',
    'data/backups', 'data/external_reviews', 'data/freebuff_sessions',
    'data/runtime',
}
SKIP_FILES = {'.env', '.env.local'}

# Root-level files to include
ROOT_INCLUDE = {
    'pyproject.toml', 'START_WAWA.bat', 'STOP_WAWA.bat',
    'start_wawa.sh', 'stop_wawa.sh', 'README.md', 'env.example',
    'Dockerfile', 'docker-compose.yml', '.gitignore',
    'AGENTS.md', 'COMO_ABRIR_WAWA.md', 'SECURITY.md',
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
if os.path.exists(OUT):
    os.remove(OUT)

count = 0
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as zf:
    for dirpath, dirs, files in os.walk(ROOT):
        rel_dir = os.path.relpath(dirpath, ROOT)

        # Skip non-included root directories
        if rel_dir != '.':
            top_dir = rel_dir.split(os.sep)[0]
            if top_dir not in INCLUDE_DIRS and top_dir not in SKIP_DIRS:
                dirs.clear()
                continue

        # Skip excluded dirs
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for f in files:
            if f.endswith('.pyc') or f in SKIP_FILES:
                continue
            fp = os.path.join(dirpath, f)
            rp = os.path.relpath(fp, ROOT)

            # Root-level: only include specific files
            if rel_dir == '.':
                if f not in ROOT_INCLUDE:
                    continue
                if f == 'data/abl.db':
                    continue

            # Skip large data files
            if rp.startswith('data/abl.db'):
                continue

            zf.write(fp, rp)
            count += 1

with zipfile.ZipFile(OUT, 'r') as zf:
    names = zf.namelist()
    required = [
        'scripts/INSTALL_WAWA.ps1',
        'scripts/START_WAWA.ps1',
        'scripts/STOP_WAWA.ps1',
        'scripts/STATUS_WAWA.ps1',
        'scripts/RESTART_WAWA.ps1',
        'app/main.py',
        'app/__init__.py',
        'pyproject.toml',
        'start_wawa.sh',
        'stop_wawa.sh',
        'START_WAWA.bat',
        'STOP_WAWA.bat',
    ]
    print('=== ZIP Verification ===')
    all_ok = True
    for r in required:
        ok = r in names
        if not ok:
            all_ok = False
        print(f'  {"OK" if ok else "MISSING"}: {r}')
    print(f'\nTotal files: {len(names)}')
    print(f'Size: {os.path.getsize(OUT):,} bytes')
    print(f'Path: {OUT}')
    print(f'All checks passed: {all_ok}')
