#!/usr/bin/env bash
# =============================================================================
# Nexus ERP — Server hardening script (run on the Ubuntu host)
# Configures UFW so only HTTP/HTTPS/SSH are exposed to the public internet.
# All internal services (Postgres, Redis, Odoo, ERPNext, n8n, AI) are reached
# only through the Docker reverse proxy.
# =============================================================================

set -euo pipefail

echo "[harden] Configuring UFW firewall ..."

# Reset UFW to known state (interactive answers avoided)
sudo ufw --force reset

# Default: deny everything incoming except what we explicitly allow
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH — restrict to your office IP if possible, otherwise keep open
sudo ufw allow 22/tcp comment 'SSH'

# Web — only these two ports should be public
sudo ufw allow 80/tcp comment 'HTTP redirect to HTTPS'
sudo ufw allow 443/tcp comment 'HTTPS'

# Optional: rate-limit SSH brute-force attempts
sudo ufw limit 22/tcp

# Make sure UFW is enabled
sudo ufw --force enable

echo "[harden] UFW status:"
sudo ufw status verbose

echo ""
echo "[harden] IMPORTANT: Direct database ports (5432, 3306, 6379) and"
echo "                     Odoo/ERPNext/n8n ports (8069, 8072, 8080, 5678, 8000)"
echo "                     must NOT appear in the list above."
echo "                     They are still accessible inside the Docker network."
