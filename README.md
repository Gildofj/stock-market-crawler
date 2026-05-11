# 📈 Stock Market Crawler

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)

A high-performance stock market crawler and REST API for the Brazilian financial market (B3). Built with **FastAPI**, **GitHub Actions**, and **Clean Architecture**.

---

## ✨ Features

- **🚀 High Performance**: FastAPI + Uvicorn with Redis caching for sub-millisecond responses.
- **🕒 Parallel Crawling**: Multi-threaded engine (15 workers) running on GitHub Actions daily.
- **🔗 Enrichment Chain**: Multi-source resilience — B3/yfinance → Fundamentus → StatusInvest. Each source fills gaps left by the previous.
- **🛡️ Resilience**: Automatic retries, rate limiting, and stealth HTTP client (curl-cffi).
- **📊 Rich Data**:
  - Company metadata and B3 listings.
  - Financial fundamentals (P/E, DY, ROIC, EV/EBITDA, etc.).
  - Historical and current stock quotes.
  - Macro economic indicators.
- **📡 Observability**: Structured JSON logs (Loguru) with Grafana + Loki stack.
- **📝 Auto Documentation**: OpenAPI (Swagger) and ReDoc.

---

## 🛠️ Getting Started

### Prerequisites

- [Python 3.12+](https://www.python.org/downloads/)
- [Docker](https://www.docker.com/) & Docker Compose
- [uv](https://github.com/astral-sh/uv) (package manager)

### Local Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/gildofj/stock-market-crawler.git
   cd stock-market-crawler
   ```

2. **Environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your local credentials
   ```

3. **Install dependencies**:
   ```bash
   uv sync
   ```

4. **Start infrastructure**:
   ```bash
   docker-compose up -d
   ```

5. **Apply migrations**:
   ```bash
   uv run alembic upgrade head
   ```

6. **Run the crawler**:
   ```bash
   uv run python main.py
   ```

7. **Run the API**:
   ```bash
   uv run uvicorn api.main:app --reload
   ```

### API Documentation

Once running, access the interactive docs at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

## 🏗️ Project Structure

```text
├── api/              # FastAPI Application (Presentation Layer)
│   ├── routers/      # Endpoints: companies, prices, fundamentals
│   ├── schemas.py    # Pydantic response models
│   ├── deps.py       # Dependency injection
│   └── security.py   # CORS, GZip, Cloudflare middleware
├── crawler/          # Core Domain (Crawler + ETL)
│   ├── engine/       # CrawlerEngine: enrichment chain orchestration
│   ├── spiders/      # B3, Fundamentus, StatusInvest, Macro spiders
│   ├── services/     # ETL, CRUD, HTTP client, config
│   └── models/       # ORM models, Pydantic schemas, CrawlResult contract
├── alembic/          # Database migrations
├── grafana/          # Observability stack (Loki, Promtail, Grafana)
├── tests/            # Unit & Integration tests
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── docs/             # Technical documentation
├── Dockerfile        # Container image
├── docker-compose.yml # Local infrastructure
├── render.yaml       # Render deployment blueprint
└── Makefile          # Cross-platform build targets
```

---

## 📖 Documentation

- [🏗️ Architecture Overview](./docs/ARCHITECTURE.md) — Enrichment chain, data flow, tech stack.
- [🚀 Deployment Guide](./docs/DEPLOYMENT.md) — Render, Supabase, GitHub Actions, local Docker.

---

## 📄 License

MIT License — see [LICENSE](LICENSE).

Developed by **[Gildo FJ](https://gildofj.dev)**.
