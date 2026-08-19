# Extracts the current public IP of the Nexus ERP server from Terraform state.
# Run this on the local Windows machine in the project root.

$statePath = "terraform/terraform.tfstate"
if (-not (Test-Path $statePath)) {
    Write-Error "Terraform state file not found: $statePath"
    exit 1
}

$state = Get-Content $statePath -Raw | ConvertFrom-Json
$ip = $state.outputs.nexus_server_public_ip.value
if (-not $ip) {
    Write-Error "Could not find nexus_server_public_ip in Terraform outputs."
    exit 1
}

Write-Host "Current server public IP: $ip"
$ip | Set-Clipboard
Write-Host "IP copied to clipboard."
