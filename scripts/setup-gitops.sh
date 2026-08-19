#!/usr/bin/env bash
# =============================================================================
# Nexus ERP — One-time GitOps setup on the production server
# Run this once after the repo is pushed to GitHub/GitLab/Bitbucket.
# =============================================================================

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/nexus-engine}"
REPO_URL="${REPO_URL:-}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"

if [ -z "$REPO_URL" ]; then
    echo "[setup-gitops] ERROR: Set REPO_URL to your git remote, e.g.:"
    echo "  REPO_URL=git@github.com:yourorg/nexus-erp.git ./scripts/setup-gitops.sh"
    exit 1
fi

# 1. Install git if missing
if ! command -v git &>/dev/null; then
    sudo apt-get update
    sudo apt-get install -y git
fi

# 2. Back up current deployment directory if it exists (no git history)
if [ -d "$PROJECT_DIR" ] && [ ! -d "$PROJECT_DIR/.git" ]; then
    BACKUP_DIR="/opt/nexus-backups/manual-$(date +%Y%m%d-%H%M%S)"
    echo "[setup-gitops] Existing deployment found without git. Backing up to $BACKUP_DIR ..."
    sudo cp -a "$PROJECT_DIR" "$BACKUP_DIR"
fi

# 3. Clone repo into project dir
sudo rm -rf "$PROJECT_DIR"
sudo mkdir -p "$PROJECT_DIR"
sudo git clone --branch "$DEPLOY_BRANCH" "$REPO_URL" "$PROJECT_DIR"

# 4. Permissions — deploy is run by ubuntu user, docker group
sudo chown -R "$(whoami):" "$PROJECT_DIR"

# 5. Create required directories/files
mkdir -p "$PROJECT_DIR/secrets"
touch "$PROJECT_DIR/.env"

echo "[setup-gitops] GitOps checkout complete at $PROJECT_DIR"
echo "[setup-gitops] Next steps:"
echo "  1. scp .env and secrets/* from your local machine to $PROJECT_DIR/"
echo "  2. Run: cd $PROJECT_DIR && ./scripts/harden-server.sh"
echo "  3. Run: ./scripts/deploy.sh"
echo ""
echo "[setup-gitops] Optional: add a cron job or webhook to auto-run deploy.sh on push."
