#!/bin/bash
# Two Celery processes on one VM image:
#   * Split keeps a stuck News (lake) fetch from starving ticker crawls.
#   * Per-child memory ceiling (celery_app.py: 200 MB) recycles offenders.
#   * Single container because COS multi-container is poorly supported on GCE.
# `wait -n` exits as soon as either child dies, letting COS recycle the unit.
#
# Secrets are fetched from Google Secret Manager via the metadata server
# (curl-free: pure stdlib in scripts/fetch_secret.py). The VM SA gets
# roles/secretmanager.secretAccessor from terraform/secrets.tf.

set -euo pipefail

: "${GCP_PROJECT:?GCP_PROJECT env var is required to fetch secrets}"

fetch_secret() {
  python3 /app/scripts/fetch_secret.py "$1"
}

echo "[entrypoint] fetching secrets from Google Secret Manager (project=${GCP_PROJECT})..."
export DATABASE_URL="$(fetch_secret database-url)"
export REDIS_PASSWORD="$(fetch_secret redis-password)"
export R2_ACCOUNT_ID="$(fetch_secret r2-account-id)"
export R2_API_TOKEN="$(fetch_secret r2-api-token)"
PROXY_URL="$(fetch_secret webshare-proxy-url || true)"
if [ -n "$PROXY_URL" ]; then
  export CRAWLER_HTTP_PROXY="$PROXY_URL"
  export CRAWLER_HTTPS_PROXY="$PROXY_URL"
fi

if [ -z "${DATABASE_URL}" ] || [ -z "${REDIS_PASSWORD}" ]; then
  echo "[entrypoint] FATAL: required secrets are empty" >&2
  exit 1
fi

cleanup() {
  echo "[entrypoint] shutting down workers..."
  kill -TERM "${HOT_PID:-}" "${LAKE_PID:-}" 2>/dev/null || true
  redis-cli shutdown || true
  wait
}
trap cleanup EXIT INT TERM

echo "[entrypoint] starting redis-server..."
redis-server --requirepass "${REDIS_PASSWORD}" --bind 0.0.0.0 --daemonize yes

echo "[entrypoint] starting worker-hot (crawler,default,macro + beat)..."
celery -A crawler.celery_app worker \
  --beat \
  --loglevel=info \
  --concurrency=2 \
  -Q crawler,default,macro \
  -n "hot@%h" &
HOT_PID=$!

echo "[entrypoint] starting worker-lake (lake)..."
celery -A crawler.celery_app worker \
  --loglevel=info \
  --concurrency=1 \
  -Q lake \
  -n "lake@%h" &
LAKE_PID=$!

echo "[entrypoint] both workers up (hot=$HOT_PID, lake=$LAKE_PID); waiting..."
wait -n
