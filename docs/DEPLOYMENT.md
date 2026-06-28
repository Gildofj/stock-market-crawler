# Deployment Guide

This project is deployed on a self-hosted **Oracle VPS** (4 CPU cores, 24GB RAM) using Docker Compose (`docker-compose.prod.yml`) and **Supabase** for PostgreSQL persistence.

## Architecture

```
                  ┌──────────────────────────────────────────┐
                  │          Oracle VPS (Shared VM)          │
                  │                                          │
                  │   ┌───────────────┐  cron  ┌─────────┐   │
                  │   │   Scheduler   ├───────▶│   API   │   │
                  │   │   (Ofelia)    │        │(4 Wkrs) │   │
                  │   └───────────────┘        └────┬────┘   │
                  │                                 │        │
                  │   ┌───────────────┐        ┌────▼────┐   │
                  │   │  Tasks Queue  │◄───────┤ Worker  │   │
                  │   │  (Emulator)   ├───────▶│(4 Wkrs) │   │
                  │   └───────────────┘        └────┬────┘   │
                  │                                 │        │
                  │              ┌──────────────────┴──┐     │
                  │              ▼                     ▼     │
                  │        ┌──────────┐          ┌──────────┐│
                  │        │ Supabase │          │  Redis   ││
                  │        │ (Remote) │          │ (Caching)││
                  │        └──────────┘          └──────────┘│
                  └──────────────────────────────────────────┘
```

## GitHub Actions CI/CD

Three automated workflows are located under `.github/workflows/`:

| Workflow | Trigger | Purpose |
|---|---|---|
| `deploy.yml` | Push to `main` (excl. `**.md`, `docs/**`); `workflow_dispatch` | Runs quality gate (ruff check/format, pyright, pytest) then deploys to Oracle VPS via SSH (`docker-compose.prod.yml up -d --build`) |
| `daily-sync.yml` | Cron `0 2 * * *` (UTC); `workflow_dispatch` | Calls the `/_tasks/enqueue-daily` endpoint on the API as a secondary trigger/backup to Ofelia |
| `migrations.yml` | Changes under `alembic/**` or `crawler/models/**`; `workflow_dispatch` | Executes `alembic upgrade head` directly against Supabase |

### Required GitHub Secrets

| Name | Description | Example / Default |
|---|---|---|
| `VPS_HOST` | Hostname or IP address of the Oracle VPS | `152.67.x.x` |
| `VPS_USERNAME` | SSH login user | `ubuntu` or `opc` |
| `VPS_SSH_KEY` | Private SSH key authorized on the VPS | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `VPS_PORT` | (Optional) Custom SSH port | `22` |
| `VPS_PROJECT_PATH` | (Optional) Path where the repo lives on the VPS | `~/stock-market-crawler` |
| `DATABASE_URL` | Supabase connection URL for CI migrations | `postgresql://postgres.xxx:pass@aws-0-...pooler.supabase.com:6543/postgres` |
| `API_KEY` | Authentication key for triggering internal endpoints | `your-secure-api-key` |

### Required GitHub Variables (Optional)

| Name | Description | Example |
|---|---|---|
| `API_URL` | Public base URL of your API service | `https://api.yourdomain.com` |

### Deploy Flow

```
  push to main
      │
      ▼
   quality ──▶ deploy-vps (SSH -> git pull & docker compose up -d --build)
```

For detailed manual installation instructions on the VPS, see [VPS_DEPLOYMENT.md](./VPS_DEPLOYMENT.md).
