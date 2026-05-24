# 🏗️ Architecture & Technical Overview

This project is built as an **agnostic backend service** following **Clean Architecture** principles. It is designed to be a high-performance data provider, decoupled from any specific frontend or consumer.

## 🏗️ System Architecture

The system is organized into three main layers:

1. **Crawler (Domain Layer)**: Async batch engine that handles data extraction, ETL, and persistence. Sharded across a 10-chunk GitHub Actions matrix that runs daily.
2. **API (Presentation Layer)**: FastAPI application serving as the entry point for consumers, with Redis caching and rate limiting.
3. **Infrastructure**: PostgreSQL (Supabase in production) for persistence, Redis for caching, Grafana stack for observability.

### 🧩 Layer Breakdown

```
crawler/
├── engine/
│   └── crawler_engine.py     # CrawlerEngine: enrichment chain, advanced metrics
│                             #   (Graham/Bazin valuation, Quality Score)
├── spiders/
│   ├── base_spider.py        # Abstract BaseSpider contract
│   ├── b3_spider.py          # B3/yfinance bulk prices + market cap
│   ├── cvm_spider.py         # Raw DFP/ITR statements -> universal indicators
│   │                         #   computed locally via financial_calculator
│   ├── macro_spider.py       # Macro indicators (SELIC, IPCA, USD, etc.)
│   ├── news_spider.py        # RSS news ingestion
│   └── ri_spider.py          # CVM RI filings (ITR/DFP/IPE/FRE)
├── services/
│   ├── request_manager.py    # Tiered HTTP client: curl_cffi + headless browser
│   │                         # Concurrency-capped browser semaphore for CI
│   ├── data_service.py       # CRUD (bulk insert, upsert on conflict)
│   ├── etl_service.py        # Validation, cleaning, transformation
│   ├── ticker_service.py     # Ticker registry / discovery
│   ├── reliability_service.py# Composite reliability score & grade
│   ├── reliability_config.py # Weights and thresholds for scoring
│   ├── logo_service.py       # Company logo URL resolution
│   ├── database.py           # Engine + sessionmaker (lazy, pool-tuned)
│   └── config.py             # Pydantic Settings (DATABASE_URL,
│                             #   DB_POOL_SIZE, DB_MAX_OVERFLOW, LOG_LEVEL)
├── models/
│   ├── models.py             # SQLAlchemy ORM: Company, StockPrice,
│   │                         #   Fundamental, CompanyReliability
│   ├── schemas.py            # Pydantic internal schemas
│   └── contract.py           # CrawlResult: unified container between spiders
├── tasks.py                  # Macro-data crawl task (runs once on chunk 0)
└── db/migrations/            # Legacy SQL bootstrap (Alembic is authoritative)

api/
├── routers/                  # companies, fundamentals, prices, reliability
├── schemas.py                # Pydantic response models (never expose ORM)
├── deps.py                   # Dependency injection: database sessions
├── limiter.py                # fastapi-limiter (Redis-backed)
└── security.py               # CORS, GZip, Cloudflare strict middleware

main.py                       # Entrypoint: argparses --chunk/--total-chunks,
                              #   runs asyncio.run(crawl_tickers_async(...))
```

## 🔄 Data Flow

```
GitHub Actions matrix [0..9] @ 02:00 UTC
        ↓
   main.py --chunk N --total-chunks 10
        ↓
   ticker_service.get_all_tickers() → slice for this chunk
        ↓
   crawl_tickers_async(tickers)
        ↓
   for sub_batch in chunks_of(tickers, 100):
        ↓
       B3Spider.crawl_batch_async(sub_batch)   ← one yfinance call for all
        ↓                                         tickers in the sub-batch
       data_service.get_existing_symbols(...)  ← single bulk lookup
        ↓
       asyncio.gather(
         safe_enrich_ticker(symbol)            ← Semaphore(15)
         for symbol in sub_batch
       )
            ↓
            [Enrichment Chain — clean-room only]
            CVMSpider.enrich_async()           ← Raw DFP/ITR statements from
                                                 CVM Dados Abertos. The
                                                 financial_calculator module
                                                 derives every universal
                                                 indicator (P/L, P/VP, ROE,
                                                 ROIC, EV/EBITDA, margins,
                                                 debt ratios) locally.
            ↓
            CrawlerEngine._calculate_advanced_metrics()
                                               ← Graham, Bazin, Quality Score
            ↓
            CrawlerEngine._save_to_db()        ← via Repositories
                                                 (bulk insert prices,
                                                  upsert company, save fundamentals)
        ↓
   PostgreSQL (Supabase in production)
        ↓
   FastAPI + fastapi-cache2 (Redis) → Consumer
```

### CrawlResult Contract

`crawler/models/contract.py` defines `CrawlResult` — the single data container passed between all spiders and services. Spiders never return raw dicts. This ensures the enrichment chain can safely merge partial results from multiple sources.

### Tiered HTTP Client (RequestManager)

`crawler/services/request_manager.py` exposes a two-tier strategy that every spider uses:

- **Tier 1 — `curl_cffi`**: Standard HTTP client with rotating User-Agents, realistic headers, jittered backoff, and exponential retries. Both sync and async sessions are pre-built. It natively bypasses proxy for trusted domestic domains (like CVM and B3) via `CRAWLER_PROXY_BYPASS_DOMAINS`.
- **Tier 2 — `nodriver` (headless browser)**: Triggered when Tier 1 returns a non-success status or fails the retry budget. Useful for pages that require JavaScript execution or full DOM rendering. This tier is only active in the dedicated `stealth` Docker image (`ENABLE_TIER2_STEALTH=true`) to keep the base API/worker image slim.
- **Concurrency guard**: A semaphore caps simultaneous browser launches to avoid OOM on small runners.

This layered approach improves resilience against transient errors and lets the crawler handle pages that the lightweight client cannot render.

### Reliability Scoring

`reliability_service.py` consumes persisted fundamentals and produces a composite reliability score and grade per company. The `CompanyReliability` table is independent from `Fundamental` so the scoring algorithm can evolve without touching collection. Weights live in `reliability_config.py`.

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 (strict typing) |
| Async runtime | `asyncio` |
| API Framework | FastAPI + Uvicorn (uvicorn[standard]) |
| ORM | SQLAlchemy 2.0 |
| Schemas | Pydantic V2 + pydantic-settings |
| Migrations | Alembic |
| Database | PostgreSQL 17 (production: Supabase via transaction pooler) |
| Caching | Redis + `fastapi-cache2` |
| Rate Limiting | `fastapi-limiter` + `pyrate-limiter` |
| HTTP Client (Tier 1) | `curl-cffi` |
| HTTP Client (Tier 2) | `nodriver` (headless browser) |
| Auxiliary HTTP | `httpx`, `requests` |
| HTML Parsing | BeautifulSoup4 + lxml |
| Financial Data | `yfinance`, `pandas` |
| Logging | Loguru |
| Observability | Grafana + Loki + Promtail |
| CI/CD | GitHub Actions (10-chunk matrix) |
| Deployment | Render (Docker) |
| Package Manager | uv |
| Linting | ruff |
| Type Checking | pyright |

## 🌐 Local Ports (docker-compose)

| Service | Port |
|---|---|
| FastAPI API | 8000 |
| PostgreSQL | 5433 (avoids conflict with local instances) |
| Redis | 6379 |
| Grafana | 3001 |
| Loki | 3100 |
