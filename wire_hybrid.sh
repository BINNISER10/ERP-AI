#!/bin/bash
set -e
cd /opt/nexus-engine

# Copy ERPNext key generator into the backend container
sudo docker compose cp /tmp/generate_erpnext_api_key.py erpnext-backend:/home/frappe/frappe-bench/sites/frontend/generate_erpnext_api_key.py

# Generate ERPNext token for Administrator
KEYS=$(sudo docker compose exec -T -w /home/frappe/frappe-bench/sites erpnext-backend /home/frappe/frappe-bench/env/bin/python frontend/generate_erpnext_api_key.py)

ERPNEXT_API_KEY=$(echo "$KEYS" | grep '^ERPNEXT_API_KEY=' | cut -d= -f2-)
ERPNEXT_API_SECRET=$(echo "$KEYS" | grep '^ERPNEXT_API_SECRET=' | cut -d= -f2-)

if [ -z "$ERPNEXT_API_KEY" ] || [ -z "$ERPNEXT_API_SECRET" ]; then
    echo "ERROR: Could not generate ERPNext API key/secret"
    exit 1
fi

echo "[ERPNext API] Generated Administrator token"

# Create / update the hybrid config record using the odoo shell
cat > /tmp/odoo_hybrid.py <<PYEOF
company = env["res.company"].search([], limit=1)
vals = {
    "company_id": company.id,
    "erpnext_url": "http://erpnext-frontend:8080",
    "erpnext_api_key": "$ERPNEXT_API_KEY",
    "erpnext_api_secret": "$ERPNEXT_API_SECRET",
    "n8n_url": "http://n8n:5678",
}
rec = env["hybrid.config"].search([("company_id", "=", company.id)], limit=1)
if rec:
    rec.write(vals)
    print(f"[HYBRID CONFIG] Updated {rec.name}")
else:
    rec = env["hybrid.config"].create(vals)
    print(f"[HYBRID CONFIG] Created {rec.name}")
env.cr.commit()
exit()
PYEOF

sudo docker compose cp /tmp/odoo_hybrid.py odoo:/tmp/odoo_hybrid.py
sudo docker compose exec -T odoo odoo shell --no-http -c /etc/odoo/odoo.conf -d nexus_erp --db_host db --db_port 5432 --db_user odoo --db_password odoo_secret < /tmp/odoo_hybrid.py
