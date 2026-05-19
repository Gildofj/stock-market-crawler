#!/bin/bash
# Worker entrypoint: starts two Celery processes on the same VM image.
#
# Why two processes (instead of one --beat with all queues):
#   * Hot path (crawler/default/macro) shouldn't share a worker process with the
#     lake path (RSS parsing), so a stuck News fetch can't starve ticker crawls.
#   * Memory ceilings are enforced per-child (see celery_app.py: 200 MB), so a
#     misbehaving lake task recycles only its own worker without touching hot.
#
# Why one container (instead of two via docker-compose):
#   * GCE Container-Optimized OS reliably runs a single container per VM via
#     gce-container-declaration. Multi-container on COS exists but is poorly
#     documented and not worth the operational cost for a 2-process split.
#   * If either Celery dies, `wait -n` returns and the script exits, which makes
#     COS recycle the whole container (restartPolicy: Always).
#
# Secrets:
#   * DATABASE_URL, REDIS_PASSWORD, R2_ACCOUNT_ID, R2_API_TOKEN are fetched from
#     Google Secret Manager via the metadata server (no gcloud SDK needed on
#     the runtime image — curl + python3 only). The VM's service account
#     (crawler-worker-sa) has roles/secretmanager.secretAccessor wired in
#     terraform/secrets.tf.

set -euo pipefail

: "${GCP_PROJECT:?GCP_PROJECT env var is required to fetch secrets}"

# Wrapper around scripts/fetch_secret.py (pure stdlib — no curl needed).
fetch_secret() {
  python3 /app/scripts/fetch_secret.py "$1"
}

echo "[entrypoint] fetching secrets from Google Secret Manager (project=${GCP_PROJECT})..."
export DATABASE_URL="$(fetch_secret database-url)"
export REDIS_PASSWORD="$(fetch_secret redis-password)"
export R2_ACCOUNT_ID="$(fetch_secret r2-account-id)"
export R2_API_TOKEN="$(fetch_secret r2-api-token)"

if [ -z "${DATABASE_URL}" ] || [ -z "${REDIS_PASSWORD}" ]; then
  echo "[entrypoint] FATAL: required secrets are empty" >&2
  exit 1
fi

cleanup() {
  echo "[entrypoint] shutting down workers..."
  kill -TERM "${HOT_PID:-}" "${LAKE_PID:-}" 2>/dev/null || true
  # Also stop redis
  redis-cli shutdown || true
  wait
}
trap cleanup EXIT INT TERM

echo "[entrypoint] starting redis-server with password protection..."
redis-server --requirepass "${REDIS_PASSWORD}" --bind 0.0.0.0 --daemonize yes

echo "[entrypoint] starting worker-hot (queues: crawler,default,macro, with beat)..."
celery -A crawler.celery_app worker \
  --beat \
  --loglevel=info \
  --concurrency=2 \
  -Q crawler,default,macro \
  -n "hot@%h" &
HOT_PID=$!

echo "[entrypoint] starting worker-lake (queues: lake)..."
celery -A crawler.celery_app worker \
  --loglevel=info \
  --concurrency=1 \
  -Q lake \
  -n "lake@%h" &
LAKE_PID=$!

echo "[entrypoint] both workers up (hot=$HOT_PID, lake=$LAKE_PID); waiting..."
# Exit as soon as either child exits so COS restarts the container as a unit.
wait -n
