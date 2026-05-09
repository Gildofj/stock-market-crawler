# 🏗️ Architecture & Technical Overview

This project is built as an **agnostic backend service** following **Clean Architecture** principles. It is designed to be a high-performance data provider, decoupled from any specific frontend or consumer.

## 🏗️ System Architecture

The system is organized into three main layers to ensure that business logic remains independent of external frameworks and delivery mechanisms:

1.  **Crawler (The Engine/Domain)**: A Celery-based distributed system that handles data extraction and business rules.
2.  **API (The Delivery/Interface)**: A FastAPI application that serves as the entry point for consumers (Web, Mobile, or CLI).
3.  **Infrastructure (The Foundation)**: PostgreSQL for persistence and Redis for task queuing and caching.

### 🧩 Layer Breakdown

*   **`crawler/`**: The core of the application.
    *   `spiders/`: Implementation of data extraction from various sources.
    *   `services/`: Core business logic, data validation, and ETL orchestration.
    *   `models/`: Domain entities and schemas.
*   **`api/`**: The presentation layer.
    *   `routers/`: RESTful endpoints organized by resource.
    *   `security/`: Middleware for CORS, GZip, and infrastructure protection.
*   **`alembic/`**: Database schema evolution.

## 🔄 Data Flow

1.  **Trigger**: A scheduled task (APScheduler) or manual trigger adds a job to Redis.
2.  **Process**: A Celery Worker picks up the job and executes the corresponding Spider.
3.  **ETL**: Raw data is cleaned, validated by Pydantic, and transformed.
4.  **Storage**: The `DataService` persists the results into PostgreSQL.
5.  **Serve**: The API retrieves data, applying a Redis cache layer for sub-millisecond responses.

## 🛠️ Tech Stack

*   **Language**: Python 3.12 (Strict typing)
*   **Frameworks**: FastAPI, Celery
*   **Database**: PostgreSQL, Redis
*   **DevOps**: Docker, Fly.io, GitHub Actions
*   **Observability**: Loguru (JSON logs), Grafana, Loki
