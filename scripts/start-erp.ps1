<#
.SYNOPSIS
    Starts the local Nexus ERP stack using Docker Compose.
.DESCRIPTION
    Requires Docker Desktop (or Docker Engine) and WSL2 to be installed and running.
    Copies .env.example to .env if .env is missing, then runs docker compose up -d.
#>

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$envFile = Join-Path $repoRoot ".env"
$exampleFile = Join-Path $repoRoot ".env.example"

if (-not (Test-Path $envFile) -and (Test-Path $exampleFile)) {
    Write-Host "Creating .env from .env.example ..."
    Copy-Item $exampleFile $envFile
}

Write-Host "Starting Docker Compose stack..."
docker compose up -d

Write-Host @"

Stack starting. Watch logs with:
  docker compose logs -f

Services:
  Odoo ERP:     http://localhost:8069
  AI services:  http://localhost:8000
  Postgres:     localhost:5432
  Redis:        localhost:6379
"@
