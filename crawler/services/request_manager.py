import asyncio
import random
import time
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlparse

import nodriver as uc
import orjson
from curl_cffi import requests
from loguru import logger


@runtime_checkable
class ResponseProtocol(Protocol):
    status_code: int
    text: str
    content: bytes
    headers: dict[str, str]
    url: str

    def json(self) -> Any: ...

    def raise_for_status(self) -> None: ...


class RequestManagerError(Exception):
    pass


class StealthResponse:
    def __init__(
        self, status_code: int, text: str, url: str, headers: dict[str, str] | None = None
    ):
        self.status_code = status_code
        self.text = text
        self.url = url
        self.content = text.encode("utf-8")
        self.headers = headers or {"Content-Type": "text/html"}
        self.cookies = {}

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self) -> Any:
        try:
            return orjson.loads(self.text)
        except (orjson.JSONDecodeError, TypeError):
            logger.debug(f"Stealth: Failed to decode JSON from {self.url}")
            return {}

    def raise_for_status(self) -> None:
        if not self.ok:
            raise RequestManagerError(f"HTTP Error {self.status_code} for {self.url}")


class RequestManager:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",  # noqa: E501 - Motivo: URL longa
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",  # noqa: E501 - Motivo: URL longa
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",  # noqa: E501 - Motivo: URL longa
    ]

    def __init__(
        self,
        proxies: list[str] | None = None,
        max_concurrent_browsers: int = 2,
        bypass_domains: frozenset[str] | None = None,
    ):
        self.proxies = proxies
        self.proxy = random.choice(proxies) if proxies else None

        if bypass_domains is None:
            from core.config import settings

            bypass_domains = settings.proxy_bypass_set
        self._bypass: frozenset[str] = bypass_domains

        self._browser_semaphore = asyncio.Semaphore(max_concurrent_browsers)

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
        # Direct sessions: skip the proxy for Brazilian gov/exchange endpoints
        # that have no anti-bot defense — routing them through webshare only
        # introduces failure modes (e.g. 407 when the secret rotates).
        # When no proxy is configured, alias to the same objects to avoid
        # opening two redundant connection pools.
        if self.proxy:
            self._session_direct = requests.Session(impersonate="chrome124", timeout=30)
            self._async_session_direct = requests.AsyncSession(
                impersonate="chrome124", timeout=30
            )
        else:
            self._session_direct = self._session
            self._async_session_direct = self._async_session

    def _should_bypass(self, url: str) -> bool:
        hostname = (urlparse(url).hostname or "").lower()
        if not hostname or not self._bypass:
            return False
        if hostname in self._bypass:
            return True
        return any(hostname.endswith(f".{domain}") for domain in self._bypass)

    def _get_headers(self, url: str) -> dict[str, str]:
        from urllib.parse import urlparse

        from core.config import settings

        domain = urlparse(url).netloc

        headers = {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": f"https://{domain}/" if domain else "https://www.google.com/",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        if settings.CRAWLER_CONTACT_EMAIL:
            headers["From"] = settings.CRAWLER_CONTACT_EMAIL
        return headers

    def _tier2_or_response(
        self, url: str, response: ResponseProtocol
    ) -> ResponseProtocol:
        from core.config import settings

        if not settings.ENABLE_TIER2_STEALTH:
            logger.warning(
                f"Tier 1 blocked for {url} (status={response.status_code}); "
                "Tier 2 disabled by ENABLE_TIER2_STEALTH=false."
            )
            return response
        logger.warning(
            f"Tier 1 (curl_cffi) blocked for {url}. Falling back to Tier 2 (nodriver)."
        )
        return asyncio.run(self._nodriver_get(url))

    def _tier2_or_raise(self, url: str, exc: Exception) -> ResponseProtocol:
        from core.config import settings

        if not settings.ENABLE_TIER2_STEALTH:
            logger.warning(
                f"Tier 1 failed for {url}: {exc}. Tier 2 disabled by "
                "ENABLE_TIER2_STEALTH=false; not retrying."
            )
            raise exc
        logger.warning(
            f"Tier 1 (curl_cffi) failed for {url}: {exc}. Falling back to Tier 2 (nodriver)."
        )
        return asyncio.run(self._nodriver_get(url))

    async def _tier2_or_response_async(
        self, url: str, response: ResponseProtocol
    ) -> ResponseProtocol:
        from core.config import settings

        if not settings.ENABLE_TIER2_STEALTH:
            logger.warning(
                f"Tier 1 async blocked for {url} (status={response.status_code}); "
                "Tier 2 disabled by ENABLE_TIER2_STEALTH=false."
            )
            return response
        logger.warning(
            f"Tier 1 async blocked for {url}. Falling back to Tier 2 (nodriver)."
        )
        return await self._nodriver_get(url)

    async def _tier2_or_raise_async(self, url: str, exc: Exception) -> ResponseProtocol:
        from core.config import settings

        if not settings.ENABLE_TIER2_STEALTH:
            logger.warning(
                f"Tier 1 async failed for {url}: {exc}. Tier 2 disabled by "
                "ENABLE_TIER2_STEALTH=false; not retrying."
            )
            raise exc
        logger.warning(
            f"Tier 1 async failed for {url}: {exc}. Falling back to Tier 2 (nodriver)."
        )
        return await self._nodriver_get(url)

    async def _nodriver_get(self, url: str) -> StealthResponse:
        async with self._browser_semaphore:
            logger.info(f"Stealth: Launching headless browser for {url}")
            browser: uc.Browser | None = None
            try:
                import os

                executable_path = os.getenv("CHROME_BIN") or None
                browser = await uc.start(
                    sandbox=False,
                    headless=True,
                    browser_executable_path=executable_path,
                    browser_args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--no-first-run",
                        "--no-zygote",
                        "--single-process",
                    ],
                )

                page = await browser.get(url)

                if page is None:
                    raise RequestManagerError("Failed to open page (nodriver returned None)")

                wait_time = random.uniform(6, 10)
                logger.debug(f"Stealth: Waiting {wait_time:.1f}s for load and challenges...")
                await asyncio.sleep(wait_time)

                content = await page.get_content()
                return StealthResponse(status_code=200, text=content, url=url)
            except Exception as e:
                logger.error(f"Stealth: nodriver failed for {url}: {e}")
                return StealthResponse(status_code=500, text=str(e), url=url)
            finally:
                if browser:
                    try:
                        browser.stop()
                        await asyncio.sleep(0.5)
                    except Exception:
                        pass

    def get(self, url: str, max_retries: int = 3, **kwargs: Any) -> ResponseProtocol:
        headers = self._get_headers(url)
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        session = self._session_direct if self._should_bypass(url) else self._session

        time.sleep(random.uniform(1.0, 2.5))

        for attempt in range(max_retries):
            try:
                response = session.get(url, headers=headers, **kwargs)

                if response.status_code in [403, 429]:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5 + random.uniform(0, 5)
                        logger.warning(
                            f"Request to {url} failed ({response.status_code}). "
                            f"Retrying in {wait_time:.1f}s..."
                        )
                        time.sleep(wait_time)
                        continue

                    return self._tier2_or_response(url, response)

                return response  # type: ignore - Motivo: Tipagem externa
            except (requests.RequestsError, Exception) as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"Request error for {url}: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                return self._tier2_or_raise(url, e)

        return session.get(url, headers=headers, **kwargs)  # type: ignore - Motivo: Tipagem externa

    async def get_async(
        self,
        url: str,
        max_retries: int = 3,
        binary: bool = False,
        **kwargs: Any,
    ) -> ResponseProtocol:
        headers = self._get_headers(url)
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        session = (
            self._async_session_direct
            if self._should_bypass(url)
            else self._async_session
        )

        await asyncio.sleep(random.uniform(0.5, 1.5))

        for attempt in range(max_retries):
            try:
                response = await session.get(url, headers=headers, **kwargs)

                if response.status_code in [403, 429]:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5 + random.uniform(0, 5)
                        await asyncio.sleep(wait_time)
                        continue

                    if binary:
                        logger.warning(
                            f"Tier 1 async blocked for {url} (binary=True; "
                            "skipping nodriver fallback)."
                        )
                        return response  # type: ignore - Motivo: Tipagem externa
                    return await self._tier2_or_response_async(url, response)

                return response  # type: ignore - Motivo: Tipagem externa
            except (requests.RequestsError, Exception) as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep((attempt + 1) * 2)
                    continue

                if binary:
                    # nodriver returns HTML; useless for downloading PDFs/ZIPs/CSVs.
                    logger.warning(
                        f"Tier 1 async failed for {url}: {e}. binary=True; not falling back."
                    )
                    raise
                return await self._tier2_or_raise_async(url, e)

        return await session.get(url, headers=headers, **kwargs)  # type: ignore - Motivo: Tipagem externa

    async def close(self):
        try:
            await self._async_session.close()
            self._session.close()
            if self._async_session_direct is not self._async_session:
                await self._async_session_direct.close()
            if self._session_direct is not self._session:
                self._session_direct.close()
        except Exception as e:
            logger.debug(f"RequestManager: Error during close: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._session.close()
        if self._session_direct is not self._session:
            self._session_direct.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
