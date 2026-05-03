# compare-transit.fr MVP — Deployment Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (some steps require manual UI clicks on Cloudflare/Hetzner dashboards that an agent cannot do — this plan is human-led with agent assist for code/config). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Stand up the production infrastructure for `compare-transit.fr` MVP — Hetzner VPS for backend + Cloudflare R2 for object storage + Cloudflare Pages for static frontend — within 1 week, at €5.50/month run cost.

**Architecture:**
```
                                    ┌─────────────────────────────────┐
   user (Le Monde reader, …)        │  Cloudflare DNS + CDN           │
            │                       │  compare-transit.fr             │
            ▼                       └────────────────┬────────────────┘
   Cloudflare Pages                                   │
   (compare-transit.fr static SSG ─────────────┐      │
    + /api proxied to backend)                  │      │
                                                ▼      ▼
                                      Hetzner CX22 (Strasbourg, FR)
                                      ┌──────────────────────────────┐
                                      │ Caddy (reverse proxy + TLS)  │
                                      │       ↓                      │
                                      │  Docker Compose:             │
                                      │   - FastAPI (panel API)      │
                                      │   - Worker (Celery)          │
                                      │   - Postgres 16              │
                                      │   - Redis (Celery broker)    │
                                      └──────────────┬───────────────┘
                                                     │ s3-compatible
                                                     ▼
                                      Cloudflare R2 bucket
                                      `compare-transit-feeds`
                                      (GTFS history archive, ~30 GB)
```

**Tech Stack:** Hetzner Cloud · Ubuntu 24.04 LTS · Docker 27 · Docker Compose v2 · Caddy 2 · Postgres 16 · Redis 7 · Cloudflare R2 · Cloudflare Pages · Cloudflare DNS · GitHub Actions

**Cost:** Hetzner CX22 €4.59/mo + R2 storage €0.30/mo (after 10 GB free) + Cloudflare Pages €0 + Cloudflare DNS €0 = **~€5/month**

**Scope:** Phase A only. Stands up `compare-transit.fr` from scratch. **Does NOT migrate** existing GTFS Miner (Zeabur) — that's a separate post-MVP plan.

