# Nexus Enterprise Engine — دليل النشر الشامل
# Comprehensive Deployment Guide

> هذا الدليل يأخذك من خادم فارغ إلى منصة SaaS جاهزة للبيع.

---

## Table of Contents

1. [المتطلبات / Prerequisites](#1-المتطلبات--prerequisites)
2. [البنية التحتية / Infrastructure](#2-البنية-التحتية--infrastructure)
3. [النشر بخطوة واحدة / One-Command Deploy](#3-النشر-بخطوة-واحدة--one-command-deploy)
4. [النشر اليدوي / Manual Deploy](#4-النشر-اليدوي--manual-deploy)
5. [إعداد Stripe / Stripe Setup](#5-إعداد-stripe--stripe-setup)
6. [إعداد Cloudflare / Cloudflare Setup](#6-إعداد-cloudflare--cloudflare-setup)
7. [تثبيت وحدات Odoo / Odoo Module Installation](#7-تثبيت-وحدات-odoo--odoo-module-installation)
8. [إعدادات ما بعد التثبيت / Post-Install Configuration](#8-إعدادات-ما-بعد-التثبيت--post-install-configuration)
9. [تزويد المستأجرين / Tenant Provisioning](#9-تزويد-المستأجرين--tenant-provisioning)
10. [النشر على خادم محلي / Local Dev Deployment](#10-النشر-على-خادم-محلي--local-dev-deployment)
11. [النسخ الاحتياطي / Backup](#11-النسخ-الاحتياطي--backup)
12. [فحص الإعداد / Health Checks](#12-فحص-الإعداد--health-checks)
13. [استكشاف الأخطاء / Troubleshooting](#13-استكشاف-الأخطاء--troubleshooting)
14. [قائمة التحقق النهائية / Final Checklist](#14-قائمة-التحقق-النهائية--final-checklist)

---

## 1. المتطلبات / Prerequisites

### Hardware

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| **CPU** | 2 vCPU | 4+ vCPU |
| **RAM** | 4 GB | 8+ GB |
| **Disk** | 40 GB SSD | 100+ GB SSD |
| **OS** | Ubuntu 22.04+ | Ubuntu 24.04 LTS |

### External Accounts

| Service | Purpose | When Needed |
|---------|---------|-------------|
| **Domain Name** | `erp.yourdomain.com` | Production (not needed for dev) |
| **Stripe Account** | Subscription billing | When selling SaaS |
| **Cloudflare Account** | Auto DNS for tenant subdomains | When offering self-service signup |
| **SMTP / Email** | Transactional emails | Production (Gmail, SendGrid, etc.) |
| **AI Provider Key** | Gemini/OpenAI/DeepSeek | When using AI Copilot features |

### Ports

| Port | Purpose | Exposed? |
|------|---------|----------|
| 80 | HTTP (redirects to HTTPS) | Yes |
| 443 | HTTPS (main access) | Yes |
| 22 | SSH | Yes (restrict to your IP) |
| 5432 | PostgreSQL | No (internal only) |
| 6379 | Redis | No (internal only) |
| 8069 | Odoo web | No (behind nginx) |
| 8072 | Odoo longpolling | No (behind nginx) |
| 8000 | AI services | No (behind nginx) |

---

## 2. البنية التحتية / Infrastructure

### Architecture Overview

```
                    ┌────────────────────────┐
                    │    Customer Browser     │
                    └───────────┬────────────┘
                                │ HTTPS:443
                    ┌───────────▼────────────┐
                    │   Nginx Reverse Proxy   │
                    │   (SSL, rate-limit)     │
                    └───┬────────┬────────┬──┘
                        │        │        │
              ┌─────────▼┐  ┌───▼────┐  ┌▼──────────┐
              │  Odoo 18  │  │  AI    │  │ ERPNext   │
              │  (UI/UX)  │  │ FastAPI│  │ (Backend) │
              └─────┬─────┘  └───┬────┘  └────┬──────┘
                    │            │            │
              ┌─────▼────┐  ┌───▼────┐  ┌───▼──────┐
              │PostgreSQL│  │ Redis  │  │ MariaDB  │
              │   16     │  │   7    │  │  10.6    │
              └──────────┘  └────────┘  └──────────┘
```

### Services in the Stack

| Service | Container | Description |
|---------|-----------|-------------|
| PostgreSQL 16 | `nexus_postgres` | Odoo database |
| Redis 7 | `nexus_redis` | Caching + longpolling |
| Odoo 18 | `nexus_odoo` | Main ERP application |
| AI Services | `nexus_ai` | FastAPI microservices (OCR, AI chat) |
| ERPNext 15 | `nexus_erpnext_*` | Secondary accounting engine (optional) |
| Nginx | `nexus_nginx` | Reverse proxy + SSL |
| Certbot | — | Let's Encrypt certificate renewal |
| n8n | `nexus_n8n` | Workflow automation (optional) |

---

## 3. النشر بخطوة واحدة / One-Command Deploy

### For Production (with domain)

```bash
# 1. SSH into your server
ssh ubuntu@your-server-ip

# 2. Clone the repository
git clone https://github.com/BINNISER10/ERP-AI.git /opt/nexus-engine
cd /opt/nexus-engine

# 3. Run the deployment script
sudo ODOO_DOMAIN=erp.yourdomain.com ACME_EMAIL=admin@yourdomain.com ./deploy.sh
```

The `deploy.sh` script will:
1. Install Docker + Docker Compose if missing
2. Verify DNS resolution for your domain
3. Generate random Docker secrets (passwords)
4. Start PostgreSQL + Redis + Odoo + AI services
5. Obtain Let's Encrypt SSL certificate
6. Start Nginx with HTTPS
7. Run final health check

### Output

After successful deployment:
```
🌐  Public URL:   https://erp.yourdomain.com
🔐  Admin user:   admin
🔑  Admin pass:   <random-password-from-secrets>

📦  Services running: 7 containers
```

---

## 4. النشر اليدوي / Manual Deploy

If you prefer step-by-step control over the deployment:

### Step 1: Install Docker

```bash
curl -fsSL https://get.docker.com | bash
systemctl enable docker
systemctl start docker
apt-get update && apt-get install -y docker-compose-plugin
```

### Step 2: Clone & Prepare

```bash
git clone https://github.com/BINNISER10/ERP-AI.git /opt/nexus-engine
cd /opt/nexus-engine
```

### Step 3: Generate Secrets

```bash
mkdir -p secrets
for key in postgres_db postgres_user postgres_password odoo_admin_password ai_services_api_key erpnext_admin_password; do
    head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 32 > "secrets/${key}.txt"
done
chmod 600 secrets/*.txt
```

### Step 4: Create .env File

```bash
cat > .env << 'EOF'
# Domain
ODOO_DOMAIN=erp.yourdomain.com
ODOO_WEBSITE_NAME=erp.yourdomain.com
ACME_EMAIL=admin@yourdomain.com

# PostgreSQL (used by dev docker-compose.yml)
POSTGRES_PASSWORD=change_me_to_a_strong_password

# SaaS Platform
SAAS_BASE_DOMAIN=yourdomain.com
SAAS_SELF_SERVICE_SIGNUP=true

# Cloudflare DNS (for tenant subdomains)
CLOUDFLARE_API_TOKEN=your_cloudflare_api_token
CLOUDFLARE_ZONE_ID=your_cloudflare_zone_id
CLOUDFLARE_CNAME_TARGET=erp.yourdomain.com

# Stripe Billing
STRIPE_SECRET_KEY=sk_live_or_test_your_key
STRIPE_PUBLISHABLE_KEY=pk_live_or_test_your_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# AI Services
AI_SERVICES_API_KEY=your_ai_api_key
AI_CORS_ORIGINS=https://erp.yourdomain.com
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-1.5-flash

# ERPNext
ERPNEXT_ADMIN_PASSWORD=change_me
MARIADB_ROOT_PASSWORD=change_me

# n8n
N8N_WEBHOOK_URL=https://erp.yourdomain.com/n8n/
N8N_ENCRYPTION_KEY=change_me
N8N_BASIC_AUTH_PASSWORD=change_me

# Server IP (for dev self-signed cert)
SERVER_IP=your.server.ip.address
EOF
```

### Step 5: Start the Stack

**Development (no domain, self-signed SSL):**
```bash
docker compose up -d
```

**Production (with domain + Let's Encrypt):**
```bash
# Start core services first
docker compose -f docker-compose.prod.yml up -d db redis odoo ai_services

# Wait for Odoo
for i in $(seq 1 30); do
    docker compose -f docker-compose.prod.yml exec -T odoo \
        curl -fs http://localhost:8069/web/health && break
    sleep 5
done

# Obtain SSL certificate
mkdir -p certbot/conf certbot/www
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
    --webroot --webroot-path /var/www/certbot \
    --email admin@yourdomain.com --agree-tos --no-eff-email \
    -d erp.yourdomain.com

# Start nginx with HTTPS
docker compose -f docker-compose.prod.yml up -d nginx
```

### Step 6: Verify

```bash
curl -fsI https://erp.yourdomain.com/web/health
# Expected: HTTP/2 200
```

---

## 5. إعداد Stripe / Stripe Setup

Stripe handles subscription billing for SaaS tenants.

### Step 1: Create Stripe Account

1. Sign up at [https://dashboard.stripe.com](https://dashboard.stripe.com)
2. Complete account verification (for live payments)
3. For testing, use **test mode** (no verification needed)

### Step 2: Get API Keys

In Stripe Dashboard → **Developers** → **API Keys**:
- **Publishable key**: `pk_test_...` or `pk_live_...`
- **Secret key**: `sk_test_...` or `sk_live_...`

### Step 3: Create Products & Prices

In Stripe Dashboard → **Products**:

1. Create a product for each SaaS plan (e.g., "Nexus Basic", "Nexus Pro", "Nexus Enterprise")
2. For each product, create two prices:
   - **Monthly** price (recurring, 1 month interval)
   - **Yearly** price (recurring, 1 year interval)
3. Copy the **Price IDs** (`price_...`) — you'll need them in Odoo

### Step 4: Configure Webhook

In Stripe Dashboard → **Developers** → **Webhooks** → **Add endpoint**:

- **Endpoint URL**: `https://erp.yourdomain.com/saas/billing/stripe/webhook`
- **Events to send**:
  - `checkout.session.completed`
  - `invoice.paid`
  - `invoice.payment_succeeded`
  - `invoice.payment_failed`
  - `customer.subscription.deleted`
  - `customer.subscription.past_due`
- Copy the **Signing Secret** (`whsec_...`)

### Step 5: Enter Keys in Odoo

1. Log into Odoo as admin
2. Go to **Settings** → **SaaS Billing**
3. Enter:
   - Stripe Publishable Key
   - Stripe Secret Key
   - Stripe Webhook Secret
4. Go to **SaaS** → **Plans** and enter Stripe Price IDs for each plan

### Step 6: Test the Flow

Use Stripe test cards:
- **Success**: `4242 4242 4242 4242`
- **Decline**: `4000 0000 0000 0002`
- Any future expiry, any CVC

---

## 6. إعداد Cloudflare / Cloudflare Setup

Cloudflare automates DNS record creation for tenant subdomains (e.g., `acme.yourdomain.com`).

### Step 1: Add Your Domain to Cloudflare

1. Sign up at [https://dash.cloudflare.com](https://dash.cloudflare.com)
2. **Add Site** → enter your domain
3. Update your nameservers at your registrar to Cloudflare's
4. Wait for DNS propagation (can take up to 24h)

### Step 2: Get API Token

1. Go to **My Profile** → **API Tokens**
2. **Create Token** → **Edit zone DNS** template
3. Permissions:
   - Zone: DNS: Edit
   - Zone: Zone: Read
4. Zone Resources: Include → Specific zone → your domain
5. Copy the token

### Step 3: Get Zone ID

1. Go to your domain's overview page in Cloudflare
2. Scroll down → copy the **Zone ID** from the right sidebar

### Step 4: Configure in Odoo

1. Go to **Settings** → **SaaS Configuration**
2. Enter:
   - Cloudflare API Token
   - Cloudflare Zone ID
   - CNAME Target (your Odoo server domain, e.g., `erp.yourdomain.com`)
3. Set `nexus_saas.base_domain` = `yourdomain.com`

Now when a tenant signs up with code `acme`, Cloudflare automatically creates:
```
acme.yourdomain.com  CNAME  erp.yourdomain.com
```

---

## 7. تثبيت وحدات Odoo / Odoo Module Installation

After the stack is running, install the Odoo modules:

### Option A: Via Odoo Web UI

1. Visit `https://erp.yourdomain.com`
2. Log in as `admin` (password from `secrets/odoo_admin_password.txt`)
3. Go to **Apps** → **Update Apps List**
4. Search and install in this order:

**Core SaaS Platform:**
1. `nexus_base_security` — security groups
2. `nexus_saas_tenant` — tenant management + provisioning
3. `nexus_saas_billing` — Stripe subscription billing
4. `nexus_saas_scoping` — AI self-serve onboarding wizard
5. `nexus_executive_cockpit` — executive dashboard

**Industry Modules (install what you need):**
6. `nexus_fuel_station` — fuel station operations
7. `nexus_restaurant_costing` — restaurant cost control
8. `nexus_real_estate` — real estate management
9. `nexus_contracting` — contracting/project management

**Localization (install per market):**
10. `nexus_saudi_localization` — Saudi ZATCA, VAT, Saudization
11. `nexus_zatca_compliance` — ZATCA Phase 2 cryptographic signing
12. `nexus_us_localization` — US GAAP, 1099, multi-state tax
13. `nexus_us_tax_engine` — US sales tax engine

**AI & Productivity:**
14. `ai_enterprise_copilot` — AI onboarding, reports, finance dashboard
15. `nexus_universal_mail` — email integration
16. `nexus_pure_branding` — white-label branding

### Option B: Via Command Line

```bash
# Install all core SaaS modules at once
docker compose exec odoo odoo -d nexus_erp -i \
    nexus_base_security,nexus_saas_tenant,nexus_saas_billing,\
nexus_saas_scoping,nexus_executive_cockpit,ai_enterprise_copilot,\
nexus_pure_branding \
    --stop-after-init

# Install industry modules
docker compose exec odoo odoo -d nexus_erp -i \
    nexus_fuel_station,nexus_restaurant_costing,nexus_real_estate,\
nexus_contracting \
    --stop-after-init

# Install Saudi localization
docker compose exec odoo odoo -d nexus_erp -i \
    nexus_saudi_localization,nexus_zatca_compliance \
    --stop-after-init

# Install US localization
docker compose exec odoo odoo -d nexus_erp -i \
    nexus_us_localization,nexus_us_tax_engine \
    --stop-after-init
```

---

## 8. إعدادات ما بعد التثبيت / Post-Install Configuration

### 8.1 System Parameters

In Odoo, go to **Settings** → **Technical** → **System Parameters** and verify/set:

| Key | Value | Purpose |
|-----|-------|---------|
| `web.base.url` | `https://erp.yourdomain.com` | Base URL for links/emails |
| `nexus_saas.base_domain` | `yourdomain.com` | Tenant subdomain base |
| `nexus_saas.self_service_signup` | `true` | Enable public self-service signup |
| `nexus_saas_billing.stripe_secret_key` | `sk_...` | Stripe secret key |
| `nexus_saas_billing.stripe_publishable_key` | `pk_...` | Stripe publishable key |
| `nexus_saas_billing.stripe_webhook_secret` | `whsec_...` | Stripe webhook signing secret |
| `nexus_saas.cloudflare_api_token` | `your_token` | Cloudflare API token |
| `nexus_saas.cloudflare_zone_id` | `your_zone_id` | Cloudflare zone ID |
| `nexus_saas.cloudflare_cname_target` | `erp.yourdomain.com` | CNAME target for subdomains |

### 8.2 Create SaaS Plans

Go to **SaaS** → **Plans** and create at least:

| Plan | Code | Monthly | Yearly | Max Users | Max Companies | Trial Days |
|------|------|---------|--------|-----------|---------------|------------|
| Starter | `starter` | $29 | $290 | 5 | 1 | 14 |
| Professional | `pro` | $99 | $990 | 25 | 3 | 14 |
| Enterprise | `enterprise` | $299 | $2990 | 0 (unlimited) | 0 | 30 |

For each plan, enter the corresponding **Stripe Price IDs**.

Mark one plan as **Default** (new signups get this plan).

### 8.3 Configure Email (SMTP)

Go to **Settings** → **Custom Email Servers**:

```
SMTP Server: smtp.gmail.com (or your provider)
Port: 587
Use TLS: Yes
Username: your-email@gmail.com
Password: your-app-password
```

### 8.4 Configure AI Services

If using AI Copilot features:

1. Get an API key from your AI provider:
   - **Google Gemini**: [https://aistudio.google.com](https://aistudio.google.com)
   - **OpenAI**: [https://platform.openai.com](https://platform.openai.com)
   - **DeepSeek**: [https://platform.deepseek.com](https://platform.deepseek.com)
2. Set in `.env`:
   ```env
   AI_PROVIDER=gemini
   GEMINI_API_KEY=your_key_here
   ```
3. Restart AI services: `docker compose restart ai_services`

### 8.5 Configure dbfilter (for dedicated_db tenants)

In `config/odoo.conf`, ensure:
```ini
dbfilter = ^%d$
list_db = False
```

This routes `acme.yourdomain.com` → database `acme` automatically.

### 8.6 Set Up the DB Provisioner (for dedicated_db isolation)

If offering enterprise tenants with dedicated databases:

```bash
cd saas-db-provisioner
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
# Edit config.yaml with your Postgres + Odoo credentials
python run.py --config config.yaml
```

Run as a systemd service for production:
```bash
cat > /etc/systemd/system/saas-db-provisioner.service << 'EOF'
[Unit]
Description=Nexus SaaS DB Provisioner
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/nexus-engine/saas-db-provisioner
ExecStart=/opt/nexus-engine/saas-db-provisioner/.venv/bin/python run.py --config config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl enable --now saas-db-provisioner
```

---

## 9. تزويد المستأجرين / Tenant Provisioning

### Two Isolation Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Shared** (default) | Tenant's companies/users in the same Odoo database | Most customers — fast, efficient |
| **Dedicated DB** | Separate PostgreSQL database per tenant | Enterprise — hard isolation, custom backup |

### Self-Service Signup Flow

```
Customer visits website
    ↓
Fills scoping wizard (sector, branches, POS, employees, etc.)
    ↓
nexus_saas_scoping computes quote (rule-based pricing)
    ↓
Customer clicks "Checkout"
    ↓
Stripe Checkout session created
    ↓
Customer pays via Stripe
    ↓
Stripe webhook → tenant activated
    ↓
Cloudflare DNS provisioned (acme.yourdomain.com)
    ↓
Customer receives login credentials
    ↓
Done — zero human intervention
```

### Manual Tenant Creation (Admin)

In Odoo, go to **SaaS** → **Tenants** → **New**:
1. Enter tenant name, code (subdomain), admin email
2. Select plan and isolation mode
3. Click **Provision Tenant**
4. For shared mode: tenant is active immediately
5. For dedicated_db: provisioner creates database, tenant activates when ready

### API Signup (for custom frontends)

```bash
# Create a scoping request + quote
curl -X POST https://erp.yourdomain.com/saas/scoping/quote \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme LLC",
    "contact_email": "admin@acme.com",
    "sector_code": "retail",
    "branches_count": 2,
    "pos_count": 4,
    "employees_count": 20,
    "billing_interval": "month"
  }'

# Start checkout
curl -X POST https://erp.yourdomain.com/saas/scoping/checkout \
  -H "Content-Type: application/json" \
  -d '{
    "scoping_reference": "SCOPE-0001",
    "tenant_code": "acme",
    "admin_email": "admin@acme.com"
  }'
```

---

## 10. النشر على خادم محلي / Local Dev Deployment

For development/testing without a domain:

### Using Docker Compose (dev mode)

```bash
# Clone
git clone https://github.com/BINNISER10/ERP-AI.git
cd ERP-AI

# Create .env with minimum settings
cat > .env << 'EOF'
POSTGRES_PASSWORD=dev_secret
SAAS_BASE_DOMAIN=localhost
SAAS_SELF_SERVICE_SIGNUP=false
SERVER_IP=127.0.0.1
AI_SERVICES_API_KEY=dev_ai_key
N8N_WEBHOOK_URL=https://localhost/n8n/
N8N_ENCRYPTION_KEY=dev_n8n_key
N8N_BASIC_AUTH_PASSWORD=dev_n8n_pass
ERPNEXT_ADMIN_PASSWORD=dev_erpnext
MARIADB_ROOT_PASSWORD=dev_mariadb
EOF

# Start (uses self-signed SSL)
docker compose up -d
```

Access at: `https://localhost` (accept self-signed cert warning)

### Using PowerShell Script (Windows)

```powershell
.\scripts\setup-docker-local.ps1
.\scripts\start-erp.ps1
```

### Using WSL

```powershell
.\scripts\setup-wsl-server.ps1
```

---

## 11. النسخ الاحتياطي / Backup

### Automated Daily Backup

```bash
# Add to crontab
crontab -e
# Add this line (runs daily at 2 AM):
0 2 * * * cd /opt/nexus-engine && ./scripts/backup.sh >> /var/log/nexus-backup.log 2>&1
```

### Manual Backup

```bash
cd /opt/nexus-engine
./scripts/backup.sh
```

Backups are stored in `/opt/nexus-backups/YYYY-MM-DD_HH-MM-SS/`:
- PostgreSQL dump (`nexus_erp.sql.gz`)
- Odoo filestore (`filestore.tar.gz`)
- Docker volumes metadata

### Restore

```bash
cd /opt/nexus-engine
./scripts/restore-backup.sh /opt/nexus-backups/2025-01-15_02-00-00
```

---

## 12. فحص الإعداد / Health Checks

### Quick Verification Commands

```bash
# Check all containers are running
docker compose ps

# Check Odoo health
curl -fs https://erp.yourdomain.com/web/health

# Check AI services
curl -fs https://erp.yourdomain.com/api/v1/health

# Check PostgreSQL
docker compose exec db pg_isready -U odoo -d nexus_erp

# Check Redis
docker compose exec redis redis-cli ping

# Check Odoo logs for errors
docker compose logs odoo --tail 50 | grep -i error

# Check nginx access
docker compose logs nginx --tail 20

# Verify Stripe webhook is reachable
curl -fs -X POST https://erp.yourdomain.com/saas/billing/stripe/webhook \
  -H "Content-Type: application/json" -d '{}'
# Expected: {"status":"rejected","reason":"webhook secret not configured"} or {"status":"ok"}
```

### End-to-End SaaS Flow Test

```bash
# 1. List available sectors
curl -fs https://erp.yourdomain.com/saas/scoping/sectors | python -m json.tool

# 2. Get a quote
curl -X POST https://erp.yourdomain.com/saas/scoping/quote \
  -H "Content-Type: application/json" \
  -d '{"company_name":"Test Co","contact_email":"test@test.com","sector_code":"retail"}' \
  | python -m json.tool

# 3. Verify executive cockpit
# Log into Odoo → go to Executive Cockpit menu → dashboard should load with widgets

# 4. Test Stripe (test mode)
# Use the checkout URL returned from step 2 with test card 4242 4242 4242 4242
```

---

## 13. استكشاف الأخطاء / Troubleshooting

### Odoo won't start

```bash
# Check logs
docker compose logs odoo --tail 100

# Common causes:
# - PostgreSQL not ready → wait and restart
# - Module conflict → check for error in log, uninstall conflicting module
# - Port conflict → ensure 8069/8072 aren't used by another process

docker compose restart odoo
```

### SSL certificate issues

```bash
# Check certbot logs
docker compose logs certbot

# Renew manually
docker compose run --rm certbot renew
docker compose restart nginx

# Check certificate
openssl s_client -connect erp.yourdomain.com:443 -servername erp.yourdomain.com 2>/dev/null | openssl x509 -noout -dates
```

### Stripe webhook not working

```bash
# 1. Verify webhook URL is accessible
curl -fs -X POST https://erp.yourdomain.com/saas/billing/stripe/webhook

# 2. Check webhook secret is set in Odoo
# Settings → Technical → System Parameters → search for "stripe_webhook_secret"

# 3. Check Stripe Dashboard → Developers → Webhooks → your endpoint → "Events"
#    to see if events are being sent and received

# 4. Test with Stripe CLI
stripe listen --forward-to https://erp.yourdomain.com/saas/billing/stripe/webhook
```

### Tenant subdomain not resolving

```bash
# 1. Check Cloudflare DNS records
# Log into Cloudflare → DNS → verify CNAME record exists for the tenant

# 2. Check Odoo logs for DNS provisioning errors
docker compose logs odoo | grep -i "cloudflare\|dns"

# 3. Verify dbfilter is set
docker compose exec odoo cat /etc/odoo/odoo.conf | grep dbfilter
# Should be: dbfilter = ^%d$
```

### Database connection errors

```bash
# Check PostgreSQL is running
docker compose exec db pg_isready

# Check credentials
docker compose exec db psql -U odoo -d nexus_erp -c "SELECT 1;"

# If password is wrong, update .env and restart
docker compose down
docker compose up -d
```

### ERPNext sync issues

```bash
# Check ERPNext is running
docker compose logs erpnext-backend --tail 50

# Check sync queue
# In Odoo: Settings → Technical → Queue Jobs → look for failed sync jobs

# Restart ERPNext
docker compose restart erpnext-backend erpnext-frontend erpnext-scheduler
```

---

## 14. قائمة التحقق النهائية / Final Checklist

### Infrastructure
- [ ] Server has minimum 4GB RAM, 40GB disk
- [ ] Ubuntu 22.04+ installed
- [ ] Docker + Docker Compose installed
- [ ] Ports 80, 443, 22 open (others closed)
- [ ] Domain DNS A record points to server IP

### SSL & Security
- [ ] Let's Encrypt certificate obtained (or self-signed for dev)
- [ ] HTTPS redirect working (HTTP → HTTPS)
- [ ] HSTS header present
- [ ] `secrets/` directory has restrictive permissions (600)
- [ ] `.env` is not committed to git
- [ ] UFW firewall configured: `sudo ufw allow 22,80,443/tcp`

### Odoo
- [ ] Odoo 18 running and accessible at `https://erp.yourdomain.com`
- [ ] Admin password changed from default
- [ ] `web.base.url` set correctly
- [ ] All required modules installed
- [ ] `dbfilter = ^%d$` configured (for multi-tenant)
- [ ] `list_db = False` set

### SaaS Platform
- [ ] At least one SaaS Plan created with Stripe Price IDs
- [ ] Default plan marked
- [ ] Stripe keys entered (secret, publishable, webhook)
- [ ] Stripe webhook endpoint registered and receiving events
- [ ] Cloudflare API token + Zone ID configured
- [ ] `nexus_saas.base_domain` set
- [ ] `nexus_saas.self_service_signup` = `true` (if offering self-service)

### Email
- [ ] SMTP server configured
- [ ] Test email sent successfully

### AI Services
- [ ] AI provider API key set
- [ ] `/api/v1/health` returns 200
- [ ] AI Copilot features working in Odoo

### Backup
- [ ] `scripts/backup.sh` tested
- [ ] Cron job scheduled for daily backups
- [ ] Backup restore tested

### End-to-End Verification
- [ ] Scoping wizard returns a quote via API
- [ ] Stripe checkout completes (test mode)
- [ ] Tenant created and activated after payment
- [ ] Tenant subdomain resolves (`acme.yourdomain.com`)
- [ ] Executive Cockpit dashboard loads with data
- [ ] Email notifications sent on signup

---

## Quick Reference: File Locations

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Dev stack (self-signed SSL) |
| `docker-compose.prod.yml` | Production stack (Let's Encrypt) |
| `deploy.sh` | One-command deployment script |
| `config/odoo.conf` | Odoo configuration |
| `config/nginx.conf` | Production Nginx (HTTPS + Let's Encrypt) |
| `config/nginx.dev.conf` | Dev Nginx (self-signed SSL) |
| `config/postgresql.conf` | PostgreSQL tuning |
| `secrets/*.txt` | Docker secrets (passwords) |
| `.env` | Environment variables |
| `scripts/backup.sh` | Backup script |
| `scripts/restore-backup.sh` | Restore script |
| `scripts/harden-server.sh` | Server security hardening |
| `saas-db-provisioner/` | Dedicated DB provisioner service |

---

## Support

- **Repository**: [https://github.com/BINNISER10/ERP-AI](https://github.com/BINNISER10/ERP-AI)
- **Email**: support@nexus-engine.app

---

<p align="center">
  <b>Nexus Enterprise Engine — دليل النشر الشامل</b><br/>
  <i>Comprehensive Deployment Guide v1.0</i>
</p>
