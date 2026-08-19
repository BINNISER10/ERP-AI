#!/usr/bin/env bash
# =============================================================================
# Fresh server deployment playbook (run on a clean Ubuntu 24.04 host)
# Use this when the previous server is unreachable or you want a clean install.
# =============================================================================

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/nexus-engine}"
REPO_URL="${REPO_URL:-}"

echo "[redeploy] Nexus ERP fresh deployment to $PROJECT_DIR"

# 1. Basic dependencies
sudo apt-get update
sudo apt-get install -y git curl ca-certificates gnupg ufw

# 2. Docker (same packages as cloud-init.yml)
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker

# 3. Clone repo
if [ -z "$REPO_URL" ]; then
    echo "[redeploy] ERROR: set REPO_URL, e.g.:"
    echo "  REPO_URL=git@github.com:yourorg/nexus-erp.git ./scripts/redeploy-server.sh"
    exit 1
fi

sudo rm -rf "$PROJECT_DIR"
sudo git clone "$REPO_URL" "$PROJECT_DIR"

# 4. Prepare environment
sudo mkdir -p "$PROJECT_DIR/secrets"
sudo touch "$PROJECT_DIR/.env"
sudo chown -R "$(whoami):" "$PROJECT_DIR"

echo "[redeploy] Project cloned to $PROJECT_DIR"
echo "[redeploy] Next:"
echo "  1. Copy .env and secrets from your local machine or password manager."
echo "  2. Run: cd $PROJECT_DIR && ./scripts/harden-server.sh && ./scripts/deploy.sh"
