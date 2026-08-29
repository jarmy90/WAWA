<#
.SYNOPSIS
    Instalador autocontenido de WAWA (Autonomous Business Lab) para Windows.

.DESCRIPTION
    Copia el proyecto completo, crea entorno virtual, instala dependencias
    y arranca la aplicación. Detecta y repara instalaciones parciales.

    Uso:
      powershell -ExecutionPolicy Bypass -File .\scripts\INSTALL_WAWA.ps1

.NOTES
    Iteración 028 — Corregido: SourceRoot ahora apunta a la raíz del proyecto,
    no al directorio scripts/.
#>
$ErrorActionPreference = 'Stop'

# ── 0. Resolver rutas ───────────────────────────────────────────────
$ScriptPath = $MyInvocation.MyCommand.Path
$ScriptsDir = Split-Path -Parent $ScriptPath          # ...\scripts
$SourceRoot = Split-Path -Parent $ScriptsDir           # Raíz del proyecto
$TargetRoot = 'C:\WAWA'
$TempRoot   = 'C:\WAWA.installing'
$BackupRoot = "C:\WAWA.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
$LogFile    = Join-Path $TargetRoot 'logs\install.log'
$VenvPython = Join-Path $TargetRoot '.venv\Scripts\python.exe'

# ── 1. Validar que SourceRoot contiene el proyecto completo ──────────
Write-Host ''
Write-Host '===============================================' -ForegroundColor Cyan
Write-Host '  WAWA — Instalador Windows'                   -ForegroundColor Cyan
Write-Host "  Fuente: $SourceRoot"                          -ForegroundColor Cyan
Write-Host '===============================================' -ForegroundColor Cyan
Write-Host ''

$RequiredItems = @(
    @{ Path = 'app';             Type = 'Directory'; Label = 'app/' },
    @{ Path = 'frontend';        Type = 'Directory'; Label = 'frontend/' },
    @{ Path = 'scripts';         Type = 'Directory'; Label = 'scripts/' },
    @{ Path = 'tests';           Type = 'Directory'; Label = 'tests/' },
    @{ Path = 'pyproject.toml';  Type = 'File';      Label = 'pyproject.toml' },
    @{ Path = 'app\main.py';    Type = 'File';      Label = 'app\main.py' },
    @{ Path = 'scripts\START_WAWA.ps1';  Type = 'File'; Label = 'scripts\START_WAWA.ps1' },
    @{ Path = 'scripts\STOP_WAWA.ps1';   Type = 'File'; Label = 'scripts\STOP_WAWA.ps1' },
    @{ Path = 'scripts\STATUS_WAWA.ps1'; Type = 'File'; Label = 'scripts\STATUS_WAWA.ps1' }
)

$MissingItems = @()
foreach ($item in $RequiredItems) {
    $fullPath = Join-Path $SourceRoot $item.Path
    if ($item.Type -eq 'Directory') {
        if (-not (Test-Path $fullPath -PathType Container)) {
            $MissingItems += $item.Label
        }
    } else {
        if (-not (Test-Path $fullPath -PathType Leaf)) {
            $MissingItems += $item.Label
        }
    }
}

if ($MissingItems.Count -gt 0) {
    Write-Host 'PACKAGE_INCOMPLETE' -ForegroundColor Red
    Write-Host ''
    Write-Host 'Faltan archivos obligatorios en el paquete fuente:' -ForegroundColor Red
    foreach ($m in $MissingItems) {
        Write-Host "  - $m" -ForegroundColor Red
    }
    Write-Host ''
    Write-Host "Directorio fuente resuelto: $SourceRoot" -ForegroundColor Yellow
    Write-Host "Script ejecutado desde:     $ScriptPath" -ForegroundColor Yellow
    Write-Host ''
    Write-Host 'Verifica que descargaste el ZIP completo y ejecutas INSTALL_WAWA.ps1 desde la carpeta scripts\.' -ForegroundColor Yellow
    exit 1
}

Write-Host '[OK] Paquete fuente completo detectado.' -ForegroundColor Green
Write-Host ''

# ── 2. Detectar Python ──────────────────────────────────────────────
Write-Host '[1/10] Comprobando Python...' -ForegroundColor White
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    $python = (Get-Command py -ErrorAction SilentlyContinue).Source
}
if (-not $python) {
    Write-Host 'ERROR: No se encontro Python. Instala Python 3.10+ desde python.org' -ForegroundColor Red
    Write-Host '       y marca "Add Python to PATH" al instalar.' -ForegroundColor Red
    exit 1
}
$pyVersion = & $python --version 2>&1
Write-Host "       Python detectado: $pyVersion" -ForegroundColor Gray
Write-Host ''

# ── 3. Manejar instalacion existente ────────────────────────────────
Write-Host '[2/10] Preparando destino...' -ForegroundColor White

