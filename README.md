# 📈 Stock Market Crawler

[![CI/CD](https://github.com/gildofj/stock-market-crawler/actions/workflows/fly-deploy.yml/badge.svg)](https://github.com/gildofj/stock-market-crawler/actions/workflows/fly-deploy.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)

A high-performance, agnostic stock market crawler and API for the Brazilian financial market (B3). Built with **FastAPI**, **Celery**, and **Clean Architecture**.

---

## ✨ Features

- **🚀 High Performance**: FastAPI with Uvicorn and Redis-based caching.
- **🕒 Distributed Crawling**: Scalable worker system using Celery for efficient data scraping.
- **🛡️ Resilience**: Automatic retries, rate limiting, and request management to handle external API limits.
- **📊 Rich Data**:
    - Company metadata and listings.
    - Financial fundamentals (P/E, DY, ROIC, etc.).
    - Historical and current stock quotes.
- **📝 Automatic Documentation**: OpenAPI (Swagger) and ReDoc support.

---

## 🛠️ Getting Started

### Prerequisites

- [Python 3.12+](https://www.python.org/downloads/)
- [Docker](https://www.docker.com/) & Docker Compose
- [uv](https://github.com/astral-sh/uv) (Highly recommended for dependency management)

### Local Setup

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/gildofj/stock-market-crawler.git
    cd stock-market-crawler
    ```

2.  **Environment Variables**:
    ```bash
    cp .env.example .env
    # Edit .env with your local credentials
    ```

3.  **Install dependencies**:
    ```bash
    uv sync
    ```

4.  **Run with Docker Compose**:
    ```bash
    docker-compose up -d
    ```

---

## 📖 Documentation

Detailed technical documentation can be found in the `docs/` folder:

- [🏗️ Architecture Overview](./docs/ARCHITECTURE.md) - Deep dive into patterns and data flow.
- [🚀 Deployment Guide](./docs/DEPLOYMENT.md) - Instructions for Fly.io and DevOps.

### API Endpoints (Interactive)

Once running, access the documentation at:
- **Swagger UI**: `http://localhost:8080/docs`
- **ReDoc**: `http://localhost:8080/redoc`

---

## 🏗️ Project Structure

```text
├── api/              # FastAPI Application (Web Layer)
├── crawler/          # Core Domain & Workers (Scraping Layer)
├── alembic/          # Database Migrations
├── docs/             # Technical Documentation
├── tests/            # Unit & Integration Tests
├── Dockerfile        # Container Configuration
└── fly.toml          # Fly.io Deployment Config
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Developed by **[Gildo FJ](https://gildofj.dev)**.
