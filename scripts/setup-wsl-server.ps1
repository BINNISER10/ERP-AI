#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Sets up WSL2 + Ubuntu on Windows Server, then installs Docker and starts the Nexus ERP stack.
.DESCRIPTION
    Docker Desktop is not supported on Windows Server. This script uses WSL2 with an Ubuntu
    distro, installs Docker inside it, copies the repo into the WSL filesystem, and starts
    the stack with docker compose.
    Run as Administrator. A reboot may be required after enabling WSL/VirtualMachinePlatform.
#>

param(
    [string]$DistroName = "Ubuntu-Nexus",
    [string]$UbuntuVersion = "noble"
)

$ErrorActionPreference = "Stop"

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $isAdmin) {
    Write-Host "This script must be run as Administrator." -ForegroundColor Red
    exit 1
}

# Repo is in G:\My Drive\ERP ODOO. In WSL this is /mnt/g/My Drive/ERP ODOO.
# We will copy it into the WSL home to avoid spaces and get native filesystem performance.
$repoWslPath = "/home/nexus/nexus-engine"
$hostRepoInWsl = "/mnt/g/My Drive/ERP ODOO"
$wslUser = "nexus"

$restartRequired = $false

function Enable-FeatureIfNeeded {
    param($FeatureName)
    $feature = Get-WindowsOptionalFeature -Online -FeatureName $FeatureName
    if ($feature.State -ne "Enabled") {
        Write-Host "Enabling $FeatureName..."
        $result = Enable-WindowsOptionalFeature -Online -FeatureName $FeatureName -All -NoRestart
        if ($result.RestartNeeded -eq $true) {
            $script:restartRequired = $true
        }
    } else {
        Write-Host "$FeatureName already enabled."
    }
}

# 1. Enable WSL and VirtualMachinePlatform
Enable-FeatureIfNeeded -FeatureName "Microsoft-Windows-Subsystem-Linux"
Enable-FeatureIfNeeded -FeatureName "VirtualMachinePlatform"

if ($restartRequired) {
    Write-Host ""
    Write-Host "WSL features were enabled but a reboot is required before they are active." -ForegroundColor Yellow
    Write-Host "Please restart the server, then run this script again." -ForegroundColor Yellow
    exit 0
}

# 2. Set WSL default version to 2
Write-Host "Setting WSL default version to 2..."
wsl --set-default-version 2

# 3. Install Ubuntu if not present
$distros = (wsl --list --quiet 2>&1) | ForEach-Object { $_.Trim() }
if ($distros -notcontains $DistroName) {
    Write-Host "Installing Ubuntu WSL distro ($UbuntuVersion)..."
    $tempDir = New-Item -ItemType Directory -Path (Join-Path $env:TEMP "wsl-ubuntu-$UbuntuVersion") -Force
    $rootfs = Join-Path $tempDir "ubuntu-$UbuntuVersion-wsl-amd64-wsl.rootfs.tar.gz"
    $url = "https://cloud-images.ubuntu.com/wsl/$UbuntuVersion/current/ubuntu-$UbuntuVersion-wsl-amd64-wsl.rootfs.tar.gz"

    Write-Host "Downloading Ubuntu rootfs from $url ..."
    Invoke-WebRequest -Uri $url -OutFile $rootfs -UseBasicParsing

    Write-Host "Importing distro..."
    wsl --import $DistroName (Join-Path $tempDir "install") $rootfs --version 2
} else {
    Write-Host "Distro $DistroName already exists."
}

# 4. Configure default user inside WSL
Write-Host "Creating user $wslUser in WSL distro..."
$createUser = 'id -u "$1" >/dev/null 2>&1 || (useradd -m -s /bin/bash "$1" && echo "$1:$1" | chpasswd && usermod -aG sudo "$1")'
wsl -d $DistroName -e bash -c $createUser -- $wslUser

$wslConf = '{ echo "[user]"; echo "default=$1"; } > /etc/wsl.conf'
wsl -d $DistroName -e bash -c $wslConf -- $wslUser
wsl --terminate $DistroName

# 5. Install Docker inside WSL
Write-Host "Installing Docker Engine inside WSL..."
$dockerInstall = 'set -e; apt-get update; apt-get install -y ca-certificates curl gnupg lsb-release; install -m 0755 -d /etc/apt/keyrings; curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg; chmod a+r /etc/apt/keyrings/docker.gpg; echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null; apt-get update; apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; usermod -aG docker "$1" || true; service docker start || true'
wsl -d $DistroName -e bash -c $dockerInstall -- $wslUser

# 6. Copy repo into WSL filesystem
Write-Host "Copying repository into WSL..."
$copyRepo = 'set -e; rm -rf "$2"; mkdir -p "$2"; cp -r "$3/." "$2"; chown -R "$1":"$1" "$2"; rm -rf "$2/.git" "$2/.dart_tool" "$2/build"'
wsl -d $DistroName -e bash -c $copyRepo -- $wslUser $repoWslPath $hostRepoInWsl

# 7. Start stack
Write-Host "Starting ERP stack inside WSL..."
$startStack = 'set -e; if [ ! -f "$1/.env" ]; then cp "$1/.env.example" "$1/.env"; fi; service docker start; cd "$1"; docker compose up -d'
wsl -d $DistroName -u root -e bash -c $startStack -- $repoWslPath

Write-Host ""
Write-Host "ERP stack is starting inside WSL."
Write-Host "Watch logs with:"
Write-Host "  wsl -d $DistroName -u root -e bash -c 'cd $repoWslPath && docker compose logs -f'"
Write-Host ""
Write-Host "Services will be available on:"
Write-Host "  Odoo ERP:     http://localhost:8069"
Write-Host "  AI services:  http://localhost:8000"
