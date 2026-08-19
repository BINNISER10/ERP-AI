#!/usr/bin/env pwsh
# Reset the 'admin' user password in the Nexus Odoo database.
# Usage: .\reset_admin_password.ps1 [-Container "nexus_odoo"] [-Database "nexus_erp"]
param(
    [string]$Container = "nexus_odoo",
    [string]$Database = "nexus_erp"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker is not available on this machine." -ForegroundColor Red
    Write-Host "Please run this script on the Docker host, or use the database manager:" -ForegroundColor Yellow
    Write-Host "  http://148.116.78.77:8069/web/database/manager" -ForegroundColor Gray
    exit 1
}

$NewPass = Read-Host "Enter the new admin password" -AsSecureString
$NewPassPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($NewPass)
)

if ([string]::IsNullOrWhiteSpace($NewPassPlain)) {
    Write-Host "Password cannot be empty." -ForegroundColor Red
    exit 1
}

Write-Host "Resetting admin password in database '$Database'..." -ForegroundColor Cyan

$pyScript = @"
import os
import odoo
from odoo import SUPERUSER_ID
from odoo.tools import config
from odoo.sql_db import db_connect

config['db_name'] = '$Database'
config['db_user'] = os.environ.get('USER', 'odoo')
config['db_password'] = os.environ.get('PASSWORD', '')
config['db_host'] = os.environ.get('HOST', 'db')
config['db_port'] = int(os.environ.get('PORT', 5432))

odoo.service.server.load_server_wide_modules()
cr = db_connect('$Database').cursor()
try:
    env = odoo.api.Environment(cr, SUPERUSER_ID, {})
    user = env['res.users'].search([('login', '=', 'admin')], limit=1)
    if user:
        user.write({'password': '$NewPassPlain'})
        cr.commit()
        print('Admin password updated successfully.')
    else:
        print('admin user not found in database.')
finally:
    cr.close()
"@

$pyScript | docker exec -i $Container /bin/bash -c "cat > /tmp/reset_admin.py && python /tmp/reset_admin.py && rm /tmp/reset_admin.py"

if ($LASTEXITCODE -ne 0) {
    throw "Password reset failed. Check the container is running and the database exists."
}

Write-Host "Done. You can now log in at http://148.116.78.77:8069/web/login with admin / $NewPassPlain" -ForegroundColor Green
