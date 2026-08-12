#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Installs WSL2 and Docker Desktop, then prepares the local ERP stack.
.DESCRIPTION
    Run this script as Administrator. It installs WSL2 (no distribution),
    then Docker Desktop via winget. A reboot may be required before Docker
    can be used. After the reboot, run `start-erp.ps1`.
#>

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $isAdmin) {
    Write-Host "This script must be run as Administrator." -ForegroundColor Red
    exit 1
}

Write-Host "Installing WSL2..."
$wslCheck = wsl --version 2>&1
if ($LASTEXITCODE -ne 0) {
    wsl --install --no-distribution
} else {
    Write-Host "WSL is already installed."
}

Write-Host "Installing Docker Desktop..."
winget install --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements

Write-Host @"

WSL2 and Docker Desktop installation initiated.
If prompted, restart your computer.
After restart, open Docker Desktop and wait for it to start,
then run: .\scripts\start-erp.ps1
"@
