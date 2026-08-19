# Nexus ERP — Deployment & GitOps Guide

## 0. Before you start

On your local Windows machine, find the current server IP:

```powershell
.\scripts\get-server-ip.ps1
```

If the IP is different from `148.116.78.77`, update all commands below.

## 1. Server access

### If SSH works
Run on the production server as `ubuntu`:

```bash
export REPO_URL=git@github.com:YOUR_ORG/nexus-erp.git
export PROJECT_DIR=/opt/nexus-engine

curl -fsSL https://raw.githubusercontent.com/YOUR_ORG/nexus-erp/main/scripts/setup-gitops.sh | bash
```

Then copy secrets and deploy:

```bash
scp .env ubuntu@YOUR_SERVER:/opt/nexus-engine/

ssh ubuntu@YOUR_SERVER '
  cd /opt/nexus-engine
  ./scripts/harden-server.sh
  ./scripts/deploy.sh
'
```

### If SSH is unreachable / IP changed
1. Get the new IP from Oracle Cloud Console.
2. If the old server is still up but SSH is down, use the OCI serial console to diagnose.
3. If the server is lost, provision a new one and run:

```bash
export REPO_URL=git@github.com:YOUR_ORG/nexus-erp.git
./scripts/redeploy-server.sh
```

## 2. Reconcile divergent code (IMPORTANT)

The live server currently runs modules that are **not** in this repo. Before GitOps can take over:

```powershell
# On Windows, in project root
.\scripts\sync-from-server.ps1 -ServerIp YOUR_SERVER_IP
```

Then compare and merge missing modules:

```bash
bash scripts/reconcile-modules.sh REMOTE_DIR=server-snapshot-*/custom_addons
```

Commit the merged set before the first `deploy.sh` run.

## 3. HTTPS modes

### Dev / test (no domain)
The default `docker-compose.yml` + `config/nginx.dev.conf` generate a self-signed certificate automatically and serve HTTPS on port 443. The browser will warn about an untrusted certificate — accept it for testing.

### Production (you have a domain)
1. Set in `.env`:
   ```
   ODOO_DOMAIN=erp.example.com
   ACME_EMAIL=admin@example.com
   ```
2. Switch `nginx` service volume from `config/nginx.dev.conf` to `config/nginx.conf`.
3. Start Certbot to obtain the certificate:
   ```bash
   docker compose run --rm certbot certonly --webroot --webroot-path=/var/www/certbot -d erp.example.com --agree-tos -m admin@example.com
   ```

## 4. Security checklist

- [ ] Only ports 22, 80, 443 are open (`sudo ufw status`).
- [ ] Direct database ports 5432, 3306, 6379 are **not** exposed.
- [ ] Odoo is not reachable directly on port 8069 from the internet.
- [ ] `.env` and `secrets/` are never committed to git.
- [ ] Backups run daily (`scripts/backup.sh` via cron).

## 5. GitOps workflow

Every production change must:
1. Be committed and pushed to `main`.
2. Trigger `./scripts/deploy.sh` on the server (manually or via CI/CD).
3. Be preceded by `./scripts/backup.sh` (deploy.sh calls it automatically).

## 6. Backup & restore

Create a backup manually:

```bash
ssh ubuntu@YOUR_SERVER 'cd /opt/nexus-engine && ./scripts/backup.sh'
```

Restore from a backup directory:

```bash
ssh ubuntu@YOUR_SERVER 'cd /opt/nexus-engine && ./scripts/restore-backup.sh /opt/nexus-backups/YYYY-MM-DD_HH-MM-SS'
```

## 7. Troubleshooting

- **Cannot reach server**: verify `sudo ufw status` shows 80/443 ALLOW and that the public IP is correct.
- **Self-signed warning**: expected in dev mode; use a real domain for production.
- **Odoo upgrades not applied**: uncomment the `-u ...` line in `deploy.sh` or run manually.
