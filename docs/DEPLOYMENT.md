# 🚀 Deployment Guide

This project is optimized for modern cloud environments, targeting **Render** for the API, **Supabase** (or Neon) for persistence, and **GitHub Actions** for automated crawling.

## ☁️ Production Environment (GCP Free Tier)

This project supports a 100% Free Tier deployment on Google Cloud Platform, separating the API from the Worker.

### 🏗️ Architecture
- **API (Cloud Run)**: Serverless FastAPI backend.
- **Worker (Compute Engine e2-micro)**: 24/7 Celery worker running on a free-tier eligible VM in `us-central1`.
- **Broker (Upstash Redis)**: External Redis for Celery tasks.
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
     -var="redis_url=YOUR_UPSTASH_URL"
   ```

### 🔑 Required GitHub Secrets

| Variable | Description |
|---|---|
| `DATABASE_URL` | Supabase Transaction Pooler URL (Port 6543). |
| `REDIS_URL` | Upstash Redis URL (Broker for Celery). |
| `GCP_PROJECT_ID` | Your GCP Project ID. |
| `GCP_SA_KEY` | (Optional) Service Account Key for automated TF/Docker push. |

### 🔄 CI/CD Flow
The **`daily-sync.yml`** workflow now acts as an **Enqueuer**. It connects to Redis and pushes task messages. The GCP VM Worker, which is always running, picks these up and executes the crawling logic.

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
