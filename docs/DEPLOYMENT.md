# 🚀 Deployment Guide

This project is optimized for modern cloud environments, targeting **Render** for the API, **Supabase/Neon** for persistence, and **GitHub Actions** for automated crawling.

## ☁️ Production Environment (Render + Supabase)

### 📄 render.yaml Configuration

The `render.yaml` (Blueprint) defines the infrastructure:
- **Service Type**: Web Service (Docker)
- **Health Check**: `/health`

### 🔑 Required Environment Variables

Set these on Render and as GitHub Actions secrets:

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ Yes | PostgreSQL connection string (Supabase/Neon) |
| `REDIS_URL` | ✅ Yes | Redis connection string (rate limiting + caching) |
| `ENV` | ✅ Yes | Set to `production` |
| `LOG_LEVEL` | No | Defaults to `INFO` |

## 🛠️ Deployment Steps

### 1. Database Setup (Supabase)
1. Create a project on [Supabase](https://supabase.com/).
2. Get your PostgreSQL connection string from *Project Settings > Database*.
3. Run migrations against the remote DB:
   ```bash
   DATABASE_URL="your-supabase-url" uv run alembic upgrade head
   ```

### 2. API Deployment (Render)
1. Connect your GitHub repository to [Render](https://render.com/).
2. Render will automatically detect the `render.yaml` file.
3. Go to the **Environment** tab and add `DATABASE_URL`, `REDIS_URL`, and `ENV=production`.
4. Deploy. The `/health` endpoint will be monitored by Render.

### 3. Automated Crawler (GitHub Actions)
1. Go to *Settings > Secrets and variables > Actions* in your GitHub repository.
2. Add secrets: `DATABASE_URL` and `REDIS_URL`.
3. The workflow `.github/workflows/daily-sync.yml` runs daily at **02:00 UTC** and populates your database.

---

## 🏗️ Local Development (Docker Compose)

```bash
# Start all services (API, PostgreSQL, Redis, Grafana)
docker-compose up -d

# Apply migrations
uv run alembic upgrade head

# Run crawler manually
uv run python main.py

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

> PostgreSQL uses port **5433** (not 5432) to avoid conflicts with local PostgreSQL instances.

### Useful Make Targets

```bash
make install     # uv sync
make up          # docker-compose up -d
make down        # docker-compose down
make run-async   # run crawler
make test        # uv run pytest
make lint        # uv run ruff check .
make format      # uv run ruff format .
```
