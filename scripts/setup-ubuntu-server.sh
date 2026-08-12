#!/bin/bash
set -e

# One-command setup for an Ubuntu server (cloud or on-prem).
# Run as root on a fresh Ubuntu 22.04/24.04 LTS machine.
# This installs Docker, Docker Compose, then starts the Nexus ERP stack.

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (or with sudo)"
    exit 1
fi

REPO_DIR="/opt/nexus-engine"

# 1. Install Docker Engine and Compose plugin
apt-get update
apt-get install -y ca-certificates curl gnupg lsb-release
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 2. Ensure repo is on the server
if [ ! -d "$REPO_DIR" ]; then
    echo "Repository not found at $REPO_DIR."
    echo "Please copy the project to $REPO_DIR (or clone from GitHub) and re-run."
    exit 1
fi

cd "$REPO_DIR"

# 3. Prepare environment file
if [ ! -f .env ]; then
    cp .env.example .env
fi

# 4. Start the stack
systemctl start docker || true
docker compose up -d

echo ""
echo "ERP stack is starting."
echo "Check logs with: docker compose logs -f"
echo ""
echo "Services:"
echo "  Odoo ERP:    http://$(hostname -I | awk '{print $1}'):8069"
echo "  AI services: http://$(hostname -I | awk '{print $1}'):8000"
