# Deployment Guide

This project runs entirely on the **GCP free tier**: a public Cloud Run API, an internal Cloud Run worker behind Cloud Tasks, a daily Cloud Run Job for RI crawling, and Supabase for persistence.

## Architecture

```
                   GitHub Actions (daily-sync.yml, cron 02:00 UTC)
                                    │
                                    ▼
                       Cloud Run API (stock-market-api)
                       Ingress: public via Cloudflare
                       Auth: X-API-Key header
                                    │
                                    ▼  (CloudTasksService.enqueue_task)
                       Cloud Tasks queue (crawler-queue)
                       rate: 10/s, max 5 retries, exponential backoff
                                    │
                                    ▼  (HTTP POST + OIDC)
                       Cloud Run Worker (stock-market-worker)
                       Ingress: internal only
                       Receives /_tasks/* endpoints

  Cloud Scheduler (07:00 BRT) ─▶ Cloud Run Job (lagoai-ri-crawl)
                                  Runs python -m crawler.tasks.lake_ri

  All workloads → Supabase PostgreSQL (transaction pooler, port 6543)
```

The API and the Worker run **the same container image**; only the Cloud Run service config differs (ingress + which env vars).

## Prerequisites

- A GCP project with billing enabled (required by Cloud Run; quota stays inside the free tier).
- [Terraform](https://developer.hashicorp.com/terraform/downloads) and [gcloud CLI](https://cloud.google.com/sdk/docs/install).
- A Supabase project (use the **transaction pooler** URL, port **6543**, to avoid exhausting the 15-connection session cap).
- An Artifact Registry repository for the container image.

## Infrastructure (Terraform)

The `terraform/` directory provisions everything:

- `cloud_run.tf` — public API service (`stock-market-api`).
- `cloud_run_worker.tf` — internal worker service (`stock-market-worker`).
- `cloud_run_job.tf` — RI crawler Job (`lagoai-ri-crawl`) + Cloud Scheduler trigger.
- `cloud_tasks.tf` — `crawler-queue` + IAM (enqueuer, invoker).
- `secrets.tf` — Secret Manager entries seeded from tfvars on first apply, then released (`ignore_changes = [secret_data]` so rotations happen via `gcloud secrets versions add`).
- `artifact_registry.tf`, `scheduler.tf`, `main.tf`, `variables.tf`, `outputs.tf`.

Apply:

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # fill in real values
terraform init
terraform apply
```

Required tfvars (see `terraform/variables.tf` for the full list):

| Variable | Notes |
|---|---|
| `project_id` | GCP project id |
| `image_name` | `<region>-docker.pkg.dev/<project>/<repo>/stock-market-crawler:latest` |
| `database_url` | Supabase transaction-pooler URL (port 6543) |
| `api_key` | Generate with `openssl rand -hex 32`. Must match the `API_KEY` GitHub secret |
| `r2_account_id`, `r2_api_token` | Cloudflare R2 credentials (optional; portfolios bucket only) |
| `webshare_proxy_url` | Proxy for crawler tier (optional) |
| `allowed_origins`, `scheduler_timezone` | CORS allowlist and Scheduler TZ |

## GitHub Actions

Three workflows under `.github/workflows/`:

| Workflow | Trigger | Purpose |
|---|---|---|
| `deploy.yml` | Push to `main` (excl. `**.md`, `docs/**`); `workflow_dispatch` | Build image, deploy api + worker + RI job in parallel after a quality gate (ruff + pyright + pytest) |
| `daily-sync.yml` | Cron `0 2 * * *` (UTC); `workflow_dispatch` | Resolves the API URL via `gcloud run services describe` and posts to `/_tasks/enqueue-daily` |
| `migrations.yml` | Changes under `alembic/**` or `crawler/models/**`; `workflow_dispatch` | Fetches `DATABASE_URL` from Secret Manager and runs `alembic upgrade head` |

### Required GitHub Secrets

| Name | Description |
|---|---|
| `GCP_PROJECT_ID` | Target GCP project |
| `GCP_SA_KEY` | Service Account JSON key (roles below) |

### Required GitHub Variables

| Name | Example |
|---|---|
| `GCP_REGION` | `us-central1` |
| `AR_REPO` | `crawler-images` |
| `CLOUD_RUN_SERVICE` | `stock-market-api` |

The Worker service name (`stock-market-worker`) and RI job name (`lagoai-ri-crawl`) are hard-coded in `deploy.yml` to match the Terraform resource names.

### Required IAM roles on `GCP_SA_KEY`

| Role | Purpose |
|---|---|
| `roles/artifactregistry.writer` | Push images |
| `roles/run.admin` | Deploy Cloud Run services and update Jobs |
| `roles/iam.serviceAccountUser` | Act as the runtime SAs of Cloud Run services and the RI Job |
| `roles/secretmanager.secretAccessor` | Read `database-url` (migrations) and `api-key` (daily-sync) |

### Deploy flow

```
  push to main
      │
      ▼
  quality  ──▶  build-and-push  ──┬──▶  deploy-api
                                  ├──▶  deploy-worker
                                  └──▶  deploy-ri-job (+ smoke execute)
```

All three deploy jobs run in parallel using the immutable `<sha>` image tag — no source upload, no Cloud Build (per-minute billing is intentionally avoided).

## Authentication boundaries

- **Public API** (`/api/v1/*`): `X-API-Key` header, validated by `api/security.py:require_api_key`. The same `API_KEY` is used by `daily-sync.yml` as a Bearer token when calling `/_tasks/enqueue-daily`.
- **Internal task endpoints** (`/_tasks/*`): accept either a Bearer token matching `API_KEY` or the presence of the `X-CloudTasks-QueueName` header (set automatically by Cloud Tasks). See `api/routers/tasks.py:_verify_task_auth`.
- **Cloud Run worker**: ingress is `INGRESS_TRAFFIC_INTERNAL_ONLY` + Cloud Tasks attaches an OIDC token. Direct internet access is blocked at the GCP edge.

## Operating

### Trigger work manually

```bash
API_URL=$(gcloud run services describe stock-market-api --region=us-central1 --format='value(status.url)')
API_KEY=$(gcloud secrets versions access latest --secret=api-key)

# Daily batch (macro + all tickers via Cloud Tasks)
curl -X POST -H "Authorization: Bearer $API_KEY" "$API_URL/_tasks/enqueue-daily"

# Single ticker (synchronous, on the worker)
WORKER_URL=$(gcloud run services describe stock-market-worker --region=us-central1 --format='value(status.url)')
gcloud auth print-identity-token --audiences="$WORKER_URL" | \
  xargs -I {} curl -X POST -H "Authorization: Bearer {}" "$WORKER_URL/_tasks/ticker/PETR4"
```

### Run the RI job ad-hoc

```bash
gcloud run jobs execute lagoai-ri-crawl --region=us-central1
```

### Rotate the API key

```bash
NEW_KEY=$(openssl rand -hex 32)
echo -n "$NEW_KEY" | gcloud secrets versions add api-key --data-file=-
# Re-deploy the API and worker to pick up the new revision.
```

### Rotate the database URL

```bash
echo -n "<new-url>" | gcloud secrets versions add database-url --data-file=-
```

Cloud Run services pick the new value on the next cold start; force a rollout with `gcloud run services update <name> --update-env-vars=ROLLOUT=$(date +%s)`.

## Local Development

See [docker-compose.yml](../docker-compose.yml) for the full local stack:

- `db` — Postgres 17 on `127.0.0.1:5433`
- `api` — FastAPI on `127.0.0.1:8000` (mirrors `stock-market-api`)
- `worker` — same image, internal only (mirrors `stock-market-worker`)
- `cloud-tasks-emulator` — `aertje/cloud-tasks-emulator` on `127.0.0.1:8123` (gRPC). The emulator delivers tasks with the same `X-CloudTasks-*` headers and retry semantics as the real service, so the api → emulator → worker path matches prod.
- `ri-job` — profile `jobs`, run on demand with `docker compose run --rm ri-job`.
- `grafana`, `loki`, `promtail`, `tempo` — observability stack.

```bash
make up
docker compose exec api uv run alembic upgrade head
curl http://localhost:8000/health
```

For request examples ready to import into Postman, see [docs/postman_collection.json](./postman_collection.json).

## Service ports (local)

| Service | Port | URL |
|---|---|---|
| FastAPI (api) | 8000 | http://localhost:8000/docs |
| PostgreSQL | 5433 | — |
| Grafana | 3001 | http://localhost:3001 |
| Loki | 3100 | — |
| Tempo (HTTP) | 3200 | — |
| Cloud Tasks emulator | 8123 | — |

PostgreSQL uses port **5433** to avoid conflicts with a local Postgres on 5432.
