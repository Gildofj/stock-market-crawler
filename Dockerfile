FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y redis-server && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock ./

# `observability` extra pulls the OpenTelemetry SDK + instrumentations needed
# for Cloud Trace export in production. Optional so local dev that only wants
# the API/crawler does not have to download the full OTel tree.
RUN uv sync --frozen --no-install-project --no-dev --extra observability

COPY . .

# COPY can drop the +x bit when the repo was checked out on Windows.
RUN chmod +x /app/scripts/worker_entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"

# Production default; docker-compose overrides to "human" for local dev.
ENV LOG_FORMAT=gcp

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
