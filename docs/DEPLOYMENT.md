# 🚀 Deployment & DevOps Guide

This project is optimized for modern cloud environments, specifically targeting **Fly.io** with **GitHub Actions** for CI/CD.

## ☁️ Production Environment (Fly.io)

The application is deployed as a single-process App on Fly.io, managing the FastAPI API.

### 📄 fly.toml Configuration

The `fly.toml` defines one process group:
- **web**: Runs the FastAPI application using Uvicorn.

### 🔑 Secret Management

Required secrets on Fly.io:
- `DATABASE_URL`: PostgreSQL connection string.
- `REDIS_URL`: Redis connection string (Internal or Upstash).
- `ENV`: Set to `production`.

## 🔄 CI/CD Pipeline

The project uses GitHub Actions (see `.github/workflows/`):

1.  **Daily Sync**: A scheduled workflow that runs the crawler parallel script natively on GitHub compute resources.
2.  **Fly Deploy**: Automatically deploys the FastAPI application on pushes to the `main` branch.

## 🐳 Dockerization

The `Dockerfile` uses `uv` for ultra-fast dependency resolution and multi-stage builds to keep the image slim.

- **Base Image**: `python:3.12-slim-bookworm`
- **Dependency Manager**: `uv` (pip compatible but faster)
- **Compile Bytecode**: Enabled for faster startup.

## 📊 Observability

Logs are emitted in JSON format via `loguru` and are intended to be consumed by:
- **Promtail**: Scrapes logs from Docker containers.
- **Loki**: Aggregates logs.
- **Grafana**: Visualizes system health and crawler performance.
