# 🏗️ Architecture & Technical Overview

This project is built as an **agnostic backend service** following **Clean Architecture** principles. It is designed to be a high-performance data provider, decoupled from any specific frontend or consumer.

## 🏗️ System Architecture

The system is organized into three main layers to ensure that business logic remains independent of external frameworks and delivery mechanisms:

1.  **Crawler (The Engine/Domain)**: A multi-threaded parallel system running on GitHub Actions that handles data extraction and business rules.
2.  **API (The Delivery/Interface)**: A FastAPI application that serves as the entry point for consumers.
3.  **Infrastructure (The Foundation)**: PostgreSQL for persistence and Redis for API caching.

### 🧩 Layer Breakdown

*   **`crawler/`**: The core of the application.
    *   `spiders/`: Implementation of data extraction from various sources.
    *   `services/`: Core business logic, data validation, and ETL orchestration.
    *   `models/`: Domain entities and schemas.
*   **`api/`**: The presentation layer.
    *   `routers/`: RESTful endpoints organized by resource.
    *   `security/`: Middleware for CORS, GZip, and infrastructure protection.

## 🔄 Data Flow

1.  **Trigger**: A scheduled GitHub Action workflow starts the process daily.
2.  **Process**: The `main.py` script executes multiple parallel workers using a `ThreadPoolExecutor`.
3.  **ETL**: Raw data is cleaned, validated by Pydantic, and transformed.
4.  **Storage**: Results are persisted into PostgreSQL (e.g., Supabase or Neon).
5.  **Serve**: The API retrieves data, applying a Redis cache layer for sub-millisecond responses.

## 🛠️ Tech Stack

*   **Language**: Python 3.12 (Strict typing)
*   **Frameworks**: FastAPI
*   **Infrastructure**: GitHub Actions (Execution), PostgreSQL, Redis
*   **DevOps**: Docker, Render, GitHub Actions
*   **Observability**: Loguru (JSON logs), Grafana, Loki