if (Test-Path $TargetRoot) {
    # Verificar si es una instalacion incompleta o funcional
    $hasVenv = Test-Path (Join-Path $TargetRoot '.venv\Scripts\python.exe')
    $hasApp  = Test-Path (Join-Path $TargetRoot 'app\main.py')
    $hasPkg  = Test-Path (Join-Path $TargetRoot 'pyproject.toml')

    if (-not $hasVenv -or -not $hasApp -or -not $hasPkg) {
        Write-Host '       Instalacion parcial detectada. Reparando...' -ForegroundColor Yellow
        # Renombrar como backup
        $BackupRoot = "C:\WAWA.partial.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        Rename-Item -Path $TargetRoot -Destination $BackupRoot -Force
        Write-Host "       Backup parcial: $BackupRoot" -ForegroundColor Gray
    } else {
        # Instalacion completa existente: hacer backup y actualizar
        Write-Host '       Instalacion existente detectada. Creando backup...' -ForegroundColor Yellow
        Rename-Item -Path $TargetRoot -Destination $BackupRoot -Force
        Write-Host "       Backup: $BackupRoot" -ForegroundColor Gray

        # Preservar datos, logs, config y base de datos
        $PreserveDirs = @('data', 'logs', '.env')
        foreach ($d in $PreserveDirs) {
            $src = Join-Path $BackupRoot $d
            if (Test-Path $src) {
                $dstDir = Join-Path $TargetRoot $d
                # Crear directorio temporal para preservar
            }
        }
    }
}

Write-Host ''

# ── 4. Copiar proyecto completo ─────────────────────────────────────
Write-Host '[3/10] Copiando proyecto...' -ForegroundColor White

if (Test-Path $TempRoot) {
    Remove-Item -Path $TempRoot -Recurse -Force
}

# Copiar todo el proyecto
Copy-Item -Path $SourceRoot -Destination $TempRoot -Recurse -Force -Exclude @(
    '.git',
    '.venv',
    '__pycache__',
    '*.pyc',
    'caches',
    '*.egg-info',
    '.pytest_cache',
    'data\abl.db',
    'data\backups\*'
)

# Preservar datos de la instalacion anterior si existe
if (Test-Path $BackupRoot) {
    foreach ($sub in @('data', 'logs', '.env')) {
        $src = Join-Path $BackupRoot $sub
        $dst = Join-Path $TempRoot $sub
        if (Test-Path $src) {
            if (Test-Path $dst) {
                Remove-Item -Path $dst -Recurse -Force
            }
            Copy-Item -Path $src -Destination $dst -Recurse -Force
        }
    }
    Write-Host '       Datos y configuracion preservados.' -ForegroundColor Gray
}

# Validar que la copia temporal tiene los archivos obligatorios
foreach ($item in $RequiredItems) {
    $fullPath = Join-Path $TempRoot $item.Path
    if ($item.Type -eq 'Directory') {
        if (-not (Test-Path $fullPath -PathType Container)) {
            Write-Host "ERROR: Falta $item.Label despues de copiar" -ForegroundColor Red
            Remove-Item -Path $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
            exit 1
        }
    } else {
        if (-not (Test-Path $fullPath -PathType Leaf)) {
            Write-Host "ERROR: Falta $item.Label despues de copiar" -ForegroundColor Red
            Remove-Item -Path $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
            exit 1
        }
    }
}

# Renombrar temporal -> destino
if (Test-Path $TargetRoot) {
    Remove-Item -Path $TargetRoot -Recurse -Force -ErrorAction SilentlyContinue
}
Rename-Item -Path $TempRoot -Destination $TargetRoot -Force
Write-Host "       Proyecto copiado a $TargetRoot" -ForegroundColor Gray
Write-Host ''

# ── 5. Crear directorios de datos ──────────────────────────────────
Write-Host '[4/10] Preparando directorios...' -ForegroundColor White
$dirsToCreate = @(
    (Join-Path $TargetRoot 'data'),
    (Join-Path $TargetRoot 'data\backups'),
    (Join-Path $TargetRoot 'data\logs'),
    (Join-Path $TargetRoot 'data\runtime\logs'),
    (Join-Path $TargetRoot 'data\external_reviews'),
    (Join-Path $TargetRoot 'data\freebuff_sessions'),
    (Join-Path $TargetRoot 'data\manual_research'),
    (Join-Path $TargetRoot 'data\manual_research\requests'),
    (Join-Path $TargetRoot 'data\manual_research\responses'),
    (Join-Path $TargetRoot 'logs')
)
foreach ($d in $dirsToCreate) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}
Write-Host '       Directorios creados.' -ForegroundColor Gray
Write-Host ''

# ── 6. Crear entorno virtual ────────────────────────────────────────
Write-Host '[5/10] Creando entorno virtual...' -ForegroundColor White
$venvDir = Join-Path $TargetRoot '.venv'
if (-not (Test-Path $venvDir)) {
    & $python -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'ERROR: Fallo al crear el entorno virtual' -ForegroundColor Red
        exit 1
    }
    Write-Host '       Entorno virtual creado.' -ForegroundColor Gray
} else {
    Write-Host '       Entorno virtual existente reutilizado.' -ForegroundColor Gray
}
Write-Host ''

