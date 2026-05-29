# Build and deploy VRP Studio frontend and backend in one step.
# Usage: .\vrp-studio\deploy.ps1 [-Clean] [-NoStart] [-Port 8000]

param(
    [switch]$Clean = $false,
    [switch]$NoStart = $false,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommandPath }
$RootDir = Split-Path -Parent $ScriptDir
$FrontendDir = Join-Path $ScriptDir "frontend"
$BackendStaticDir = Join-Path $ScriptDir "vrp_studio\frontend"
$VenvPython = Join-Path $RootDir ".venv\Scripts\python.exe"
$HasUv = [bool](Get-Command uv -ErrorAction SilentlyContinue)

function Ensure-Venv {
    if ($HasUv -and -not (Test-Path $VenvPython)) {
        Write-Host "Creating .venv with uv..." -ForegroundColor Cyan
        Push-Location $RootDir
        & uv venv .venv
        if ($LASTEXITCODE -ne 0) { throw "uv venv failed with exit code $LASTEXITCODE" }
        Pop-Location
    } elseif (-not (Test-Path $VenvPython)) {
        Write-Host "Creating .venv with python..." -ForegroundColor Cyan
        & python -m venv (Join-Path $RootDir ".venv")
        if ($LASTEXITCODE -ne 0) { throw "python -m venv failed with exit code $LASTEXITCODE" }
    }
}

function Ensure-Pip {
    & $VenvPython -m pip --version 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Bootstrapping pip with ensurepip..." -ForegroundColor Cyan
        & $VenvPython -m ensurepip --upgrade
        if ($LASTEXITCODE -ne 0) { throw "ensurepip failed with exit code $LASTEXITCODE" }
    }
}

function Install-PythonDeps {
    Write-Host "Installing VRP Studio Python dependencies..." -ForegroundColor Green
    if ($HasUv) {
        & uv pip install --python $VenvPython -r (Join-Path $ScriptDir "requirements.txt") -q
    } else {
        Ensure-Pip
        & $VenvPython -m pip install -r (Join-Path $ScriptDir "requirements.txt") -q
    }
    if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed with exit code $LASTEXITCODE" }
}

function Build-Backend {
    Write-Host "Building and installing local vrp-cli Python bindings..." -ForegroundColor Green
    & (Join-Path $RootDir "build.ps1") -NoRust
    if ($LASTEXITCODE -ne 0) { throw "build.ps1 -NoRust failed with exit code $LASTEXITCODE" }

    Write-Host "Installing vrp-studio package in editable mode..." -ForegroundColor Green
    if ($HasUv) {
        & uv pip install --python $VenvPython --no-deps -e $ScriptDir -q
    } else {
        Ensure-Pip
        & $VenvPython -m pip install --no-deps -e $ScriptDir -q
    }
    if ($LASTEXITCODE -ne 0) { throw "vrp-studio editable install failed with exit code $LASTEXITCODE" }
}

function Build-Frontend {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm not found in PATH. Please install Node.js/npm to build the frontend."
    }

    Write-Host "Building VRP Studio frontend..." -ForegroundColor Green
    if ($Clean) {
        Remove-Item -Path (Join-Path $FrontendDir "dist") -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -Path (Join-Path $BackendStaticDir "dist") -Recurse -Force -ErrorAction SilentlyContinue
    }

    Push-Location $FrontendDir
    if (Test-Path (Join-Path $FrontendDir "package-lock.json")) {
        & npm ci
    } else {
        & npm install
    }
    if ($LASTEXITCODE -ne 0) { throw "npm dependency installation failed with exit code $LASTEXITCODE" }

    & npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build failed with exit code $LASTEXITCODE" }
    Pop-Location

    Write-Host "Deploying frontend assets into backend package..." -ForegroundColor Green
    New-Item -ItemType Directory -Force -Path $BackendStaticDir | Out-Null
    Remove-Item -Path (Join-Path $BackendStaticDir "dist") -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item -Path (Join-Path $FrontendDir "dist") -Destination (Join-Path $BackendStaticDir "dist") -Recurse
}

function Start-Server {
    Write-Host "Starting VRP Studio on http://127.0.0.1:$Port ..." -ForegroundColor Cyan
    if ($HasUv) {
        Push-Location $RootDir
        & uv run --python $VenvPython vrp-studio --port $Port
        Pop-Location
    } else {
        & $VenvPython -m vrp_studio.server --port $Port
    }
}

Ensure-Venv
Install-PythonDeps
Build-Backend
Build-Frontend

if (-not $NoStart) {
    Start-Server
} else {
    Write-Host "Build/deploy complete. Start later with: uv run --python $VenvPython vrp-studio --port $Port" -ForegroundColor Green
}
