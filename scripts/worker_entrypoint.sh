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

set -euo pipefail

cleanup() {
  echo "[entrypoint] shutting down workers..."
  kill -TERM "${HOT_PID:-}" "${LAKE_PID:-}" 2>/dev/null || true
  # Also stop redis
  redis-cli shutdown || true
  wait
}
trap cleanup EXIT INT TERM

echo "[entrypoint] starting redis-server..."
# Extract password from REDIS_URL: redis://:PASSWORD@localhost:6379/0
# This handle formats like redis://:pass@host:port/db
REDIS_PWD=$(echo "${REDIS_URL:-}" | sed -n 's/.*:\(.*\)@.*/\1/p')

if [ -n "$REDIS_PWD" ]; then
  echo "[entrypoint] redis starting with password protection"
  redis-server --requirepass "$REDIS_PWD" --bind 0.0.0.0 --daemonize yes
else
  echo "[entrypoint] redis starting without password (WARNING: local only recommended)"
  redis-server --bind 0.0.0.0 --daemonize yes
fi

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
