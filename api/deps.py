import os
from collections.abc import Generator

import redis.asyncio as redis

from crawler.services.database import session_local


def get_db() -> Generator:
    """
    Injeção de dependência para sessões do banco de dados SQLAlchemy.
    Garante que a conexão seja fechada após a requisição.
    """
    db = session_local()
    try:
        yield db
    finally:
        db.close()

async def get_redis():
    """
    Conexão assíncrona com o Redis para cache e rate limiting.
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    pool = redis.ConnectionPool.from_url(redis_url, encoding="utf8", decode_responses=True)
    return redis.Redis(connection_pool=pool)
