import os
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from loguru import logger

from .limiter import close_rate_limiter, init_rate_limiter
from .routers import companies, fundamentals, lake, portfolio, prices, reliability, sources
from .security import CloudflareMiddleware, require_api_key

if not os.getenv("API_KEY"):
    raise RuntimeError(
        "API_KEY env var must be set. The API requires authentication on every request."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.from_url(redis_url, encoding="utf8", decode_responses=True)
        FastAPICache.init(RedisBackend(r), prefix="stock-api-cache")
        logger.info("API initialized with Redis Cache.")
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}")

    await init_rate_limiter()
    yield
    await close_rate_limiter()


app = FastAPI(
    title="Stock Market Crawler API",
    description="""
    High-performance API for serving Brazilian financial market data.

    ## Features
    * **Companies**: List and details of companies listed on B3.
    * **Fundamentals**: Updated financial fundamentals and indicators.
    * **Prices**: Historical and real-time stock quotes.

    ---
    Developed by gildofj.dev.
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "gildofj.dev",
        "url": "https://gildofj.dev",
    },
    license_info={
        "name": "MIT",
    },
)

# OpenAPI Tags Configuration
tags_metadata = [
    {
        "name": "Companies",
        "description": "Operations with listed companies and assets.",
    },
    {
        "name": "Fundamentals",
        "description": "Fundamentalist and financial data.",
    },
    {
        "name": "Prices",
        "description": "Stock quotes and market data.",
    },
    {
        "name": "Reliability",
        "description": "Company reliability rankings and scores.",
    },
    {
        "name": "Data Lake",
        "description": "Premium data lake (news, RI documents, AI insights).",
    },
    {
        "name": "Portfolio",
        "description": "Premium portfolio management and enrichment.",
    },
    {
        "name": "Transparency",
        "description": "Public, unauthenticated metadata about the deployment "
        "(data sources, attribution, takedown signals).",
    },
]
app.openapi_tags = tags_metadata

# 1. Configuração de Segurança - CORS
if os.getenv("ENV") == "production":
    raw_origins = os.getenv("ALLOWED_ORIGINS", "")
    allow_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    if not allow_origins:
        raise RuntimeError(
            "ALLOWED_ORIGINS must be set to a non-empty comma-separated list "
            "when ENV=production."
        )
    allow_credentials = True
else:
    allow_origins = ["*"]
    allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# 2. Performance - Compressão GZip
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 3. Configuração de Segurança - Cloudflare Strict
# Garante que ninguém acesse a URL do Render diretamente
if os.getenv("ENV") == "production":
    app.add_middleware(CloudflareMiddleware)

# 4. Registro de Rotas
api_dependencies = [Depends(require_api_key)]
app.include_router(companies.router, prefix="/api/v1", dependencies=api_dependencies)
app.include_router(fundamentals.router, prefix="/api/v1", dependencies=api_dependencies)
app.include_router(prices.router, prefix="/api/v1", dependencies=api_dependencies)
app.include_router(reliability.router, prefix="/api/v1", dependencies=api_dependencies)
app.include_router(lake.router, prefix="/api/v1", dependencies=api_dependencies)
app.include_router(portfolio.router, prefix="/api/v1", dependencies=api_dependencies)

# Transparency endpoint — intentionally public (no api_key, no premium gate).
# Anyone can audit which sources are active in this deployment.
app.include_router(sources.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return {"message": "Stock Market Crawler API is running. Access via Cloudflare Proxy only."}
