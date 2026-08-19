# Recreates the Nexus ERP server from Terraform when the old one is lost.
# Run this on the local Windows machine in the project root.

param(
    [Parameter(Mandatory=$false)]
    [string]$TfDir = "terraform"
)

$ErrorActionPreference = "Stop"

Set-Location $TfDir

Write-Host "[recreate] Current Terraform state:"
terraform state list

Write-Host ""
Write-Host "[recreate] Tainting the instance so Terraform will recreate it on next apply..."
terraform taint oci_core_instance.nexus_erp

Write-Host ""
Write-Host "[recreate] Planning changes (review carefully)..."
terraform plan -out=tfplan

Write-Host ""
$confirm = Read-Host "Type YES to destroy and recreate the server (data will be lost unless you have backups)"
if ($confirm -ne "YES") {
    Write-Host "Aborted."
    exit 0
}

Write-Host ""
Write-Host "[recreate] Applying..."
terraform apply tfplan

Write-Host ""
Write-Host "[recreate] New server IP:"
terraform output -raw nexus_server_public_ip
