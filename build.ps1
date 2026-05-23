# Build Rust workspace and Python packages in one step
# Usage: .\build.ps1 [options]
# Options:
#   -Clean     Remove build artifacts before building
#   -Release   Build in release mode (default)
#   -Debug     Build in debug mode
#   -NoPython  Skip Python wheel build and install
#   -NoRust    Skip Rust build

param(
    [switch]$Clean = $false,
    [switch]$Release = $true,
    [switch]$Debug = $false,
    [switch]$NoPython = $false,
    [switch]$NoRust = $false
)

$ErrorActionPreference = "Stop"

# Get root directory - handle both direct execution and dot-sourcing
if ($PSScriptRoot) {
    $RootDir = $PSScriptRoot
} elseif ($MyInvocation.MyCommandPath) {
    $RootDir = Split-Path -Parent $MyInvocation.MyCommandPath
} else {
    $RootDir = Get-Location
}

$VenvPython = Join-Path $RootDir ".venv\Scripts\python.exe"

# Determine build profile
$BuildProfile = if ($Debug) { "debug" } else { "release" }
$CargoArgs = @("build")
if (-not $Debug) { $CargoArgs += "--release" }

Write-Host "=== VRP Build Script ===" -ForegroundColor Cyan
Write-Host "Root directory: $RootDir"
Write-Host "Build profile: $BuildProfile"
Write-Host ""

# Step 0: Check prerequisites
if (-not (Test-Path $VenvPython)) {
    Write-Host "ERROR: Python virtual environment not found at $VenvPython" -ForegroundColor Red
    Write-Host "Please create a .venv with: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

# Step 1: Clean (optional)
if ($Clean) {
    Write-Host "Step 1: Cleaning build artifacts..." -ForegroundColor Green
    try {
        Write-Host "  - Removing target/ ..."
        Remove-Item -Path (Join-Path $RootDir "target") -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  - Removing vrp-cli/target/ ..."
        Remove-Item -Path (Join-Path $RootDir "vrp-cli\target") -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  - Removing build wheels ..."
        Remove-Item -Path (Join-Path $RootDir "target\wheels") -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  Clean complete." -ForegroundColor Green
    }
    catch {
        Write-Host "  WARNING: Some cleanup failed (may be locked): $_" -ForegroundColor Yellow
    }
    Write-Host ""
}

# Step 2: Build Rust workspace (unless skipped)
if (-not $NoRust) {
    Write-Host "Step 2: Building Rust workspace ($BuildProfile)..." -ForegroundColor Green
    try {
        $CargoPath = "C:\Users\$env:USERNAME\.cargo\bin\cargo.exe"
        if (-not (Test-Path $CargoPath)) {
            $CargoPath = "cargo"
        }
        
        Push-Location $RootDir
        & $CargoPath build --release
        if ($LASTEXITCODE -ne 0) {
            throw "Cargo build failed with exit code $LASTEXITCODE"
        }
        Write-Host "  Rust build complete." -ForegroundColor Green
        Pop-Location
    }
    catch {
        Write-Host "ERROR: Rust build failed: $_" -ForegroundColor Red
        exit 1
    }
    Write-Host ""
}

# Step 3: Build and install Python package (unless skipped)
if (-not $NoPython) {
    Write-Host "Step 3: Building Python wheel with maturin..." -ForegroundColor Green
    try {
        # Check if maturin is available
        & $VenvPython -m maturin --version 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Installing maturin..." -ForegroundColor Cyan
            & $VenvPython -m pip install "maturin>=1.0" -q
        }
        
        Push-Location (Join-Path $RootDir "vrp-cli")
        $MaturinArgs = @("build", "--release")
        & $VenvPython -m maturin @MaturinArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Maturin build failed with exit code $LASTEXITCODE"
        }
        Write-Host "  Python wheel build complete." -ForegroundColor Green
        Pop-Location
    }
    catch {
        Write-Host "ERROR: Python wheel build failed: $_" -ForegroundColor Red
        exit 1
    }
    Write-Host ""
    
    Write-Host "Step 4: Installing Python wheel..." -ForegroundColor Green
    try {
        $WheelPattern = Join-Path $RootDir "target\wheels\vrp_cli-*.whl"
        $Wheels = @(Get-Item $WheelPattern -ErrorAction SilentlyContinue)
        
        if ($Wheels.Count -eq 0) {
            throw "No .whl file found at $WheelPattern"
        }
        
        $LatestWheel = $Wheels | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        Write-Host "  Installing from: $($LatestWheel.Name)"
        
        & $VenvPython -m pip install $LatestWheel.FullName --force-reinstall -q
        if ($LASTEXITCODE -ne 0) {
            throw "Wheel installation failed with exit code $LASTEXITCODE"
        }
        Write-Host "  Installation complete." -ForegroundColor Green
    }
    catch {
        Write-Host "ERROR: Python wheel installation failed: $_" -ForegroundColor Red
        exit 1
    }
    Write-Host ""
}

# Step 5: Verification
Write-Host "Step 5: Verifying installation..." -ForegroundColor Green
try {
    & $VenvPython -c "import vrp_cli; print(f'vrp_cli module imported successfully'); print([x for x in dir(vrp_cli) if not x.startswith('_')])"
    Write-Host "  Verification successful." -ForegroundColor Green
}
catch {
    Write-Host "WARNING: Verification failed (may be normal if Python-only): $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Build Complete ===" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor Green
Write-Host "  - Test with: python examples\python-interop\run_pragmatic_example.py --list"
Write-Host "  - Run example: python examples\python-interop\run_pragmatic_example.py simple.basic.problem.json"
Write-Host "  - Run all:    python examples\python-interop\run_pragmatic_example.py --all"
