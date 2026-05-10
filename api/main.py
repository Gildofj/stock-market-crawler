import os
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from loguru import logger

from .routers import companies, fundamentals, prices
from .security import CloudflareMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Inicialização de Cache
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.from_url(redis_url, encoding="utf8", decode_responses=True)
        FastAPICache.init(RedisBackend(r), prefix="stock-api-cache")
        logger.info("API initialized with Redis Cache.")
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}")
    yield

app = FastAPI(
    title="Stock Market Crawler API",
    description="""
    High-performance API for serving Brazilian financial market data.

    ## Features
    * **Companies**: List and details of companies listed on B3.
    * **Fundamentals**: Updated financial fundamentals and indicators.
    * **Prices**: Historical and real-time stock quotes.

    ---
    Developed by Gildo FJ.
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "Gildo FJ",
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
]
app.openapi_tags = tags_metadata

# 1. Configuração de Segurança - CORS
if os.getenv("ENV") == "production":
    origins = [
        "https://your-frontend.example.com",
        "http://localhost:3000",
    ]
    allow_origins = origins
else:
    allow_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# 2. Performance - Compressão GZip
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 3. Configuração de Segurança - Cloudflare Strict
# Garante que ninguém acesse a URL da Fly diretamente
if os.getenv("ENV") == "production":
    app.add_middleware(CloudflareMiddleware)

# 4. Registro de Rotas
app.include_router(companies.router, prefix="/api/v1")
app.include_router(fundamentals.router, prefix="/api/v1")
app.include_router(prices.router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {"message": "Stock Market Crawler API is running. Access via Cloudflare Proxy only."}
