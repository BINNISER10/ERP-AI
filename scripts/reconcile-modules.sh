#!/usr/bin/env bash
# =============================================================================
# Nexus ERP — Module reconciliation helper
# Compares modules in local repo vs modules on an existing deployed server
# so divergent production modules can be merged into the single Git repo.
# =============================================================================

set -euo pipefail

LOCAL_DIR="${LOCAL_DIR:-.}"
REMOTE_DIR="${REMOTE_DIR:-}"

if [ -z "$REMOTE_DIR" ]; then
    echo "Usage: REMOTE_DIR=/path/to/server/custom_addons ./scripts/reconcile-modules.sh"
    echo "Or use via SSH: ssh user@host 'find /opt/nexus-engine/odoo-backend/custom_addons -mindepth 1 -maxdepth 1 -type d -printf \"%f\\n\"' > /tmp/remote-modules.txt"
    exit 1
fi

LOCAL_MODS="$(cd "$LOCAL_DIR/odoo-backend/custom_addons" && find . -mindepth 1 -maxdepth 1 -type d | sed 's|^./||' | sort)"
REMOTE_MODS="$(cd "$REMOTE_DIR" && find . -mindepth 1 -maxdepth 1 -type d | sed 's|^./||' | sort)"

echo "=== Modules only in LOCAL repo ==="
comm -23 <(echo "$LOCAL_MODS") <(echo "$REMOTE_MODS")

echo ""
echo "=== Modules only on REMOTE server ==="
comm -13 <(echo "$LOCAL_MODS") <(echo "$REMOTE_MODS")

echo ""
echo "=== Modules present in BOTH ==="
comm -12 <(echo "$LOCAL_MODS") <(echo "$REMOTE_MODS")

echo ""
echo "[reconcile] Next steps:"
echo "  1. Review 'only on REMOTE server' modules — copy them into the local repo."
echo "  2. Review 'only in LOCAL repo' modules — keep if they replace remote ones."
echo "  3. Commit the merged set and deploy via GitOps."
