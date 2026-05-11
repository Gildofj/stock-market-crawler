import asyncio
import random
import time
from typing import Any

import nodriver as uc
from curl_cffi import requests
from loguru import logger


class StealthResponse:
    """Mock response object for nodriver to match curl_cffi interface."""
    def __init__(self, status_code: int, text: str, url: str, headers: dict | None = None):
        self.status_code = status_code
        self.text = text
        self.url = url
        self.content = text.encode("utf-8")
        self.headers = headers or {"Content-Type": "text/html"}

    def json(self) -> Any:
        import json
        try:
            return json.loads(self.text)
        except Exception:
            return {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP Error {self.status_code} for {self.url}")


class RequestManager:
    """
    Centralized manager for HTTP requests with rate limiting, retries,
    and fallback to headless browser for anti-bot challenges.
    """

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ]

    def __init__(self, proxies: list[str] | None = None):
        self.proxies = proxies
        self.proxy = random.choice(proxies) if proxies else None

        # Tier 1: curl_cffi for TLS fingerprinting
        self._session = requests.Session(
            impersonate="chrome124",
            proxy=self.proxy,
            timeout=30,
        )
        self._async_session = requests.AsyncSession(
            impersonate="chrome124",
            proxy=self.proxy,
            timeout=30,
        )

    def _get_headers(self, url: str) -> dict[str, str]:
        """Generates realistic headers for a request."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc

        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": f"https://{domain}/" if domain else "https://www.google.com/",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def _nodriver_get(self, url: str) -> StealthResponse:
        """Tier 2: Headless browser fallback using nodriver."""
        logger.info(f"Stealth: Launching headless browser for {url}")
        browser = None
        try:
            # Basic args for Docker/Actions
            browser = await uc.start(
                browser_args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.get(url)
            
            if page is None:
                raise Exception("Failed to open page (nodriver returned None)")

            # Wait for initial load
            await page
            
            # Extra wait for Cloudflare/WAF challenges
            wait_time = random.uniform(5, 8)
            logger.debug(f"Stealth: Waiting {wait_time:.1f}s for challenge resolution...")
            await asyncio.sleep(wait_time)
            
            content = await page.get_content()
            return StealthResponse(status_code=200, text=content, url=url)
        except Exception as e:
            logger.error(f"Stealth: nodriver failed for {url}: {e}")
            return StealthResponse(status_code=500, text=str(e), url=url)
        finally:
            if browser:
                try:
                    await browser.stop()
                except Exception:
                    pass

    def get(self, url: str, max_retries: int = 3, **kwargs: Any) -> Any:
        """Synchronous GET request with curl_cffi and nodriver fallback."""
        headers = self._get_headers(url)
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        # Jittered delay
        time.sleep(random.uniform(1.0, 2.5))

        for attempt in range(max_retries):
            try:
                response = self._session.get(url, headers=headers, **kwargs)

                if response.status_code in [403, 429]:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5 + random.uniform(0, 5)
                        logger.warning(f"Request to {url} failed ({response.status_code}). Retrying in {wait_time:.1f}s...")
                        time.sleep(wait_time)
                        continue
                    
                    # Last resort: Fallback to nodriver
                    logger.warning(f"Tier 1 (curl_cffi) blocked for {url}. Falling back to Tier 2 (nodriver).")
                    return asyncio.run(self._nodriver_get(url))

                return response
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"Request error for {url}: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                logger.warning(f"Tier 1 (curl_cffi) exception for {url}. Falling back to Tier 2 (nodriver).")
                return asyncio.run(self._nodriver_get(url))

        return self._session.get(url, headers=headers, **kwargs)

    async def get_async(self, url: str, max_retries: int = 3, **kwargs: Any) -> Any:
        """Asynchronous GET request with curl_cffi and nodriver fallback."""
        headers = self._get_headers(url)
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        await asyncio.sleep(random.uniform(0.5, 1.5))

        for attempt in range(max_retries):
            try:
                response = await self._async_session.get(url, headers=headers, **kwargs)

                if response.status_code in [403, 429]:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5 + random.uniform(0, 5)
                        await asyncio.sleep(wait_time)
                        continue
                    
                    logger.warning(f"Tier 1 async blocked for {url}. Falling back to Tier 2 (nodriver).")
                    return await self._nodriver_get(url)

                return response
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep((attempt + 1) * 2)
                    continue
                
                logger.warning(f"Tier 1 async exception for {url}. Falling back to Tier 2 (nodriver).")
                return await self._nodriver_get(url)

        return await self._async_session.get(url, headers=headers, **kwargs)

    async def close(self):
        """Closes internal clients."""
        await self._async_session.close()
        self._session.close()
