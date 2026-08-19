#!/usr/bin/env bash
# =============================================================================
# Nexus ERP — Pre-deployment validation
# Run this locally before committing or deploying to catch common errors:
#   - Missing env variables
#   - Python syntax errors
#   - XML view files that reference fields not defined in models
#   - Manifest inconsistencies
# =============================================================================

set -uo pipefail

PROJECT_DIR="${PROJECT_DIR:-.}"
ERRORS=0

echo "[validate] Running local pre-deployment checks ..."

# 1. .env.example contains all variables referenced in docker-compose.yml
echo "[validate] Checking docker-compose variable references ..."
missing_vars=$(grep -oE '\$\{[A-Z_]+' "$PROJECT_DIR/docker-compose.yml" | sed 's/\${//' | sort -u | while read -r var; do
    if ! grep -q "^$var=" "$PROJECT_DIR/.env.example"; then
        echo "  MISSING in .env.example: $var"
    fi
done)
if [ -n "$missing_vars" ]; then
    echo "$missing_vars"
    ((ERRORS++))
fi

# 2. Python syntax check across custom_addons
if command -v python3 &>/dev/null; then
    echo "[validate] Checking Python syntax ..."
    find "$PROJECT_DIR/odoo-backend/custom_addons" -name '*.py' -print0 | while IFS= read -r -d '' f; do
        if ! python3 -m py_compile "$f" 2>/dev/null; then
            echo "  SYNTAX ERROR: $f"
            ((ERRORS++))
        fi
    done
else
    echo "[validate] WARNING: python3 not available, skipping Python syntax check"
fi

# 3. XML views: detect fields referenced that might not exist (basic check)
echo "[validate] Checking XML views for obvious missing fields ..."
# This is a shallow heuristic; full validation requires running Odoo.
while IFS= read -r xml; do
    # Very naive check for field name attribute not matching any python field= line
    model=$(grep -oE 'model="[^"]+"' "$xml" | head -1 | cut -d'"' -f2)
    if [ -n "$model" ]; then
        model_file=$(find "$PROJECT_DIR/odoo-backend/custom_addons" -path "*/models/*.py" -print0 | xargs -0 grep -l "_name.*=.*['\"]$model['\"]" 2>/dev/null | head -1)
        if [ -n "$model_file" ]; then
            grep -oE '<field name="[^"]+"' "$xml" | sed 's/<field name="//;s/"$//' | while read -r field; do
                if ! grep -qE "^[[:space:]]*$field[[:space:]]*=" "$model_file"; then
                    echo "  SUSPECT: field '$field' in $xml not found in $model_file"
                fi
            done
        fi
    fi
done < <(find "$PROJECT_DIR/odoo-backend/custom_addons" -name '*.xml')

# 4. Manifest files must list existing data/view files
echo "[validate] Checking manifests reference existing files ..."
while IFS= read -r manifest; do
    dir=$(dirname "$manifest")
    # Extract 'data': [...] and parse quoted paths
    python3 - "$manifest" "$dir" <<'PY' 2>/dev/null || true
import ast, json, os, sys
manifest_path = sys.argv[1]
dir = sys.argv[2]
with open(manifest_path) as f:
    data = ast.literal_eval(f.read())
for key in ('data', 'assets'):
    for path in data.get(key, []):
        if not os.path.exists(os.path.join(dir, path)):
            print(f"  MISSING FILE in {manifest_path}: {path}")
PY
done < <(find "$PROJECT_DIR/odoo-backend/custom_addons" -name '__manifest__.py')

if [ "$ERRORS" -gt 0 ]; then
    echo "[validate] FAILED with $ERRORS error(s)."
    exit 1
fi

echo "[validate] All local checks passed."
