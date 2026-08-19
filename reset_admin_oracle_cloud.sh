#!/usr/bin/env bash
# Run this script inside Oracle Cloud Cloud Shell or any SSH session to the Docker host.
# It finds the running Odoo container and sets the admin user password to Admin123!

set -e

DB_NAME="nexus_erp"
NEW_PASS="Admin123!"

# Find the Odoo container (by image name or common naming).
CONTAINER=$(docker ps --filter "ancestor=odoo:18.0" --format "{{.Names}}" | head -n 1)
if [ -z "$CONTAINER" ]; then
    CONTAINER=$(docker ps --filter "name=odoo" --format "{{.Names}}" | head -n 1)
fi
if [ -z "$CONTAINER" ]; then
    echo "ERROR: Could not find an Odoo container."
    docker ps
    exit 1
fi

echo "Found Odoo container: $CONTAINER"

# Create a Python reset script inside the container and execute it.
docker exec -i "$CONTAINER" /bin/bash -c "cat > /tmp/reset_admin.py" <<'PY'
import os
import odoo
from odoo import SUPERUSER_ID
from odoo.tools import config
from odoo.sql_db import db_connect

config['db_name'] = os.environ.get('DB_NAME', 'nexus_erp')
config['db_user'] = os.environ.get('USER', 'odoo')
config['db_password'] = os.environ.get('PASSWORD', '')
config['db_host'] = os.environ.get('HOST', 'db')
config['db_port'] = int(os.environ.get('PORT', 5432))

odoo.service.server.load_server_wide_modules()
cr = db_connect(config['db_name']).cursor()
try:
    env = odoo.api.Environment(cr, SUPERUSER_ID, {})
    user = env['res.users'].search([('login', '=', 'admin')], limit=1)
    if user:
        user.write({'password': os.environ.get('NEW_PASS', 'Admin123!')})
        env.cr.commit()
        print('Admin password updated to:', os.environ.get('NEW_PASS', 'Admin123!'))
    else:
        print('admin user not found.')
finally:
    cr.close()
PY

docker exec -e DB_NAME="$DB_NAME" -e NEW_PASS="$NEW_PASS" "$CONTAINER" python /tmp/reset_admin.py
docker exec "$CONTAINER" rm -f /tmp/reset_admin.py

echo "Done. Login with: admin / $NEW_PASS"
