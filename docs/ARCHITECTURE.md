# 🏗️ Architecture & Technical Overview

This project is built as an **agnostic backend service** following **Clean Architecture** principles. It is designed to be a high-performance data provider, decoupled from any specific frontend or consumer.

## 🏗️ System Architecture

The system is organized into three main layers:

1. **Crawler (Domain Layer)**: Multi-threaded parallel engine that handles data extraction, ETL, and persistence. Runs on GitHub Actions daily.
2. **API (Presentation Layer)**: FastAPI application serving as the entry point for consumers, with Redis caching.
3. **Infrastructure**: PostgreSQL for persistence, Redis for caching, Grafana stack for observability.

### 🧩 Layer Breakdown

```
crawler/
├── engine/           # Orchestration: CrawlerEngine, enrichment chain
├── spiders/          # Data extraction: BaseSpider + B3, Fundamentus, StatusInvest, Macro
├── services/
│   ├── data_service.py    # CRUD operations (SQLAlchemy sessions)
│   ├── etl_service.py     # Data validation, cleaning, transformation
│   ├── request_manager.py # HTTP client with rate limiting and retries
│   ├── ticker_service.py  # Ticker registry management
│   ├── logo_service.py    # Company logo URL resolution
│   └── config.py          # Pydantic Settings (DATABASE_URL, REDIS_URL, LOG_LEVEL)
├── models/
│   ├── models.py     # SQLAlchemy ORM: Company, StockPrice, Fundamental
│   ├── schemas.py    # Pydantic internal schemas
│   └── contract.py   # CrawlResult: unified data container between spiders

api/
├── routers/          # RESTful endpoints: companies, prices, fundamentals
├── schemas.py        # Pydantic response models (never expose ORM models directly)
├── deps.py           # Dependency injection: database sessions
├── limiter.py        # Rate limiting configuration
└── security.py       # Middleware: CORS, GZip, Cloudflare
```

## 🔄 Data Flow

```
GitHub Actions (02:00 UTC)
        ↓
    main.py (ThreadPoolExecutor, 15 workers, 5 concurrent API calls)
        ↓
  CrawlerEngine.run(ticker)
        ↓
  [Enrichment Chain]
  B3Spider.get_items(ticker)          ← Primary source (yfinance)
        ↓ (fills missing fields)
  FundamentusSpider.get_items(ticker) ← Fallback #1
        ↓ (fills remaining None fields)
  StatusInvestSpider.get_items(ticker)← Fallback #2
        ↓
  CrawlResult (unified contract)
        ↓
  ETLService.validate_and_clean()
        ↓
  DataService.save() → PostgreSQL
        ↓
  API → Redis Cache → Consumer
```

### CrawlResult Contract

`crawler/models/contract.py` defines `CrawlResult` — the single data container passed between all spiders and services. Spiders never return raw dicts. This ensures the enrichment chain can safely merge partial results from multiple sources.

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 (strict typing) |
| API Framework | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 |
| Schemas | Pydantic V2 |
| Migrations | Alembic |
| Database | PostgreSQL (production: Supabase/Neon) |
| Caching | Redis + fastapi-cache2 |
| HTTP Client | httpx, curl-cffi (stealth mode) |
| HTML Parsing | BeautifulSoup4 + lxml |
| Financial Data | yfinance, pandas |
| Logging | Loguru (JSON output) |
| Observability | Grafana + Loki + Promtail |
| CI/CD | GitHub Actions |
| Deployment | Render (Docker) |
| Package Manager | uv |
| Linting | ruff |

## 🌐 Local Ports (docker-compose)

| Service | Port |
|---|---|
| FastAPI API | 8000 |
| PostgreSQL | 5433 (avoids conflict with local instances) |
| Redis | 6379 |
| Grafana | 3001 |
| Loki | 3100 |