# ── 7. Actualizar pip e instalar dependencias ───────────────────────
Write-Host '[6/10] Instalando dependencias...' -ForegroundColor White
if (-not (Test-Path $VenvPython)) {
    Write-Host "ERROR: No se encontro Python en el venv: $VenvPython" -ForegroundColor Red
    exit 1
}

# Actualizar pip silenciosamente
& $VenvPython -m pip install --quiet --upgrade pip setuptools wheel 2>&1 | Out-Null

# Instalar usando pyproject.toml (edicion editable con extras dev)
Set-Location $TargetRoot
& $VenvPython -m pip install --quiet -e '.[dev]'
if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERROR: Fallo al instalar dependencias con pip' -ForegroundColor Red
    Write-Host '       Revisa que pyproject.toml existe y es valido.' -ForegroundColor Yellow
    exit 1
}
Write-Host '       Dependencias instaladas.' -ForegroundColor Gray
Write-Host ''

# ── 8. Inicializar base de datos ────────────────────────────────────
Write-Host '[7/10] Inicializando base de datos...' -ForegroundColor White
& $VenvPython -c "from app.repositories.db import init_db; from app.core.config import get_settings; init_db(get_settings()); print('       SQLite OK')"
if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERROR: Fallo al inicializar la base de datos' -ForegroundColor Red
    exit 1
}
Write-Host ''

# ── 9. Verificar OmniRoute ──────────────────────────────────────────
Write-Host '[8/10] Comprobando OmniRoute...' -ForegroundColor White
try {
    $omniResp = Invoke-WebRequest -Uri 'http://127.0.0.1:20128/v1/models' -Method GET -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    Write-Host '       OmniRoute: DISPONIBLE' -ForegroundColor Green
} catch {
    Write-Host '       OmniRoute: NO DISPONIBLE (esto es normal; WAWA funciona sin el)' -ForegroundColor Yellow
}
Write-Host ''

# ── 10. Aplicar bootstrap comercial ─────────────────────────────────
Write-Host '[9/10] Aplicando bootstrap comercial...' -ForegroundColor White
$bootstrapScript = Join-Path $TargetRoot 'scripts\startup_bootstrap.py'
if (Test-Path $bootstrapScript) {
    & $VenvPython $bootstrapScript
    if ($LASTEXITCODE -ne 0) {
        Write-Host '       AVISO: Bootstrap fallo, pero WAWA puede arrancar de todas formas.' -ForegroundColor Yellow
    }
} else {
    Write-Host '       Script de bootstrap no encontrado. Continuando...' -ForegroundColor Yellow
}
Write-Host ''

# ── 11. Arrancar WAWA ──────────────────────────────────────────────
Write-Host '[10/10] Arrancando WAWA...' -ForegroundColor White
$startScript = Join-Path $TargetRoot 'scripts\START_WAWA.ps1'
if (Test-Path $startScript) {
    & powershell -ExecutionPolicy Bypass -File $startScript
} else {
    # Fallback: arrancar directamente con uvicorn
    $host_addr = '127.0.0.1'
    $port = 8000
    $url = "http://${host_addr}:${port}"

    Start-Process -FilePath $VenvPython -ArgumentList "-m", "uvicorn", "app.main:app", "--host", $host_addr, "--port", $port -WindowStyle Hidden -PassThru | ForEach-Object {
        $_.Id | Out-File -FilePath (Join-Path $TargetRoot 'logs\wawa.pid') -Encoding ASCII -NoNewline
    }

    Write-Host "       Esperando respuesta en $url ..." -ForegroundColor Gray
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "$url/api/health" -Method GET -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
            $ready = $true
            break
        } catch {
            Start-Sleep -Seconds 1
        }
    }

    if ($ready) {
        Write-Host ''
        Write-Host '===============================================' -ForegroundColor Green
        Write-Host '  WAWA instalado y arrancado!'                  -ForegroundColor Green
        Write-Host "  Owner Command Center: $url"                    -ForegroundColor Green
        Write-Host '===============================================' -ForegroundColor Green
        Start-Process $url
    } else {
        Write-Host ''
        Write-Host '  AVISO: WAWA instalado pero el servidor no respondio.' -ForegroundColor Yellow
        Write-Host "  Abre manualmente: $url" -ForegroundColor Yellow
        Write-Host "  Logs: $TargetRoot\logs\wawa.log" -ForegroundColor Yellow
    }
}

Write-Host ''
Write-Host '===============================================' -ForegroundColor Cyan
Write-Host '  INSTALACION COMPLETADA'                        -ForegroundColor Cyan
Write-Host "  Ubicacion: $TargetRoot"                        -ForegroundColor Cyan
Write-Host '  Para iniciar: START_WAWA.bat'                   -ForegroundColor Cyan
Write-Host '  Para detener:  STOP_WAWA.bat'                   -ForegroundColor Cyan
Write-Host '===============================================' -ForegroundColor Cyan
