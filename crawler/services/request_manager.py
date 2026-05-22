import asyncio
import random
import time
from typing import Any, Protocol, runtime_checkable

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

    def __init__(self, proxies: list[str] | None = None, max_concurrent_browsers: int = 2):
        self.proxies = proxies
        self.proxy = random.choice(proxies) if proxies else None

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

    async def _nodriver_get(self, url: str) -> StealthResponse:
        async with self._browser_semaphore:
            logger.info(f"Stealth: Launching headless browser for {url}")
            browser: uc.Browser | None = None
            try:
                browser = await uc.start(
                    sandbox=False,
                    headless=True,
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

        time.sleep(random.uniform(1.0, 2.5))

        for attempt in range(max_retries):
            try:
                response = self._session.get(url, headers=headers, **kwargs)

                if response.status_code in [403, 429]:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5 + random.uniform(0, 5)
                        logger.warning(
                            f"Request to {url} failed ({response.status_code}). "
                            f"Retrying in {wait_time:.1f}s..."
                        )
                        time.sleep(wait_time)
                        continue

                    logger.warning(
                        f"Tier 1 (curl_cffi) blocked for {url}. Falling back to Tier 2 (nodriver)."
                    )
                    return asyncio.run(self._nodriver_get(url))

                return response  # type: ignore - Motivo: Tipagem externa
            except (requests.RequestsError, Exception) as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"Request error for {url}: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                logger.warning(
                    f"Tier 1 (curl_cffi) failed for {url}: {e}. Falling back to Tier 2 (nodriver)."
                )
                return asyncio.run(self._nodriver_get(url))

        return self._session.get(url, headers=headers, **kwargs)  # type: ignore - Motivo: Tipagem externa

    async def get_async(self, url: str, max_retries: int = 3, **kwargs: Any) -> ResponseProtocol:
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

                    logger.warning(
                        f"Tier 1 async blocked for {url}. Falling back to Tier 2 (nodriver)."
                    )
                    return await self._nodriver_get(url)

                return response  # type: ignore - Motivo: Tipagem externa
            except (requests.RequestsError, Exception) as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep((attempt + 1) * 2)
                    continue

                logger.warning(
                    f"Tier 1 async failed for {url}: {e}. Falling back to Tier 2 (nodriver)."
                )
                return await self._nodriver_get(url)

        return await self._async_session.get(url, headers=headers, **kwargs)  # type: ignore - Motivo: Tipagem externa

    async def close(self):
        try:
            await self._async_session.close()
            self._session.close()
        except Exception as e:
            logger.debug(f"RequestManager: Error during close: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
