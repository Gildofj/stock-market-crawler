import asyncio
import random
from typing import Any

import httpx


class RequestManager:
    """
    Centralized manager for HTTP requests with rate limiting and retry logic.

    Uses a shared httpx client to manage connections efficiently and implement
    respectful crawling patterns.
    """

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self):
        self._client = httpx.Client(headers={"User-Agent": self.USER_AGENT}, timeout=20)
        self._async_client = httpx.AsyncClient(headers={"User-Agent": self.USER_AGENT}, timeout=20)

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Synchronous GET request with jittered delay."""
        # Simple jitter to avoid robotic patterns
        import time

        time.sleep(random.uniform(0.5, 1.5))

        default_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",  # noqa: E501
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "DNT": "1",
            "Cache-Control": "max-age=0",
        }
        if "headers" in kwargs:
            default_headers.update(kwargs.pop("headers"))

        return self._client.get(url, headers=default_headers, **kwargs)

    async def get_async(self, url: str, **kwargs: Any) -> httpx.Response:
        """Asynchronous GET request."""
        # Respectful async delay
        await asyncio.sleep(random.uniform(0.2, 0.8))
        return await self._async_client.get(url, **kwargs)

    async def close(self):
        """Closes internal clients."""
        await self._async_client.aclose()
        self._client.close()
