#!/usr/bin/env pwsh
# Nexus Enterprise Engine — PowerShell setup helper
# Usage: .\setup.ps1 [-SkipFlutter] [-SkipDocker]
param(
    [switch]$SkipFlutter,
    [switch]$SkipDocker
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
if (-not $root) { $root = (Get-Location).Path }

function Test-CommandAvailable {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

Write-Host "== Nexus Enterprise Engine setup ==" -ForegroundColor Cyan
Write-Host "Working directory: $root" -ForegroundColor Gray

# 1. Structural validation
Write-Host "`n[1/4] Running structural validation..." -ForegroundColor Cyan
& python "$root\validate.py" | ForEach-Object { Write-Host $_ }
if ($LASTEXITCODE -ne 0) {
    Write-Host "Validation failed. Please fix the issues above and rerun." -ForegroundColor Red
    exit 1
}
Write-Host "Validation passed." -ForegroundColor Green

# 2. Flutter build_runner (Drift code generation)
if (-not $SkipFlutter) {
    Write-Host "`n[2/4] Preparing Flutter POS..." -ForegroundColor Cyan
    if (Test-CommandAvailable "flutter") {
        $flutterDir = Join-Path $root "flutter_pos"
        Push-Location $flutterDir
        try {
            Write-Host "Running flutter pub get..." -ForegroundColor Gray
            flutter pub get
            if ($LASTEXITCODE -ne 0) { throw "flutter pub get failed" }

            Write-Host "Running build_runner (Drift .g.dart)..." -ForegroundColor Gray
            dart run build_runner build --delete-conflicting-outputs
            if ($LASTEXITCODE -ne 0) { throw "build_runner failed" }
        }
        finally {
            Pop-Location
        }
    }
    else {
        Write-Host "Flutter not found. Skipping POS build. Install Flutter and rerun without -SkipFlutter." -ForegroundColor Yellow
    }
}
else {
    Write-Host "`n[2/4] Skipping Flutter build (requested -SkipFlutter)." -ForegroundColor Yellow
}

# 3. Docker Compose build
if (-not $SkipDocker) {
    Write-Host "`n[3/4] Building Docker images..." -ForegroundColor Cyan
    if (Test-CommandAvailable "docker") {
        & docker compose -f "$root\docker-compose.yml" build
        if ($LASTEXITCODE -ne 0) { throw "docker compose build failed" }
    }
    else {
        Write-Host "Docker not found. Skipping container build. Install Docker and rerun without -SkipDocker." -ForegroundColor Yellow
    }
}
else {
    Write-Host "`n[3/4] Skipping Docker build (requested -SkipDocker)." -ForegroundColor Yellow
}

# 4. Docker Compose start
if (-not $SkipDocker) {
    Write-Host "`n[4/4] Starting services..." -ForegroundColor Cyan
    if (Test-CommandAvailable "docker") {
        & docker compose -f "$root\docker-compose.yml" up -d
        if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }

        Write-Host "`nServices started successfully." -ForegroundColor Green
        Write-Host "  Nexus Core:  http://localhost:8069" -ForegroundColor Gray
        Write-Host "  AI services: http://localhost:8000" -ForegroundColor Gray
        Write-Host "  n8n:         http://localhost:5678" -ForegroundColor Gray
        Write-Host "`nNext steps:" -ForegroundColor Cyan
        Write-Host "  1. Open http://localhost:8069 and create the database." -ForegroundColor Gray
        Write-Host "  2. Activate developer mode in Nexus Core." -ForegroundColor Gray
        Write-Host "  3. Install the Nexus custom modules from Apps." -ForegroundColor Gray
    }
    else {
        Write-Host "Docker not found. Cannot start services." -ForegroundColor Yellow
    }
}
else {
    Write-Host "`n[4/4] Skipping Docker start (requested -SkipDocker)." -ForegroundColor Yellow
}
