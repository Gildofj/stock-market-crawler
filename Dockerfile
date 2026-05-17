# Use a slim Python image
FROM python:3.12-slim-bookworm

# Install uv directly from the official GitHub Container Registry
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy only the files needed for dependency installation to maximize Docker cache
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
# --frozen ensures we use the exact versions from uv.lock
RUN uv sync --frozen --no-install-project --no-dev

# Copy the rest of the application code
COPY . .

# Ensure the worker entrypoint script is executable on Linux even if the
# repo was checked out on Windows (where COPY can lose the +x bit).
RUN chmod +x /app/scripts/worker_entrypoint.sh

# Place executables in the path
ENV PATH="/app/.venv/bin:$PATH"

# Default command (serves the API)
# Use 0.0.0.0 and PORT env var for Render compatibility
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
