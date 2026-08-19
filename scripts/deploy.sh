#!/usr/bin/env bash
# =============================================================================
# Nexus ERP — GitOps deployment script (run on the server)
# Pulls the latest code, backs up, and restarts services.
# =============================================================================

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/nexus-engine}"
GIT_REMOTE="${GIT_REMOTE:-origin}"
GIT_BRANCH="${GIT_BRANCH:-main}"

cd "$PROJECT_DIR"

echo "[deploy] Starting deployment from $GIT_REMOTE/$GIT_BRANCH ..."

# 1. Backup before any change
if [ -x "./scripts/backup.sh" ]; then
    ./scripts/backup.sh
else
    echo "[deploy] WARNING: backup.sh not found or not executable"
fi

# 2. Fetch latest code
echo "[deploy] Pulling latest code ..."
git fetch "$GIT_REMOTE"
git reset --hard "$GIT_REMOTE/$GIT_BRANCH"

# 3. Ensure .env exists and has required variables
if [ ! -f ".env" ]; then
    echo "[deploy] ERROR: .env file missing. Copy .env.example and fill in real values."
    exit 1
fi

# 4. Validate docker compose syntax
echo "[deploy] Validating docker compose configuration ..."
docker compose config >/dev/null

# 5. Build/pull images
echo "[deploy] Pulling/building images ..."
docker compose pull
docker compose build

# 6. Stop and restart services
echo "[deploy] Restarting services ..."
docker compose down --remove-orphans
docker compose up -d

# 7. Health check
echo "[deploy] Waiting for Odoo to become healthy ..."
for i in {1..30}; do
    if curl -fs "http://localhost:8069/web/health" >/dev/null 2>&1; then
        echo "[deploy] Odoo is healthy"
        break
    fi
    sleep 5
done

# 8. Upgrade custom addons (optional, if modules changed)
# Uncomment and adjust the module list when needed:
# docker exec nexus_odoo odoo -u nexus_saudi_localization,nexus_us_localization,ai_enterprise_copilot -d nexus_erp --stop-after-init

echo "[deploy] Deployment complete."
