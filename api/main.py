import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_limiter import FastAPILimiter
import redis.asyncio as redis
from loguru import logger

from .routers import companies, fundamentals, prices
from .security import CloudflareMiddleware

app = FastAPI(
    title="Stock Market Crawler API",
    description="API de alta performance para servir dados do mercado financeiro brasileiro.",
    version="1.0.0",
    docs_url="/api/docs" if os.getenv("ENV") != "production" else None,
    redoc_url=None
)

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

# 4. Inicialização de Cache e Rate Limiting
@app.on_event("startup")
async def startup():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.from_url(redis_url, encoding="utf8", decode_responses=True)
        
        # Inicializa Cache
        FastAPICache.init(RedisBackend(r), prefix="stock-api-cache")
        
        # Inicializa Rate Limiter
        await FastAPILimiter.init(r)
        
        logger.info("API initialized with Redis Cache and Rate Limiting.")
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}")

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