**Estimated time:** 1 week single-dev (parallel to Plan 1's discovery work).

---

## Pre-flight: Accounts to set up (once, before Task 1)

These require human web-UI actions and credit cards. Cannot be automated.

- [ ] **Hetzner Cloud account** — https://accounts.hetzner.com/signUp
  - Enable 2FA
  - Add a payment method
  - Choose **Strasbourg (FRA1)** region for FR latency
- [ ] **Cloudflare account** — https://dash.cloudflare.com/sign-up
  - Enable 2FA
  - Add domain `compare-transit.fr` (registrar must allow nameserver change to Cloudflare's)
- [ ] **Domain registrar**: register `compare-transit.fr` if not already done
  - Verify availability at https://www.afnic.fr (`.fr` registry)
  - OVH/Gandi/Namecheap all work; cost ~€10/year
- [ ] **GitHub repository**: confirm push access to current GTFS Miner repo (deployment will use existing repo + add `frontend-panel/` and infra/ subdirs)

---

## File Structure (added by this plan)

```
infra/
├── hetzner/
│   ├── docker-compose.yml      — production compose
│   ├── Caddyfile               — reverse proxy + TLS config
│   ├── .env.production.example — secrets template (NEVER commit real secrets)
│   ├── postgres/
│   │   └── init.sql            — schema isolation between products
│   └── scripts/
│       ├── bootstrap.sh        — first-time host setup (Docker, firewall)
│       ├── deploy.sh           — pull + restart containers
│       └── backup.sh           — pg_dump → R2 daily
├── cloudflare/
│   ├── pages-project.md        — manual setup steps for Pages
│   └── r2-bucket-setup.md      — bucket + IAM credential steps
└── README.md                   — runbook overview

.github/workflows/
└── deploy-compare-transit.yml  — push-to-deploy CI

frontend-panel/                 — created in Plan 3, deployed by this plan's CI
├── (vite + vike app — placeholder index.html for Phase A smoke test)
└── package.json
```

---

## Task 1: Provision Hetzner VPS + Initial Hardening

**Goal:** Get a working Ubuntu 24.04 VPS in Strasbourg with Docker, firewall, and SSH-key-only access.

**Files:**
- Create: `infra/hetzner/scripts/bootstrap.sh`
- Create: `infra/README.md` (runbook overview)

- [ ] **Step 1: Create the Hetzner Cloud Server (web UI)**

In Hetzner Cloud Console:
1. Click "New Server"
2. **Location**: Strasbourg (FRA1)
3. **Image**: Ubuntu 24.04
4. **Type**: CX22 (3 vCPU shared AMD, 4 GB RAM, 80 GB NVMe SSD, 20 TB traffic) — €4.59/mo
5. **SSH Keys**: paste your public key from `~/.ssh/id_ed25519.pub` (or generate with `ssh-keygen -t ed25519`)
6. **Name**: `compare-transit-prod`
7. **Networking**: keep default (IPv4 + IPv6 enabled)

After provisioning, note the public IPv4 address.

- [ ] **Step 2: First SSH connection + verify**

```powershell
ssh root@<HETZNER_IPV4>
# Inside the VM:
lsb_release -a    # verify Ubuntu 24.04
uname -a
df -h             # verify ~80 GB available
```

If SSH refuses with "Permission denied (publickey)", check key was added correctly to the server.

- [ ] **Step 3: Create the bootstrap script**

Create `infra/hetzner/scripts/bootstrap.sh`:

```bash
#!/usr/bin/env bash
# infra/hetzner/scripts/bootstrap.sh — first-time host setup
# Run as root: ssh root@<host> "bash -s" < bootstrap.sh
set -euo pipefail

# 1. System update
apt-get update -y
apt-get upgrade -y

# 2. Install essentials
apt-get install -y \
  ca-certificates curl gnupg ufw fail2ban htop tmux jq unzip \
  postgresql-client-16

# 3. Install Docker (official Docker repo, not Ubuntu's snap)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | tee /etc/apt/sources.list.d/docker.list >/dev/null
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 4. Firewall: allow SSH + HTTP + HTTPS only
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force enable

# 5. fail2ban with default jail.conf (covers SSH brute force)
systemctl enable --now fail2ban

# 6. Disable root password SSH (key-only)
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
systemctl restart sshd

# 7. Create deployment user (non-root for daily ops)
id -u deploy &>/dev/null || useradd -m -s /bin/bash -G docker deploy
mkdir -p /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys

# 8. Project dir
mkdir -p /opt/compare-transit
chown deploy:deploy /opt/compare-transit

echo "Bootstrap complete."
echo "Reconnect as: ssh deploy@$(hostname -I | awk '{print $1}')"
```

- [ ] **Step 4: Run bootstrap script remotely**

From your local machine:
```powershell
$ip = "<HETZNER_IPV4>"
ssh root@$ip "bash -s" < infra/hetzner/scripts/bootstrap.sh
```

Expected output: each step logs success; ends with "Reconnect as: ssh deploy@..."

- [ ] **Step 5: Verify deploy user works**

```powershell
ssh deploy@$ip "docker --version && docker compose version"
```

Expected: Docker version 27.x; Docker Compose version v2.x

- [ ] **Step 6: Commit the script**

```powershell
git add infra/hetzner/scripts/bootstrap.sh
git add infra/README.md  # write at least a header + reference to this plan
git commit -m "infra: hetzner bootstrap script + runbook stub"
```

---

## Task 2: Cloudflare R2 Bucket + S3 Credentials

**Goal:** Create R2 bucket for GTFS feed archive + obtain S3-compatible credentials for backend access.

**Files:**
- Create: `infra/cloudflare/r2-bucket-setup.md` (manual setup notes)

- [ ] **Step 1: Create R2 bucket (Cloudflare web UI)**

In Cloudflare Dashboard → R2 Object Storage:
1. Click "Create bucket"
2. **Name**: `compare-transit-feeds`
3. **Location hint**: WEUR (Western Europe)
4. **Default storage class**: Standard
5. Click "Create bucket"

- [ ] **Step 2: Generate R2 API token**

In R2 dashboard → "Manage R2 API Tokens":
1. Click "Create API token"
2. **Token name**: `compare-transit-backend`
3. **Permissions**: "Object Read & Write"
4. **Specify bucket**: `compare-transit-feeds`
5. Optional **TTL**: leave blank (no expiration)
6. Click "Create API Token"

**IMPORTANT**: copy `Access Key ID` and `Secret Access Key` immediately — they shown only once.

Also note your **R2 endpoint URL** (format: `https://<account_id>.r2.cloudflarestorage.com`) — find your account ID under "R2" → "Overview".

- [ ] **Step 3: Document setup in `infra/cloudflare/r2-bucket-setup.md`**

```markdown
# Cloudflare R2 — compare-transit.fr setup

## Bucket
- Name: `compare-transit-feeds`
- Location: WEUR
- Created: <date>

## Access
- API Token name: `compare-transit-backend`
- Permissions: Object Read & Write, scoped to `compare-transit-feeds`
- Credentials stored in: Hetzner host `/opt/compare-transit/.env.production` (NEVER in git)

## Endpoint
- S3-compatible URL: `https://<account_id>.r2.cloudflarestorage.com`
- Region: `auto`

## Bucket layout
```
compare-transit-feeds/
├── feeds/<network_slug>/<feed_start_date>.zip      — dedup'd GTFS archive
├── validator-output/<feed_id>.json                  — MobilityData reports
└── backup/postgres/<YYYY-MM-DD>.sql.gz              — daily DB dumps
```
```

- [ ] **Step 4: Commit doc (no secrets!)**

```powershell
git add infra/cloudflare/r2-bucket-setup.md
git commit -m "infra: cloudflare R2 setup documentation (no secrets)"
```

---

## Task 3: Postgres + Docker Compose Production Stack

**Goal:** Author the production Docker Compose stack — Postgres + Redis + Caddy + (placeholder app container until Plan 1 builds it). Deploy to Hetzner.

**Files:**
- Create: `infra/hetzner/docker-compose.yml`
- Create: `infra/hetzner/Caddyfile`
- Create: `infra/hetzner/.env.production.example`
- Create: `infra/hetzner/postgres/init.sql`

- [ ] **Step 1: Author docker-compose.yml**

Create `infra/hetzner/docker-compose.yml`:

```yaml
# Production stack on Hetzner (single host)
# Run on host: cd /opt/compare-transit && docker compose up -d
services:

  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "127.0.0.1:5432:5432"  # localhost-only — never expose to internet
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports:
      - "127.0.0.1:6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      retries: 5

  panel-api:
    image: ghcr.io/${GITHUB_OWNER}/${GITHUB_REPO}/panel-api:${IMAGE_TAG:-latest}
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      R2_ACCOUNT_ID: ${R2_ACCOUNT_ID}
      R2_ACCESS_KEY_ID: ${R2_ACCESS_KEY_ID}
      R2_SECRET_ACCESS_KEY: ${R2_SECRET_ACCESS_KEY}
      R2_BUCKET: compare-transit-feeds
      ENVIRONMENT: production
    ports:
      - "127.0.0.1:8001:8001"

  panel-worker:
    image: ghcr.io/${GITHUB_OWNER}/${GITHUB_REPO}/panel-api:${IMAGE_TAG:-latest}
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A app.celery_app.celery worker -P solo --loglevel=info
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      R2_ACCOUNT_ID: ${R2_ACCOUNT_ID}
      R2_ACCESS_KEY_ID: ${R2_ACCESS_KEY_ID}
      R2_SECRET_ACCESS_KEY: ${R2_SECRET_ACCESS_KEY}
      R2_BUCKET: compare-transit-feeds
      ENVIRONMENT: production

  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config

volumes:
  postgres_data:
  redis_data:
  caddy_data:
  caddy_config:
```

- [ ] **Step 2: Author Caddyfile**

Create `infra/hetzner/Caddyfile`:

```caddyfile
# Caddy reverse proxy + automatic Let's Encrypt TLS

{
    email admin@compare-transit.fr
}

api.compare-transit.fr {
    reverse_proxy panel-api:8001
    encode gzip
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
    }
    log {
        output file /var/log/caddy/api.access.log {
            roll_size 100mb
            roll_keep 5
        }
    }
}

# Health check endpoint without TLS for monitoring services
:80 {
    handle /healthz {
        respond "ok" 200
    }
    redir https://{host}{uri} permanent
}
```

- [ ] **Step 3: Author secrets template**

Create `infra/hetzner/.env.production.example`:

```bash
# Copy to .env.production on host and fill in values
# NEVER commit .env.production with real values

# Postgres
POSTGRES_USER=panel_app
POSTGRES_PASSWORD=<generate via: openssl rand -base64 32>
POSTGRES_DB=compare_transit

# Redis
REDIS_PASSWORD=<generate via: openssl rand -base64 32>

# Cloudflare R2 (from Task 2)
R2_ACCOUNT_ID=<your account ID>
R2_ACCESS_KEY_ID=<from R2 API token>
R2_SECRET_ACCESS_KEY=<from R2 API token>

# GitHub Container Registry image tag
GITHUB_OWNER=<your github username>
GITHUB_REPO=GTFS-Miner
IMAGE_TAG=latest
```

- [ ] **Step 4: Author Postgres init.sql (schema isolation)**

Create `infra/hetzner/postgres/init.sql`:

```sql
-- Run once at first container start (Postgres entrypoint hook)
-- Creates schemas to isolate compare-transit panel data from any future product

CREATE SCHEMA IF NOT EXISTS panel;
CREATE SCHEMA IF NOT EXISTS gtfs_miner;

-- Set default search_path to panel for the app user
ALTER DATABASE compare_transit SET search_path TO panel, public;

-- Grant
GRANT ALL ON SCHEMA panel TO panel_app;
GRANT ALL ON SCHEMA gtfs_miner TO panel_app;
```

- [ ] **Step 5: Update Alembic config to use the `panel` schema**

In `backend/alembic/env.py`, after the `target_metadata` assignment, add:

```python
# Compare-transit panel tables live in the `panel` schema (production isolation)
if context.is_offline_mode():
    context.configure(version_table_schema="panel")
```

Update Plan 1 Task 6 model definitions to add `__table_args__ = {"schema": "panel"}` per panel table — but **defer this until production deploy**, keep them schema-less for SQLite tests. Use environment-controlled schema:

In `backend/app/db/models.py`, at top:
```python
import os
PANEL_SCHEMA = os.environ.get("PANEL_DB_SCHEMA", None)  # None = no schema (SQLite tests)
```

And per panel table:
```python
class PanelNetwork(Base):
    __tablename__ = "panel_networks"
    __table_args__ = ({"schema": PANEL_SCHEMA},) if PANEL_SCHEMA else ()
```

This is a careful change — coordinate with Plan 1 Task 6 timing.

- [ ] **Step 6: Copy compose stack to Hetzner host**

```powershell
$ip = "<HETZNER_IPV4>"
scp -r infra/hetzner/* deploy@${ip}:/opt/compare-transit/
ssh deploy@$ip "cd /opt/compare-transit && cp .env.production.example .env.production"
ssh deploy@$ip "nano /opt/compare-transit/.env.production"
# Fill in real secrets via SSH-into-edit; save and exit
```

- [ ] **Step 7: Smoke test — start Postgres + Redis only (panel-api/worker images don't exist yet)**

```powershell
ssh deploy@$ip "cd /opt/compare-transit && docker compose up -d postgres redis caddy"
ssh deploy@$ip "docker compose ps"
ssh deploy@$ip "docker compose logs postgres --tail=20"
```

Expected: postgres + redis + caddy in "running (healthy)" state.

- [ ] **Step 8: Verify Postgres schema isolation**

```powershell
ssh deploy@$ip "docker exec compare-transit-postgres-1 psql -U panel_app -d compare_transit -c '\dn'"
```

Expected output: schemas `panel`, `gtfs_miner`, `public` listed.

- [ ] **Step 9: Commit**

```powershell
git add infra/hetzner/
git commit -m "infra: docker compose production stack + caddy reverse proxy

Postgres 16 + Redis 7 + Caddy 2 (Let's Encrypt). Schema isolation via
init.sql. .env.production template with no secrets."
```

---

## Task 4: Cloudflare DNS + Pages Project

**Goal:** Point `compare-transit.fr` (frontend) and `api.compare-transit.fr` (backend) DNS to Cloudflare; create Pages project for the frontend.

**Files:**
- Create: `infra/cloudflare/pages-project.md`
- Create: `frontend-panel/index.html` (placeholder for Phase A smoke test)

- [ ] **Step 1: Add domain to Cloudflare (web UI)**

In Cloudflare Dashboard:
1. Click "Add site"
2. Enter `compare-transit.fr`
3. Select "Free" plan
4. Cloudflare scans existing DNS records — review then "Continue"
5. **Update nameservers** at your registrar to Cloudflare's (e.g., `aria.ns.cloudflare.com`, `bart.ns.cloudflare.com`). Propagation: 0–24h.

- [ ] **Step 2: Add DNS records**

In Cloudflare → DNS:
1. **A record**: `api.compare-transit.fr` → `<HETZNER_IPV4>` (Proxied OFF — Caddy handles TLS directly)
2. **CNAME record**: `compare-transit.fr` (root) → will be set by Pages in next step
3. **CNAME record**: `www.compare-transit.fr` → will be set by Pages

- [ ] **Step 3: Verify DNS propagation**

```powershell
nslookup api.compare-transit.fr
# Expected: returns Hetzner IP
```

If still returns NXDOMAIN, wait up to 24h for nameserver change to propagate.

- [ ] **Step 4: Verify Caddy + TLS for api subdomain**

Once DNS resolves:
```powershell
curl -I https://api.compare-transit.fr/healthz
```

Expected: `HTTP/2 200`. If TLS errors, check:
- Cloudflare A record is "DNS only" (not Proxied), since Caddy fetches its own cert
- Port 80 + 443 reachable (verify with `telnet api.compare-transit.fr 443`)

- [ ] **Step 5: Create Pages project**

In Cloudflare Dashboard → Workers & Pages → Create:
1. Click "Pages" tab → "Connect to Git"
2. Authorize GitHub access to the repo
3. Select repo (the GTFS Miner repo)
4. **Project name**: `compare-transit-panel`
5. **Production branch**: `master`
6. **Build settings**:
   - Framework preset: None (manual)
   - Build command: `cd frontend-panel && npm install && npm run build`
   - Build output directory: `frontend-panel/dist`
   - Root directory: `/` (repo root)
7. **Environment variables** (build-time):
   - `VITE_API_BASE=https://api.compare-transit.fr`
8. Click "Save and Deploy"

First build will fail because `frontend-panel/` doesn't exist yet — fix in next step.

- [ ] **Step 6: Create placeholder frontend (Phase A smoke test)**

Create `frontend-panel/package.json`:

```json
{
  "name": "compare-transit-panel",
  "version": "0.0.1",
  "private": true,
  "scripts": {
    "build": "mkdir -p dist && cp index.html dist/"
  }
}
```

Create `frontend-panel/index.html`:

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>compare-transit.fr</title>
  <meta name="description" content="Le panel statistique des réseaux de transport public français — bientôt en ligne.">
</head>
<body>
  <h1>compare-transit.fr</h1>
  <p>Le panel statistique des réseaux de transport public français — bientôt en ligne.</p>
  <p><small>Phase A deployment smoke test · Plan 3 brings the real site.</small></p>
</body>
</html>
```

Push to master. Cloudflare Pages auto-builds and deploys.

- [ ] **Step 7: Custom domain on Pages**

In Pages project → Custom Domains:
1. "Set up a custom domain" → `compare-transit.fr`
2. Cloudflare auto-creates the CNAME (or A) record
3. Repeat for `www.compare-transit.fr`
4. Verify in browser: `https://compare-transit.fr` shows the placeholder page

- [ ] **Step 8: Commit**

```powershell
git add frontend-panel/package.json frontend-panel/index.html
git add infra/cloudflare/pages-project.md
git commit -m "infra: cloudflare pages placeholder + DNS docs"
git push origin master
```

---

## Task 5: GitHub Actions — Backend Image CI/CD

**Goal:** Push-to-deploy: every push to `master` builds the panel-api image, pushes to GHCR, and SSHes into Hetzner to redeploy.

**Files:**
- Create: `.github/workflows/deploy-compare-transit.yml`
- Create: `backend/Dockerfile.panel`
- Create: `infra/hetzner/scripts/deploy.sh`

- [ ] **Step 1: Create panel-api Dockerfile**

Create `backend/Dockerfile.panel`:

```dockerfile
FROM python:3.11-slim AS base

# System deps for geopandas + java (for MobilityData validator)
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libgeos-dev libproj-dev libgdal-dev \
      default-jre-headless curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app
COPY backend/app /app/app
COPY backend/alembic /app/alembic
COPY backend/alembic.ini /app/alembic.ini

# MobilityData validator JAR (downloaded at build time)
RUN mkdir -p /opt/validator && \
    curl -fsSL https://github.com/MobilityData/gtfs-validator/releases/download/v6.0.0/gtfs-validator-6.0.0-cli.jar \
      -o /opt/validator/gtfs-validator-cli.jar

ENV PYTHONUNBUFFERED=1 \
    PANEL_DB_SCHEMA=panel \
    VALIDATOR_JAR=/opt/validator/gtfs-validator-cli.jar

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

- [ ] **Step 2: Create deploy.sh on host**

Create `infra/hetzner/scripts/deploy.sh`:

```bash
#!/usr/bin/env bash
# infra/hetzner/scripts/deploy.sh — pull latest image + restart
# Run on Hetzner host as deploy user
set -euo pipefail

cd /opt/compare-transit
docker compose pull panel-api panel-worker
docker compose up -d panel-api panel-worker
docker compose exec -T panel-api alembic upgrade head
echo "Deploy complete. Status:"
docker compose ps
```

Push the file to host:
```powershell
scp infra/hetzner/scripts/deploy.sh deploy@<HETZNER_IPV4>:/opt/compare-transit/scripts/
ssh deploy@<HETZNER_IPV4> "chmod +x /opt/compare-transit/scripts/deploy.sh"
```

- [ ] **Step 3: Add GitHub Secrets (web UI)**

GitHub repo → Settings → Secrets and variables → Actions → New repository secret:

- `HETZNER_HOST` = `<HETZNER_IPV4>`
- `HETZNER_SSH_KEY` = full content of your private key (the one whose pub key was added to Hetzner)
- `GHCR_TOKEN` = a fine-grained PAT with `write:packages` scope (Settings → Developer settings → Personal access tokens)

- [ ] **Step 4: Create the workflow**

Create `.github/workflows/deploy-compare-transit.yml`:

```yaml
name: Deploy compare-transit panel

on:
  push:
    branches: [master]
    paths:
      - 'backend/**'
      - 'infra/**'
      - '.github/workflows/deploy-compare-transit.yml'

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}/panel-api

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push panel-api
        uses: docker/build-push-action@v6
        with:
          context: .
          file: backend/Dockerfile.panel
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:latest
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    needs: build-and-push
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Hetzner via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.HETZNER_HOST }}
          username: deploy
          key: ${{ secrets.HETZNER_SSH_KEY }}
          script: bash /opt/compare-transit/scripts/deploy.sh
```

- [ ] **Step 5: Trigger first build**

Push the workflow file to master:

```powershell
git add backend/Dockerfile.panel
git add infra/hetzner/scripts/deploy.sh
git add .github/workflows/deploy-compare-transit.yml
git commit -m "ci: github actions push-to-deploy for compare-transit panel"
git push origin master
```

Watch GitHub Actions tab. Expected:
- `build-and-push` job: ~5–8 min (Docker build + GHCR push)
- `deploy` job: ~30s (SSH + docker compose pull + restart)

If first build fails, common causes:
- Validator JAR URL changed → update version in Dockerfile
- `requirements.txt` install fails → may need build-time deps added
- SSH connection refused → check `HETZNER_SSH_KEY` secret is the **private** key

- [ ] **Step 6: Verify panel-api responds**

After deploy succeeds:
```powershell
curl https://api.compare-transit.fr/healthz
# Expected: 200 OK from panel-api (need to add a /healthz route in app.main)
```

If 502 Bad Gateway, the panel-api container probably crashed. Check logs:
```powershell
ssh deploy@<HETZNER_IPV4> "docker compose logs panel-api --tail=50"
```

- [ ] **Step 7: Add /healthz to panel API (if not present)**

Quick edit to `backend/app/main.py`:
```python
@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

Push, redeploy via CI, retest with curl.

---

## Task 6: Backup Automation (pg_dump → R2)

**Goal:** Daily Postgres dump pushed to R2 with 30-day retention.

**Files:**
- Create: `infra/hetzner/scripts/backup.sh`
- Create: `infra/hetzner/scripts/install-cron.sh`

- [ ] **Step 1: Author backup script**

Create `infra/hetzner/scripts/backup.sh`:

```bash
#!/usr/bin/env bash
# Daily Postgres backup → R2
# Run via cron: 0 3 * * * /opt/compare-transit/scripts/backup.sh
set -euo pipefail

cd /opt/compare-transit
source .env.production

DATE=$(date +%F)
DUMP_FILE=/tmp/compare_transit_${DATE}.sql.gz

# 1. Dump
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$DUMP_FILE"

# 2. Upload to R2 (uses aws CLI configured for R2 endpoint)
aws --endpoint-url="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com" \
    --profile compare-transit-r2 \
    s3 cp "$DUMP_FILE" "s3://compare-transit-feeds/backup/postgres/${DATE}.sql.gz"

# 3. Local cleanup
rm "$DUMP_FILE"

# 4. Retention: delete dumps older than 30 days from R2
CUTOFF=$(date -d "30 days ago" +%F)
aws --endpoint-url="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com" \
    --profile compare-transit-r2 \
    s3 ls "s3://compare-transit-feeds/backup/postgres/" | \
while read -r line; do
  dump_date=$(echo "$line" | awk '{print $4}' | sed 's/\.sql\.gz$//')
  if [[ -n "$dump_date" && "$dump_date" < "$CUTOFF" ]]; then
    aws --endpoint-url="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com" \
        --profile compare-transit-r2 \
        s3 rm "s3://compare-transit-feeds/backup/postgres/${dump_date}.sql.gz"
    echo "Deleted old backup: ${dump_date}"
  fi
done

echo "Backup ${DATE} done."
```

- [ ] **Step 2: Configure aws CLI for R2 on host**

```bash
# Run as deploy user on Hetzner host
sudo apt-get install -y awscli
mkdir -p ~/.aws
cat > ~/.aws/credentials <<EOF
[compare-transit-r2]
aws_access_key_id = <R2_ACCESS_KEY_ID>
aws_secret_access_key = <R2_SECRET_ACCESS_KEY>
EOF
cat > ~/.aws/config <<EOF
[profile compare-transit-r2]
region = auto
output = json
EOF
chmod 600 ~/.aws/credentials
```

- [ ] **Step 3: Test backup manually**

```bash
# On host:
chmod +x /opt/compare-transit/scripts/backup.sh
/opt/compare-transit/scripts/backup.sh
# Expected: "Backup YYYY-MM-DD done."
```

Verify in Cloudflare R2 dashboard: bucket should contain `backup/postgres/<date>.sql.gz`.

- [ ] **Step 4: Install daily cron**

Create `infra/hetzner/scripts/install-cron.sh`:

```bash
#!/usr/bin/env bash
# Install daily backup cron for deploy user
set -euo pipefail
(crontab -l 2>/dev/null; echo "0 3 * * * /opt/compare-transit/scripts/backup.sh >> /var/log/compare-transit-backup.log 2>&1") | sort -u | crontab -
echo "Cron installed. Current crontab:"
crontab -l
```

Run on host:
```bash
chmod +x /opt/compare-transit/scripts/install-cron.sh
sudo touch /var/log/compare-transit-backup.log && sudo chown deploy /var/log/compare-transit-backup.log
/opt/compare-transit/scripts/install-cron.sh
```

- [ ] **Step 5: Commit scripts**

```powershell
git add infra/hetzner/scripts/backup.sh
git add infra/hetzner/scripts/install-cron.sh
git commit -m "infra: daily postgres backup → R2 with 30-day retention"
```

---

## Task 7: Monitoring + Alerts

**Goal:** Free-tier monitoring that pings the production API + alerts on outages.

- [ ] **Step 1: UptimeRobot account + monitor**

1. Register at https://uptimerobot.com (free tier: 50 monitors, 5-min interval)
2. Create monitor:
   - **Type**: HTTP(s)
   - **URL**: `https://api.compare-transit.fr/healthz`
   - **Friendly Name**: `compare-transit panel API`
   - **Interval**: 5 minutes
3. Add alert contact: your email + optionally Slack/Telegram webhook
4. Create second monitor for the frontend:
   - **URL**: `https://compare-transit.fr`
   - **Name**: `compare-transit panel frontend`

- [ ] **Step 2: Verify alert by simulating outage**

```bash
ssh deploy@<HETZNER_IPV4> "docker compose stop panel-api"
# Wait 10 minutes; UptimeRobot should email/notify
ssh deploy@<HETZNER_IPV4> "docker compose start panel-api"
```

- [ ] **Step 3: Add status page (optional, free)**

UptimeRobot → Status Pages → Create. Public URL like `stats.uptimerobot.com/<id>` to share with stakeholders.

- [ ] **Step 4: Document in runbook**

Append to `infra/README.md`:

```markdown
## Monitoring

- **UptimeRobot dashboard**: https://uptimerobot.com/dashboard (admin@compare-transit.fr login)
- **Public status page**: <URL>
- **Alert channels**: email (admin@compare-transit.fr) + Slack #compare-transit-ops
- **Logs on host**: `docker compose logs panel-api --tail=100 -f`
- **Caddy access logs**: `/var/log/caddy/api.access.log` on host
```

```powershell
git add infra/README.md
git commit -m "infra: monitoring runbook (uptimerobot)"
```

---

## Task 8: Production Smoke Test + Documentation

**Goal:** End-to-end validation that all infrastructure works together. Document the runbook for future ops.

- [ ] **Step 1: Smoke test checklist**

Verify each item:

- [ ] `https://compare-transit.fr` loads placeholder page (Pages working)
- [ ] `https://api.compare-transit.fr/healthz` returns 200 (Caddy + Hetzner working)
- [ ] `https://api.compare-transit.fr/docs` shows FastAPI Swagger UI (panel-api working)
- [ ] DNS lookup `compare-transit.fr` → Cloudflare; `api.compare-transit.fr` → Hetzner IP
- [ ] TLS valid (no browser warning) on both
- [ ] `docker compose ps` on host: all services healthy
- [ ] Postgres connection from panel-api: `docker compose exec panel-api alembic current` returns a revision
- [ ] R2 bucket reachable: `aws --endpoint-url="..." s3 ls s3://compare-transit-feeds/` returns no error
- [ ] One backup file present at `s3://compare-transit-feeds/backup/postgres/`
- [ ] UptimeRobot reports both monitors as UP
- [ ] GitHub Actions: latest deploy workflow run is green

- [ ] **Step 2: Disaster recovery dry run**

Test the backup actually works:
```bash
# On host:
LATEST_BACKUP=$(aws --endpoint-url="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com" \
                --profile compare-transit-r2 \
                s3 ls s3://compare-transit-feeds/backup/postgres/ | tail -1 | awk '{print $4}')
aws --endpoint-url="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com" \
    --profile compare-transit-r2 \
    s3 cp "s3://compare-transit-feeds/backup/postgres/${LATEST_BACKUP}" /tmp/restore-test.sql.gz

# Restore into a temp DB to verify
docker exec -it compare-transit-postgres-1 createdb -U panel_app restore_test
gunzip -c /tmp/restore-test.sql.gz | docker exec -i compare-transit-postgres-1 \
    psql -U panel_app -d restore_test
docker exec -it compare-transit-postgres-1 psql -U panel_app -d restore_test -c "\dt panel.*"
# Drop test DB
docker exec -it compare-transit-postgres-1 dropdb -U panel_app restore_test
```

Expected: tables list correctly. Document any issues in runbook.

- [ ] **Step 3: Complete runbook**

Update `infra/README.md` with full sections:

```markdown
# compare-transit.fr Infrastructure Runbook

## Stack
- Hetzner CX22 in Strasbourg (FRA1), IPv4 `<X.X.X.X>`
- Cloudflare DNS + Pages + R2
- Postgres 16 + Redis 7 + Caddy 2 (Docker Compose)
- GitHub Actions push-to-deploy

## Domains
- `compare-transit.fr` (frontend, Cloudflare Pages)
- `www.compare-transit.fr` (CNAME to root)
- `api.compare-transit.fr` (backend, Hetzner)

## Daily ops
- Logs: `ssh deploy@<host> "cd /opt/compare-transit && docker compose logs -f"`
- DB shell: `ssh deploy@<host> "docker compose exec postgres psql -U panel_app -d compare_transit"`
- Restart service: `ssh deploy@<host> "cd /opt/compare-transit && docker compose restart panel-api"`

## Deploy
- Automatic: push to `master`
- Manual: `ssh deploy@<host> "/opt/compare-transit/scripts/deploy.sh"`

## Backups
- Location: `s3://compare-transit-feeds/backup/postgres/<YYYY-MM-DD>.sql.gz`
- Retention: 30 days
- Frequency: daily 03:00 UTC

## Incident response
1. Check UptimeRobot for which service down
2. SSH to host, `docker compose ps` to see container states
3. `docker compose logs <service> --tail=100`
4. If DB corrupt: see "Restore" section
5. If host down: provision new Hetzner CX22, run bootstrap.sh, restore from latest backup

## Restore procedure (DB)
[steps from Task 8 Step 2]

## Cost
~€5/month total. Hetzner €4.59 + R2 €0.30 + Cloudflare €0.

## When to migrate to Scaleway
If we sign a B2G client requiring SecNumCloud / sovereign cloud.
This plan does NOT cover that migration — write a new plan when triggered.
```

- [ ] **Step 4: Final commit + tag**

```powershell
git add infra/README.md
git commit -m "infra: complete runbook + DR procedures"
git tag -a deployment-phase-a-complete -m "compare-transit.fr Phase A deployment ready"
git push origin master
git push origin deployment-phase-a-complete
```

---

# Self-Review

| Spec / Goal | Plan task |
|-------------|-----------|
| Hetzner VPS provisioned | T1 |
| R2 bucket + IAM | T2 |
| Docker compose stack (Postgres + Redis + Caddy) | T3 |
| TLS + DNS for `compare-transit.fr` + `api.compare-transit.fr` | T4 |
| Cloudflare Pages frontend hosting | T4 |
| Push-to-deploy CI/CD | T5 |
| Daily encrypted DB backup | T6 |
| Monitoring + alerts | T7 |
| End-to-end smoke test + runbook | T8 |

**Out of scope** (separate plans, not part of Phase A):
- GTFS Miner Pro migration from Zeabur (Phase B/C, post-MVP)
- Backfill of 17,500 GTFS feeds to R2 (Plan 2 indicator pipeline)
- Frontend SSG implementation (Plan 3)
- Sovereign cloud migration (V2+ when B2G triggered)

**Total cost (verified during execution)**: __ €/month (fill in after T8 completes)

**Phase B trigger conditions** (when to consider Zeabur → Hetzner migration of GTFS Miner Pro):
- Phase A stable for ≥4 weeks (UptimeRobot >99.5%)
- compare-transit.fr public launched
- No emergency bug fixes pending on Pro tool
- Available time window of 2–3 days for migration + verification

---

*Phase A deployment plan complete. Run in parallel with Plan 1 — by end of W2 the site is up at compare-transit.fr with placeholder + working API.*
