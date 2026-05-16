import os

from fastapi import Request, Response
from fastapi_limiter.depends import RateLimiter
from loguru import logger
from pyrate_limiter import Duration, InMemoryBucket, Limiter, Rate, RedisBucket
from redis.asyncio import from_url

_default_rates = [Rate(60, Duration.MINUTE)]
_strict_rates = [Rate(10, Duration.MINUTE)]

_default_limiter: Limiter | None = None
_strict_limiter: Limiter | None = None


async def init_rate_limiter() -> None:
    global _default_limiter, _strict_limiter

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        connection = from_url(redis_url, encoding="utf8", decode_responses=True)
        # RedisBucket.init is an async classmethod at runtime but its type
        # stub is marked synchronous in current pyrate-limiter versions.
        default_bucket = await RedisBucket.init(  # type: ignore[misc]
            _default_rates, connection, "rl:default"
        )
        strict_bucket = await RedisBucket.init(  # type: ignore[misc]
            _strict_rates, connection, "rl:strict"
        )
        _default_limiter = Limiter(default_bucket)
        _strict_limiter = Limiter(strict_bucket)
        logger.info("Rate limiter initialized (Redis backend).")
    except Exception as e:
        logger.warning(f"Falling back to in-memory rate limiter ({e}).")
        _default_limiter = Limiter(InMemoryBucket(_default_rates))
        _strict_limiter = Limiter(InMemoryBucket(_strict_rates))


async def close_rate_limiter() -> None:
    return None


async def _client_identifier(request: Request) -> str:
    return request.headers.get("cf-connecting-ip") or (
        request.client.host if request.client else "unknown"
    )


class _LazyRateLimiter:
    def __init__(self, getter):
        self._getter = getter
        self._delegate: RateLimiter | None = None

    async def __call__(self, request: Request, response: Response) -> None:
        if self._delegate is None:
            limiter = self._getter()
            if limiter is None:
                return None
            self._delegate = RateLimiter(limiter=limiter, identifier=_client_identifier)
        await self._delegate(request, response)
        return None


DefaultRateLimit = _LazyRateLimiter(lambda: _default_limiter)
StrictRateLimit = _LazyRateLimiter(lambda: _strict_limiter)
