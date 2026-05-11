import asyncio
import random
import time
from typing import Any

import httpx
from loguru import logger


class RequestManager:
    """
    Centralized manager for HTTP requests with rate limiting, retries,
    and User-Agent rotation to avoid bot detection.
    """

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    ]

    def __init__(self, proxies: list[str] | None = None):
        self.proxies = proxies

        client_proxy = None
        if proxies:
            # Simple rotation: pick one for the lifetime of the manager
            client_proxy = random.choice(proxies)

        self._client = httpx.Client(
            timeout=20, follow_redirects=True, proxy=client_proxy
        )
        self._async_client = httpx.AsyncClient(
            timeout=20, follow_redirects=True, proxy=client_proxy
        )

    def _get_headers(self, url: str) -> dict[str, str]:
        """Generates realistic headers for a request."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc

        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": f"https://{domain}/" if domain else "https://www.google.com/",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "DNT": "1",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1",
        }

    def get(self, url: str, max_retries: int = 3, **kwargs: Any) -> httpx.Response:
        """Synchronous GET request with jittered delay and retries."""
        headers = self._get_headers(url)
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        # Jittered delay (longer for sync to be respectful)
        time.sleep(random.uniform(1.0, 2.5))

        for attempt in range(max_retries):
            try:
                response = self._client.get(url, headers=headers, **kwargs)

                # If we get rate limited or forbidden, wait and retry with backoff
                if response.status_code in [403, 429] and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5 + random.uniform(0, 5)
                    logger.warning(
                        f"Request to {url} failed with {response.status_code}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    time.sleep(wait_time)
                    # Rotate headers for retry
                    headers.update(self._get_headers(url))
                    continue

                return response
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(
                        f"Request error for {url}: {e}. Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue
                raise

        # Should not reach here if max_retries > 0, but for safety:
        return self._client.get(url, headers=headers, **kwargs)

    async def get_async(self, url: str, max_retries: int = 3, **kwargs: Any) -> httpx.Response:
        """Asynchronous GET request with retries."""
        headers = self._get_headers(url)
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        await asyncio.sleep(random.uniform(0.5, 1.5))

        for attempt in range(max_retries):
            try:
                response = await self._async_client.get(url, headers=headers, **kwargs)

                if response.status_code in [403, 429] and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5 + random.uniform(0, 5)
                    logger.warning(
                        f"Async request to {url} failed with {response.status_code}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    await asyncio.sleep(wait_time)
                    headers.update(self._get_headers(url))
                    continue

                return response
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(
                        f"Async request error for {url}: {e}. Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise

        return await self._async_client.get(url, headers=headers, **kwargs)

    async def close(self):
        """Closes internal clients."""
        await self._async_client.aclose()
        self._client.close()
