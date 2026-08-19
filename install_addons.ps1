#!/usr/bin/env pwsh
# Install all Nexus custom modules into the selected database.
# Usage: .\install_addons.ps1 [-Database "BINNISER"] [-Container "nexus_odoo"]
param(
    [string]$Database = "BINNISER",
    [string]$Container = "nexus_odoo",
    [switch]$Restart
)

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
if (-not $root) { $root = (Get-Location).Path }

function Test-DockerContainerRunning {
    param([string]$Name)
    $state = docker inspect -f "{{.State.Status}}" $Name 2>$null
    return $state -eq "running"
}

$modules = @(
    "nexus_base_security",
    "nexus_pure_branding",
    "odoo_erpnext_hybrid_sync",
    "nexus_universal_mail",
    "ai_enterprise_copilot",
    "nexus_api_gateway",
    "nexus_contracting",
    "nexus_fuel_station",
    "nexus_real_estate",
    "nexus_restaurant_costing",
    "nexus_us_tax_engine",
    "nexus_zatca_compliance",
    "nexus_saudi_localization",
    "nexus_us_localization",
    "nexus_advanced_accounting",
    "nexus_erpnext_accounting"
) -join ","

Write-Host "== Nexus Addons Installer ==" -ForegroundColor Cyan
Write-Host "Database: $Database" -ForegroundColor Gray
Write-Host "Container: $Container" -ForegroundColor Gray

# Verify Docker is available
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker is not available. Please run this on the Docker host." -ForegroundColor Red
    exit 1
}

# Verify container is running
if (-not (Test-DockerContainerRunning $Container)) {
    Write-Host "Container '$Container' is not running. Starting with docker compose..." -ForegroundColor Yellow
    docker compose -f "$root\docker-compose.yml" up -d
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }
    Start-Sleep -Seconds 5
}

# Restart if requested (e.g. to load new code)
if ($Restart) {
    Write-Host "Restarting Nexus Core container..." -ForegroundColor Yellow
    docker restart $Container
    if ($LASTEXITCODE -ne 0) { throw "docker restart failed" }
    Start-Sleep -Seconds 5
}

Write-Host "`nInstalling all Nexus modules into database '$Database'..." -ForegroundColor Cyan
Write-Host "This may take several minutes." -ForegroundColor Yellow

docker exec $Container odoo -i $modules -d $Database --stop-after-init --no-http
if ($LASTEXITCODE -ne 0) { throw "Nexus module installation failed" }

Write-Host "`nAll Nexus modules installed successfully." -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "  - Open http://localhost:8069 and log in to '$Database'" -ForegroundColor Gray
Write-Host "  - Activate developer mode if not already active" -ForegroundColor Gray
Write-Host "  - Confirm apps are installed under Settings -> Apps" -ForegroundColor Gray
