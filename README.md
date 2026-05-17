# 📈 Stock Market Crawler

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Code of Conduct](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](./CODE_OF_CONDUCT.md)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](./CONTRIBUTING.md)

A high-performance stock market crawler and REST API for the Brazilian financial market (B3). Built with **FastAPI**, **asyncio**, **GitHub Actions**, and **Clean Architecture**.

> :warning: **Operator-responsibility tool.** Compliance with the Terms of Service and `robots.txt` of target sites (B3, CVM Dados Abertos, Yahoo Finance) is the operator's responsibility. The fundamentals pipeline reads raw CVM open-data statements and computes every indicator locally — no proprietary aggregator is touched. Released under the [MIT License](./LICENSE) — see [`DISCLAIMER.md`](./DISCLAIMER.md) for the per-source legal status and the takedown channel before deploying commercially.

---

## ✨ Features

- **🚀 High Performance**: FastAPI + Uvicorn with Redis caching for sub-millisecond responses.
- **⚡ Async Batch Crawling**: `asyncio` engine with sub-batches of 100 tickers, parallel enrichment (`Semaphore(15)`), and yfinance bulk price fetching — runs daily on a 10-chunk GitHub Actions matrix.
- **🔗 Clean-room Enrichment Chain**: B3/yfinance for prices (facts — Lei 9.610/98 Art. 8º), then `CVMSpider` reads raw DFP/ITR statements from CVM Dados Abertos and the in-process `financial_calculator` derives every universal indicator (P/L, P/VP, ROE, ROIC, EV/EBITDA, margins, Graham, Bazin) using public-domain formulas.
- **🌐 Tiered HTTP Client**: Tier-1 `curl_cffi` with rotating User-Agents and realistic headers; Tier-2 fallback to a headless browser (`nodriver`) for JS-heavy pages.
- **🏅 Reliability Scoring**: `ReliabilityService` computes a composite company reliability score and grade, queryable via API.
- **📊 Rich Data**:
  - Company metadata and B3 listings.
  - Financial fundamentals (P/L, DY, ROE, ROIC, EV/EBITDA, EPS, etc.).
  - Valuation metrics (Graham, Bazin) and Quality Score.
  - Historical and current stock quotes.
  - Macro economic indicators.
- **📡 Observability**: Structured logs (Loguru) shipped to Grafana + Loki + Promtail.
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
   # Or use a specific shard (used in GHA):
   uv run python main.py --chunk 0 --total-chunks 10
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
├── api/                       # FastAPI Application (Presentation Layer)
│   ├── routers/               # companies, fundamentals, prices, reliability
│   ├── schemas.py             # Pydantic response models
│   ├── deps.py                # Dependency injection
│   ├── limiter.py             # fastapi-limiter setup
│   └── security.py            # CORS, GZip, Cloudflare strict middleware
├── crawler/                   # Core Domain (Crawler + ETL)
│   ├── engine/
│   │   └── crawler_engine.py  # Enrichment chain orchestration + advanced metrics
│   ├── spiders/               # base_spider, b3_spider (prices),
│   │                          # cvm_spider (raw DFP/ITR fundamentals),
│   │                          # macro_spider, news_spider, ri_spider
│   ├── services/
│   │   ├── request_manager.py # Tier-1 curl_cffi + Tier-2 nodriver stealth
│   │   ├── data_service.py    # CRUD (SQLAlchemy)
│   │   ├── etl_service.py     # Validation, cleaning, transformation
│   │   ├── ticker_service.py  # Ticker registry
│   │   ├── reliability_service.py / reliability_config.py
│   │   ├── logo_service.py    # Company logo URL resolution
│   │   ├── database.py        # Engine factory + pool sizing
│   │   └── config.py          # Pydantic Settings
│   ├── models/                # ORM models, Pydantic schemas, CrawlResult
│   ├── db/migrations/         # Legacy SQL migration (kept for reference)
│   └── tasks.py               # Macro-data crawl tasks (run once per shard)
├── alembic/                   # Database migrations (autogenerate-compatible)
├── grafana/                   # Loki + Promtail + Grafana provisioning
├── tests/
│   ├── unit/                  # Spider, engine, service tests
│   ├── integration/           # End-to-end DB flow
│   └── conftest.py
├── docs/                      # Technical documentation
├── .github/workflows/         # deploy.yml, bootstrap-worker-vm.yml,
│                              # daily-sync.yml, migrations.yml
├── main.py                    # Crawler entrypoint (--chunk / --total-chunks)
├── Dockerfile
├── docker-compose.yml
├── render.yaml                # Render Blueprint
└── Makefile                   # Cross-platform build targets
```

---

## 📖 Documentation

- [🏗️ Architecture Overview](./docs/ARCHITECTURE.md) — Enrichment chain, async data flow, stealth HTTP tiers, reliability scoring.
- [🚀 Deployment Guide](./docs/DEPLOYMENT.md) — Render, Supabase (transaction-mode pooler), GitHub Actions matrix, local Docker.

---

## 🤝 Contributing

Contributions are welcome! Please read:

- [CONTRIBUTING.md](./CONTRIBUTING.md) — workflow, commit convention, code standards, PR process.
- [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) — Contributor Covenant 2.1 + Ethical Use section.
- [SECURITY.md](./SECURITY.md) — how to report vulnerabilities privately.
- [CHANGELOG.md](./CHANGELOG.md) — release history (Keep a Changelog + SemVer).

---

## 📄 License

MIT License — see [LICENSE](LICENSE).

Developed by **[gildofj.dev](https://gildofj.dev)**.
