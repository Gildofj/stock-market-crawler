# 🚀 Deployment Guide

This project is optimized for modern cloud environments, targeting **Render** for the API, **Supabase** (or Neon) for persistence, and **GitHub Actions** for automated crawling.

## ☁️ Production Environment (GCP Free Tier)

This project supports a 100% Free Tier deployment on Google Cloud Platform, separating the API from the Worker.

### 🏗️ Architecture
- **API (Cloud Run)**: Serverless FastAPI backend.
- **Worker (Compute Engine e2-micro)**: 24/7 Celery worker running on Container-Optimized OS (COS).
- **Broker (Self-hosted Redis)**: Sidecar container on the GCE VM.
- **Database (Supabase)**: External PostgreSQL.

### 🛠️ Infrastructure as Code (Terraform)

The `terraform/` directory contains the configuration to provision this setup.

1. **Prerequisites**:
   - Install [Terraform](https://developer.hashicorp.com/terraform/downloads).
   - Install [GCloud CLI](https://cloud.google.com/sdk/docs/install).
   - Create a GCP Project and enable billing (required for Cloud Run, even if within free tier).

2. **Initialize & Apply**:
   ```bash
   cd terraform
   terraform init
   
   # Create a terraform.tfvars file or pass variables via command line
   terraform apply \
     -var="project_id=YOUR_PROJECT_ID" \
     -var="image_name=gcr.io/YOUR_PROJECT_ID/stock-market-crawler" \
     -var="database_url=YOUR_SUPABASE_URL" \
     -var="redis_url=redis://:YOUR_PASSWORD@VM_PUBLIC_IP:6379/0" \
     -var="redis_password=YOUR_PASSWORD"
   ```

### 🔑 Required GitHub Secrets & Variables

**Secrets** (`Settings → Secrets and variables → Actions → Secrets`):

| Name | Description |
|---|---|
| `GCP_PROJECT_ID` | GCP project ID. |
| `GCP_SA_KEY` | Service Account JSON key. Required IAM roles below. |
| `DATABASE_URL` | Supabase Transaction Pooler URL (port **6543**). |
| `REDIS_URL` | Redis URL (`redis://:password@ip:6379/0`). |
| `REDIS_PASSWORD` | Password for the self-hosted Redis instance. |

**Variables** (`Settings → Secrets and variables → Actions → Variables` — non-sensitive):

| Name | Example |
|---|---|
| `GCP_REGION` | `us-central1` |
| `GCP_ZONE` | `us-central1-a` |
| `AR_REPO` | `crawler-images` (Artifact Registry repo) |
| `CLOUD_RUN_SERVICE` | `stock-market-api` |
| `WORKER_VM_NAME` | `crawler-worker-vm` |

**Required IAM roles on `GCP_SA_KEY`**:

| Role | Why |
|---|---|
| `roles/artifactregistry.writer` | Push images. |
| `roles/run.admin` | Deploy Cloud Run revisions. |
| `roles/iam.serviceAccountUser` | Act as the runtime SAs of Cloud Run / VM. |
| `roles/compute.instanceAdmin.v1` | Describe & modify the worker VM. |
| `roles/compute.osAdminLogin` | SSH as root into the VM (for `sudo apt` / `sudo docker`). |
| `roles/iap.tunnelResourceAccessor` | **Only if the VM has no external IP** — also append `--tunnel-through-iap` to every `gcloud compute ssh` call. |

The **VM's own service account** additionally needs `roles/artifactregistry.reader` so it can pull images at deploy time.

### 🔄 CI/CD Flow

The repo ships three production workflows under `.github/workflows/`:

| Workflow | Trigger | Purpose |
|---|---|---|
| `deploy.yml` | Push to `main` (excl. `**.md`, `docs/**`); `workflow_dispatch` | Build image, deploy API, roll worker. |
| `bootstrap-worker-vm.yml` | `workflow_dispatch` only | One-time VM setup (OS Login + Docker). |
| `migrations.yml` | Changes under `alembic/` or `crawler/models/` | Apply Alembic migrations against Supabase. |

#### `deploy.yml` — three sequential jobs

```
                build-and-push (Artifact Registry)
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
   deploy-api            deploy-worker
   (Cloud Run)           (Compute Engine VM via SSH)
```

1. **`build-and-push`** — Builds the Docker image on the GHA runner and pushes it to Artifact Registry. Tags both `:<sha>` and `:latest`. **Cloud Build is intentionally not used** (per-minute billing); never run `gcloud run deploy --source=...` or `gcloud builds submit`.
2. **`deploy-api`** — `gcloud run deploy` with the immutable `:<sha>` tag. Image-only deploy, no source upload.
3. **`deploy-worker`** — SSHes into `WORKER_VM_NAME`, mints a short-lived Artifact Registry access token, pulls the image, replaces the `celery-worker` container, and writes `/etc/celery-worker.env` (mode 600) from the `DATABASE_URL` / `REDIS_URL` secrets. Secrets are base64-encoded in transit so values with quotes/spaces survive the shell.

> **Why SSH and not `gcloud compute instances update-container`?** The worker runs on a plain Debian VM, not a Container-Optimized OS (COS) container-VM, so `update-container` errors out with *"Instance doesn't have gce-container-declaration metadata key"*. GCP has also deprecated the container-startup-agent path, so SSH + Docker is the recommended replacement.

#### `bootstrap-worker-vm.yml` — one-time VM setup

Run this **once** after creating the VM, before the first `deploy.yml` succeeds. Idempotent — safe to re-run after a teardown or partial failure. It:

1. Enables OS Login on the instance (`enable-oslogin=TRUE` metadata).
2. Installs `docker.io` from the distro repo if missing.
3. Enables the Docker daemon at boot.
4. Sanity-checks `docker pull hello-world`.

Trigger it from **Actions → Bootstrap Worker VM → Run workflow**.

#### How the worker stays in sync

- Container name is fixed at `celery-worker`. The deploy step always `docker rm -f`s it before `docker run`ing — first run is a no-op, subsequent runs replace the previous instance.
- `--restart unless-stopped` keeps the worker up across VM reboots.
- After each deploy a verify step tails `docker logs --tail 100` for the celery `ready.` / `celery@` markers and fails the job if neither appears within 10 s.
- `docker image prune -f` runs after every deploy so the e2-micro's 10 GB disk doesn't fill up with old image layers.

---

## ☁️ Legacy: Production Environment (Render + Supabase)

### 📄 render.yaml Configuration

The `render.yaml` (Blueprint) defines the infrastructure:
- **Service Type**: Web Service (Docker)
- **Health Check**: `/health`

### 🔑 Required Environment Variables

Set these on Render and as GitHub Actions secrets:

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ Yes | PostgreSQL connection string (Supabase transaction pooler — port **6543**). |
| `REDIS_URL` | ✅ Yes | Redis connection string (rate limiting + caching). |
| `ENV` | ✅ Yes | Set to `production` to enable strict CORS and the Cloudflare middleware. |
| `ALLOWED_ORIGINS` | ✅ in prod | Comma-separated list of allowed CORS origins. Required when `ENV=production`. Example: `https://app.example.com,https://admin.example.com`. |
| `LOG_LEVEL` | No | Defaults to `INFO`. |
| `DB_POOL_SIZE` | No | SQLAlchemy in-process pool size. Defaults to `2`. Keep small when many parallel workers share the same Supabase project. |
| `DB_MAX_OVERFLOW` | No | SQLAlchemy overflow connections. Defaults to `3`. |
| `YF_HISTORY_PERIOD` | No | yfinance history window (used by the daily-sync workflow). Defaults to `1mo`. |

### ⚠️ Supabase Free Tier — Pooler Mode Matters

Supabase free projects expose two poolers:

- **Session mode (port 5432)** — caps the whole project at **15 concurrent clients**. Easy to exhaust with parallel GHA chunks.
- **Transaction mode (port 6543)** — releases the connection after every transaction; supports hundreds of clients.

**Use port 6543** for both Render and GitHub Actions to avoid `EMAXCONNSESSION`. Copy it from *Supabase → Project Settings → Database → Connection string → Transaction*.

The crawler keeps a deliberately small in-process pool (`DB_POOL_SIZE=2`, `DB_MAX_OVERFLOW=3` by default) so 10 parallel chunks stay well within Supabase's global cap.

## 🛠️ Deployment Steps

### 1. Database Setup (Supabase)
1. Create a project on [Supabase](https://supabase.com/).
2. Copy the **transaction-mode** connection string (port `6543`) from *Project Settings → Database*.
3. Run migrations against the remote DB:
   ```bash
   DATABASE_URL="your-supabase-transaction-url" uv run alembic upgrade head
   ```

### 2. API Deployment (Render)
1. Connect your GitHub repository to [Render](https://render.com/).
2. Render auto-detects the `render.yaml` file.
3. Go to the **Environment** tab and add `DATABASE_URL`, `REDIS_URL`, and `ENV=production`.
4. Deploy. The `/health` endpoint is monitored by Render.

### 3. Automated Crawler (GitHub Actions)

The repo ships two workflows under `.github/workflows/`:

- **`daily-sync.yml`** — Scheduled daily run. Uses a `strategy.matrix` with 10 chunks; each chunk processes `len(tickers) / 10` symbols in parallel runners. The exact cron expression lives in the workflow file.
- **`migrations.yml`** — Manual/CI migration runner.

Setup:
1. Go to *Settings → Secrets and variables → Actions* in your GitHub repository.
2. Add the secrets above (`DATABASE_URL`, `REDIS_URL`, …).
3. The 10 parallel chunks will share the Supabase transaction pooler. If you need to throttle them, set `max-parallel` under `strategy:` in the workflow.

---

## 🏗️ Local Development (Docker Compose)

```bash
# Start all services (API, PostgreSQL, Redis, Grafana, Loki, Promtail)
docker-compose up -d

# Apply migrations
uv run alembic upgrade head

# Run crawler manually (full ticker set)
uv run python main.py

# Run a single shard (mimics one GHA chunk)
uv run python main.py --chunk 0 --total-chunks 10

# Run API in dev mode (with hot reload)
uv run uvicorn api.main:app --reload
```

### Local Service Ports

| Service | Port | URL |
|---|---|---|
| FastAPI API | 8000 | http://localhost:8000/docs |
| PostgreSQL | 5433 | — |
| Redis | 6379 | — |
| Grafana | 3001 | http://localhost:3001 |
| Loki | 3100 | — |

> PostgreSQL uses port **5433** (not 5432) to avoid conflicts with local PostgreSQL instances.

### Useful Make Targets

```bash
make install     # uv sync
make up          # docker-compose up -d
make down        # docker-compose down
make run-async   # run crawler (main.py)
make start       # build + up + run-async (full local cycle)
make test        # uv run pytest tests/ -v
make lint        # uv run ruff check .
make format      # uv run ruff format .
make clean       # remove caches (pytest, ruff, __pycache__)
make build       # docker-compose build
```
