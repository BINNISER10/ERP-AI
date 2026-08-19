#!/usr/bin/env bash
# =============================================================================
# Nexus Production Deployment Script
#
# Brings up the entire stack on a fresh Ubuntu server:
#   - Generates Docker secrets (random passwords)
#   - Installs Docker + Docker Compose
#   - Configures Let's Encrypt via Certbot
#   - Brings up all services
#
# Usage:
#   sudo ODOO_DOMAIN=erp.example.com ./deploy.sh
# =============================================================================

set -euo pipefail

ODOO_DOMAIN="${ODOO_DOMAIN:-erp.example.com}"
ACME_EMAIL="${ACME_EMAIL:-admin@${ODOO_DOMAIN}}"
SECRETS_DIR="${SECRETS_DIR:-./secrets}"

# Pretty logging
log() { printf '\033[1;32m[DEPLOY]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[WARN]\033[0m %s\n' "$*" >&2; }
err() { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; }

trap 'err "Deployment failed at line $LINENO"' ERR

# ─────────────────────────────────────────────────────────────────────────────
# 1. Pre-flight checks
# ─────────────────────────────────────────────────────────────────────────────
log "Step 1/8 — pre-flight checks"

if [[ $EUID -ne 0 ]]; then
    err "Please run as root (sudo ./deploy.sh)"
    exit 1
fi

if ! command -v docker &>/dev/null; then
    warn "Docker not installed — installing"
    curl -fsSL https://get.docker.com | bash
    systemctl enable docker
    systemctl start docker
fi

if ! docker compose version &>/dev/null; then
    err "Docker Compose plugin not installed"
    apt-get update && apt-get install -y docker-compose-plugin
fi

log "Docker $(docker --version) ready"

# ─────────────────────────────────────────────────────────────────────────────
# 2. DNS check
# ─────────────────────────────────────────────────────────────────────────────
log "Step 2/8 — DNS resolution for ${ODOO_DOMAIN}"
RESOLVED_IP=$(dig +short "$ODOO_DOMAIN" | head -1 || true)
PUBLIC_IP=$(curl -fs https://ifconfig.me || echo "unknown")
if [[ "$RESOLVED_IP" != "$PUBLIC_IP" && -n "$RESOLVED_IP" ]]; then
    warn "Domain ${ODOO_DOMAIN} resolves to ${RESOLVED_IP}, server IP is ${PUBLIC_IP}"
    warn "Update your DNS A record before continuing"
    if [[ "${SKIP_DNS_CHECK:-}" != "1" ]]; then
        read -rp "Continue anyway? [y/N] " ans
        [[ "$ans" =~ ^[Yy]$ ]] || exit 1
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# 3. Generate secrets
# ─────────────────────────────────────────────────────────────────────────────
log "Step 3/8 — generating Docker secrets"
mkdir -p "$SECRETS_DIR"

gen_secret() {
    local name="$1"
    local file="$SECRETS_DIR/${name}.txt"
    if [[ ! -f "$file" ]]; then
        head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 32 > "$file"
        log "  created $file"
    else
        log "  reused $file"
    fi
}

gen_secret postgres_db
gen_secret postgres_user
gen_secret postgres_password
gen_secret odoo_admin_password
gen_secret ai_services_api_key
gen_secret erpnext_admin_password

# Set restrictive permissions
chmod 600 "$SECRETS_DIR"/*.txt

# ─────────────────────────────────────────────────────────────────────────────
# 4. Configure environment
# ─────────────────────────────────────────────────────────────────────────────
log "Step 4/8 — writing .env file"
cat > .env <<EOF
ODOO_DOMAIN=${ODOO_DOMAIN}
ODOO_WEBSITE_NAME=${ODOO_DOMAIN}
ACME_EMAIL=${ACME_EMAIL}
EOF
log "  .env written"

# ─────────────────────────────────────────────────────────────────────────────
# 5. Create Let's Encrypt directory structure
# ─────────────────────────────────────────────────────────────────────────────
log "Step 5/8 — preparing certbot directories"
mkdir -p ./certbot/conf ./certbot/www

# ─────────────────────────────────────────────────────────────────────────────
# 6. Bring up the stack (without SSL first to get the cert)
# ─────────────────────────────────────────────────────────────────────────────
log "Step 6/8 — starting stack (HTTP-only initially)"
docker compose -f docker-compose.prod.yml up -d db redis odoo ai_services

# Wait for Odoo to be ready
log "Waiting for Odoo to become ready..."
for i in $(seq 1 30); do
    if docker compose -f docker-compose.prod.yml exec -T odoo curl -fs http://localhost:8069/web/health >/dev/null 2>&1; then
        log "  Odoo is ready (after ${i} attempts)"
        break
    fi
    sleep 5
done

# ─────────────────────────────────────────────────────────────────────────────
# 7. Obtain Let's Encrypt certificate
# ─────────────────────────────────────────────────────────────────────────────
log "Step 7/8 — requesting Let's Encrypt certificate"
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
    --webroot --webroot-path /var/www/certbot \
    --email "${ACME_EMAIL}" --agree-tos --no-eff-email \
    -d "${ODOO_DOMAIN}"

# ─────────────────────────────────────────────────────────────────────────────
# 8. Start nginx with HTTPS
# ─────────────────────────────────────────────────────────────────────────────
log "Step 8/8 — starting nginx with HTTPS"
docker compose -f docker-compose.prod.yml up -d nginx

sleep 3

# ─────────────────────────────────────────────────────────────────────────────
# Final verification
# ─────────────────────────────────────────────────────────────────────────────
log "Final verification"
if curl -fsI "https://${ODOO_DOMAIN}/web/health" >/dev/null 2>&1; then
    log "✅ HTTPS health check PASSED"
else
    warn "HTTPS health check FAILED — check 'docker compose logs nginx'"
fi

cat <<EOF

═══════════════════════════════════════════════════════════════════════
  🎉  Nexus ERP deployment complete!
═══════════════════════════════════════════════════════════════════════

  🌐  Public URL:   https://${ODOO_DOMAIN}
  🔐  Admin user:   admin
  🔑  Admin pass:   $(cat "${SECRETS_DIR}/odoo_admin_password.txt")

  📦  Services running:
    $(docker compose -f docker-compose.prod.yml ps --services | wc -l) containers
    Odoo 18, AI services, ERPNext, PostgreSQL, Redis, Nginx, Certbot

  �  Next steps:
    1. Visit https://${ODOO_DOMAIN}
    2. Log in with admin / password above
    3. Change the admin password
    4. Run "Setup Journey" to configure your company

  🔒  Security reminders:
    • Save your secrets in a password manager
    • Configure backups for /var/lib/docker/volumes
    • Enable 2FA on your DNS registrar

═══════════════════════════════════════════════════════════════════════
EOF
