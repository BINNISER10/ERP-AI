#!/usr/bin/env bash
# =============================================================================
# Restore a Nexus ERP database backup created by scripts/backup.sh
# =============================================================================

set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <backup-dir> [--odoo-only|--erpnext-only]"
    exit 1
fi

BACKUP_DIR="$1"
MODE="${2:-all}"

cd /opt/nexus-engine

if [ "$MODE" = "all" ] || [ "$MODE" = "--odoo-only" ]; then
    if [ -f "$BACKUP_DIR/nexus_erp.dump" ]; then
        echo "[restore] Restoring Odoo database..."
        docker exec -i nexus_postgres pg_restore -U odoo -d nexus_erp --clean --if-exists < "$BACKUP_DIR/nexus_erp.dump" || true
        echo "[restore] Odoo database restored."
    else
        echo "[restore] Odoo backup not found, skipping."
    fi
fi

if [ "$MODE" = "all" ] || [ "$MODE" = "--erpnext-only" ]; then
    if [ -f "$BACKUP_DIR/erpnext.sql" ]; then
        echo "[restore] Restoring ERPNext database..."
        docker exec -i nexus_erpnext_db mysql -uroot -p"$(cat secrets/erpnext_admin_password.txt)" _1bd3e0294da19198 < "$BACKUP_DIR/erpnext.sql"
        echo "[restore] ERPNext database restored."
    else
        echo "[restore] ERPNext backup not found, skipping."
    fi
fi
