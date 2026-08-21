# =============================================================================
# Nexus ERP — Auto-setup Docker locally on Windows
# This script enables WSL, installs Ubuntu, installs Docker, and runs the system
# Run as Administrator
# =============================================================================

$ErrorActionPreference = "Stop"

Write-Host "[SETUP] Nexus ERP Local Docker Setup" -ForegroundColor Cyan
Write-Host ""

# 1. Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] This script must be run as Administrator." -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# 2. Enable WSL features
Write-Host "[SETUP] Enabling WSL features..." -ForegroundColor Yellow
try {
    dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart | Out-Null
    dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart | Out-Null
    Write-Host "[OK] WSL features enabled" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to enable WSL features: $_" -ForegroundColor Red
    exit 1
}

# 3. Check if WSL is already installed
$wslInstalled = Get-Command wsl -ErrorAction SilentlyContinue
if (-not $wslInstalled) {
    Write-Host "[SETUP] WSL not found. Please restart your computer and run this script again." -ForegroundColor Yellow
    Write-Host "After restart, WSL will be available." -ForegroundColor Yellow
    exit 0
}

# 4. Update WSL
Write-Host "[SETUP] Updating WSL..." -ForegroundColor Yellow
wsl --update 2>$null
Write-Host "[OK] WSL updated" -ForegroundColor Green

# 5. Install Ubuntu if not already installed
$ubuntuInstalled = wsl -l -q | Select-String "Ubuntu"
if (-not $ubuntuInstalled) {
    Write-Host "[SETUP] Installing Ubuntu..." -ForegroundColor Yellow
    wsl --install -d Ubuntu
    Write-Host "[SETUP] Ubuntu installed. Please complete the Ubuntu setup (create username/password)." -ForegroundColor Yellow
    Write-Host "After completing Ubuntu setup, run this script again." -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "[OK] Ubuntu already installed" -ForegroundColor Green
}

# 6. Install Docker inside WSL2
Write-Host "[SETUP] Installing Docker inside WSL2..." -ForegroundColor Yellow
$dockerInstallScript = @'
#!/bin/bash
set -e

# Remove old Docker packages
sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

# Update apt
sudo apt-get update

# Install dependencies
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Add Docker GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add current user to docker group
sudo usermod -aG docker $USER

echo "Docker installed successfully"
'@

$dockerInstallScript | wsl bash -e
Write-Host "[OK] Docker installed in WSL2" -ForegroundColor Green

# 7. Copy project to WSL
Write-Host "[SETUP] Copying project to WSL..." -ForegroundColor Yellow
$projectDir = Split-Path -Parent $PSScriptRoot
$wslProjectDir = "/mnt/c/$(($projectDir -replace '\\', '/').Replace('C:/', ''))"
Write-Host "[OK] Project available at: $wslProjectDir" -ForegroundColor Green

# 8. Create .env file if not exists
$envFile = Join-Path $projectDir ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "[SETUP] Creating .env file from .env.example..." -ForegroundColor Yellow
    Copy-Item (Join-Path $projectDir ".env.example") $envFile
    Write-Host "[OK] .env file created. Please edit it with your values." -ForegroundColor Green
} else {
    Write-Host "[OK] .env file already exists" -ForegroundColor Green
}

# 9. Instructions to run
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To run the system:" -ForegroundColor Yellow
Write-Host "1. Open WSL Ubuntu" -ForegroundColor White
Write-Host "2. cd $wslProjectDir" -ForegroundColor White
Write-Host "3. docker compose up -d" -ForegroundColor White
Write-Host ""
Write-Host "Access the system at:" -ForegroundColor Yellow
Write-Host "- Odoo: http://localhost:8069" -ForegroundColor White
Write-Host "- AI Services: http://localhost:8000" -ForegroundColor White
Write-Host "- n8n: http://localhost:5678" -ForegroundColor White
Write-Host "- ERPNext: http://localhost:8080" -ForegroundColor White
Write-Host ""
