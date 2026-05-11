# 🚀 Deployment Guide

This project is optimized for modern cloud environments, specifically targeting **Render** with **Supabase** for persistence and **GitHub Actions** for automated crawling.

## ☁️ Production Environment (Render + Supabase)

The application is deployed as a Dockerized web service on Render, serving the FastAPI API.

### 📄 render.yaml Configuration

The `render.yaml` (Blueprint) defines the infrastructure:
- **Service Type**: Web Service (Docker)
- **Plan**: Free (No credit card required)
- **Health Check**: `/health`

### 🔑 Environment Variables

Required secrets on Render and GitHub Actions:
- `DATABASE_URL`: Connection string for your Supabase PostgreSQL.
- `REDIS_URL`: (Optional) Connection string for your Redis cache.
- `ENV`: Set to `production`.

## 🛠️ Deployment Steps

### 1. Database Setup (Supabase)
1.  Create a project on [Supabase](https://supabase.com/).
2.  Get your PostgreSQL connection string from *Project Settings > Database*.

### 2. API Deployment (Render)
1.  Connect your GitHub repository to [Render](https://render.com/).
2.  Render will automatically detect the `render.yaml` file.
3.  Go to the **Environment** tab in your Render service and add the `DATABASE_URL`.
4.  Deploy.

### 3. Automated Crawler (GitHub Actions)
1.  Go to your GitHub repository *Settings > Secrets and variables > Actions*.
2.  Add a secret named `DATABASE_URL` with your Supabase connection string.
3.  The workflow in `.github/workflows/daily-sync.yml` will now run daily at 02:00 UTC and populate your database.

---

## 🏗️ Local Deployment (Docker Compose)

For local development or self-hosting:

```bash
docker-compose up -d
```

This will spin up:
- **API**: Port 8080
- **Postgres**: Port 5432
- **Redis**: Port 6379
- **Loki/Promtail/Grafana**: For observability (Port 3000)
