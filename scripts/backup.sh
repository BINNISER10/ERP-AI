#!/usr/bin/env bash
# =============================================================================
# Nexus ERP — Backup script (run on the server)
# Backs up Odoo, ERPNext databases and essential configuration files.
# =============================================================================

set -euo pipefail

BACKUP_DIR="/opt/nexus-backups/$(date +%Y-%m-%d_%H-%M-%S)"
PROJECT_DIR="${PROJECT_DIR:-/opt/nexus-engine}"
mkdir -p "$BACKUP_DIR"

cd "$PROJECT_DIR"

echo "[backup] Starting backup to $BACKUP_DIR ..."

# Odoo PostgreSQL backup
if docker ps --format '{{.Names}}' | grep -q '^nexus_postgres$'; then
    echo "[backup] Backing up Odoo database (nexus_erp) ..."
    docker exec nexus_postgres pg_dump -U odoo -d nexus_erp -Fc > "$BACKUP_DIR/nexus_erp.dump"
else
    echo "[backup] WARNING: nexus_postgres container not running"
fi

# ERPNext MariaDB backup
if docker ps --format '{{.Names}}' | grep -q '^nexus_erpnext_db$'; then
    echo "[backup] Backing up ERPNext database (_1bd3e0294da19198) ..."
    docker exec nexus_erpnext_db mysqldump -uroot -p"$(cat "$PROJECT_DIR/secrets/erpnext_admin_password.txt" 2>/dev/null || echo '')" --single-transaction _1bd3e0294da19198 2>/dev/null > "$BACKUP_DIR/erpnext.sql" || echo "[backup] WARNING: ERPNext backup failed (password missing or wrong DB name)"
fi

# Configuration backup
echo "[backup] Backing up configuration files ..."
cp -r "$PROJECT_DIR/config" "$BACKUP_DIR/config" 2>/dev/null || true
cp "$PROJECT_DIR/docker-compose.yml" "$BACKUP_DIR/docker-compose.yml" 2>/dev/null || true
cp "$PROJECT_DIR/.env" "$BACKUP_DIR/.env" 2>/dev/null || true

# Custom addons snapshot (not the whole repo — git handles that)
echo "[backup] Backing up custom addons list ..."
ls -la "$PROJECT_DIR/odoo-backend/custom_addons" > "$BACKUP_DIR/custom_addons.txt" 2>/dev/null || true

# Cleanup old backups (keep last 14 days)
find /opt/nexus-backups -maxdepth 1 -type d -mtime +14 -exec rm -rf {} \; 2>/dev/null || true

echo "[backup] Backup complete: $BACKUP_DIR"
