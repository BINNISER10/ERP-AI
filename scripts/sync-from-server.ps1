# Fetches the remote custom_addons and config from the live server so divergent
# modules can be reconciled before GitOps deployment.
# Run this on the local Windows machine in the project root.

param(
    [Parameter(Mandatory=$true)]
    [string]$ServerIp,

    [string]$SshKey = "terraform/oci_ssh_key.pem",
    [string]$RemoteDir = "/opt/nexus-engine",
    [string]$LocalBackupDir = "server-snapshot-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
)

$ErrorActionPreference = "Stop"

Write-Host "Creating local snapshot directory: $LocalBackupDir"
New-Item -ItemType Directory -Force -Path $LocalBackupDir | Out-Null

$remoteAddons = "ubuntu@${ServerIp}:${RemoteDir}/odoo-backend/custom_addons"
$remoteConfig = "ubuntu@${ServerIp}:${RemoteDir}/config"
$remoteCompose = "ubuntu@${ServerIp}:${RemoteDir}/docker-compose.yml"

Write-Host "Downloading remote custom_addons..."
scp -i $SshKey -r $remoteAddons "$LocalBackupDir/"

Write-Host "Downloading remote config..."
scp -i $SshKey -r $remoteConfig "$LocalBackupDir/"

Write-Host "Downloading remote docker-compose.yml..."
scp -i $SshKey $remoteCompose "$LocalBackupDir/"

Write-Host "Snapshot saved to $LocalBackupDir"
Write-Host "Next: compare modules with scripts/reconcile-modules.sh, then merge missing modules into the local repo."
