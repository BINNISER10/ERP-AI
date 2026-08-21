# Nexus SaaS DB Provisioner

Privileged, standalone worker that physically creates/drops Postgres
databases for `nexus_saas_tenant` tenants running in **`dedicated_db`**
isolation mode. It must run **outside** the Odoo web worker process —
Odoo application code deliberately never holds `CREATEDB`/superuser
Postgres credentials.

```
[Odoo control plane]  <--HTTP poll/callback-->  [this provisioner]  --SQL/subprocess-->  [Postgres + odoo-bin]
```

## Why a separate service?

`nexus_saas_tenant` supports two isolation modes:

- **`shared`** (default) — tenant's companies/users live in the same
  database as everyone else. Matches Ocean Seven's single-cluster,
  multi-company setup. No extra infrastructure needed.
- **`dedicated_db`** — a fully separate, physically isolated Odoo
  database is provisioned for the tenant. This is for enterprise
  clients needing hard isolation, per-tenant backup/restore, or that
  outgrow the shared cluster.

Creating a Postgres database requires OS/DB-admin privileges. Giving
those privileges to the Odoo app server itself would be a serious
security regression, so instead:

1. `nexus_saas_tenant.provision_tenant(..., isolation_mode="dedicated_db")`
   creates a lightweight control-plane `nexus.saas.tenant` record
   (state=`provisioning`) and enqueues a
   `nexus.saas.db.provision.request`.
2. This service polls `GET /saas/db-provisioner/pending` for jobs,
   authenticated with a shared secret (Settings > SaaS > "DB Provisioner
   API Key").
3. It runs `CREATE DATABASE`, then `odoo-bin -d <db> -i <modules>
   --stop-after-init`, then sets the tenant's real admin credentials via
   XML-RPC.
4. It reports success/failure to `POST /saas/db-provisioner/callback`,
   which flips the tenant to `active` (or leaves it in `provisioning`
   with an error logged in its chatter for a manual retry).

Any failure mid-provisioning triggers best-effort rollback (drop the
half-created database) so a retry starts clean.

## Routing: how does `tenant.subdomain.nexus-engine.app` find the right DB?

No custom router needed — Odoo has this built in. In `odoo.conf` on the
shared web-facing Odoo instance:

```ini
[options]
dbfilter = ^%d$
list_db = False
```

`%d` is replaced by the **first subdomain component** of the incoming
request's Host header. Since `nexus.saas.tenant.code` *is* the
subdomain (enforced by the model's regex constraint) and
`dedicated_db_name` is set to that same code, a request to
`acme.nexus-engine.app` is automatically routed by Odoo itself to the
`acme` database — zero application code required. `shared`-mode tenants
simply aren't matched by this filter differently; they all resolve to
the one shared database configured as the default/only match, since
their subdomain routes through the control-plane app instead (handled
by the existing `nexus_saas_tenant` self-service signup + Cloudflare
DNS flow, unchanged).

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config.example.yaml config.yaml
```

Edit `config.yaml`:
- `odoo.base_url` / `odoo.api_key` — matches Settings > SaaS in Odoo.
- `postgres.*` — a role with `CREATEDB` privilege. **Never** reuse the
  regular Odoo application DB role for this.
- `odoo_bin.path` / `addons_path` — same host/cluster as this service.

## Running

```bash
python run.py --config config.yaml
```

Run as a systemd unit / Windows service for production. Unlike
`forecourt-bridge`, this process only needs to run on **one** node
(the one with Postgres admin + odoo-bin access) — it's not tied to any
physical site.

## Admin bootstrap caveat

`bootstrap_admin()` assumes the freshly-installed database has the
default `admin`/`admin` login created by `-i base --without-demo=all`
(standard Odoo behavior). If your base install customizes this (e.g. a
custom `_post_init_hook` in one of the modules in
`odoo_bin.extra_args`'s module list), update
`provisioner/db_ops.py::bootstrap_admin` accordingly.

## Testing

```bash
python -m pytest tests/
```

Unit tests mock out Postgres/odoo-bin/XML-RPC and verify the job
dispatch + rollback-on-failure logic. **They do not exercise a real
database creation** — that requires live Postgres + an `odoo-bin`
install and should be validated manually once per environment:

```bash
# 1. Point config.yaml at a disposable Postgres + Odoo checkout.
# 2. In Odoo: create a plan with allows_dedicated_db=True, then:
python3 -c "
import xmlrpc.client
# ... call nexus.saas.tenant.provision_tenant(..., isolation_mode='dedicated_db')
"
# 3. Run this service and confirm the tenant flips to 'active' and
#    the new database is reachable.
```
