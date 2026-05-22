from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from loguru import logger

from core.repositories import CompanyRepository

from .metadata_overrides import get_override
from .request_manager import RequestManager


def _clearbit_url(website: str) -> str | None:
    parsed = urlparse(website if "://" in website else f"https://{website}")
    if not parsed.netloc:
        return None
    domain = parsed.netloc.removeprefix("www.")
    return f"https://logo.clearbit.com/{domain}"


class LogoService:
    def __init__(
        self,
        company_repo: CompanyRepository,
        request_manager: RequestManager | None = None,
    ) -> None:
        self.company_repo = company_repo
        self.request_manager = request_manager or RequestManager()

    async def resolve(self, symbol: str, website: str | None) -> str | None:
        override = get_override(symbol).get("logo_url")
        if override:
            return override

        if website:
            scraped = await self._extract_logo_from_site(website)
            if scraped:
                return scraped
            clearbit = _clearbit_url(website)
            if clearbit:
                return clearbit

        return None

    async def update_logo_if_missing(self, symbol: str) -> str | None:
        company = await self.company_repo.get_by_symbol(symbol)
        if company is None:
            return None
        if company.logo_url:
            return str(company.logo_url)

        logo_url = await self.resolve(symbol, getattr(company, "website", None))
        if logo_url:
            await self.company_repo.update_info(symbol, {"logo_url": logo_url})
            logger.info(f"Logo for {symbol} resolved: {logo_url}")
        return logo_url

    async def _extract_logo_from_site(self, site_url: str) -> str | None:
        try:
            response = await self.request_manager.get_async(site_url, timeout=10)
        except Exception as exc:
            logger.debug(f"LogoService: failed to fetch {site_url}: {exc}")
            return None
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "lxml")

        icon = soup.find("link", rel=lambda value: bool(value and "icon" in str(value).lower()))
        if isinstance(icon, Tag):
            href = icon.get("href")
            href_str = href[0] if isinstance(href, list) else href
            if href_str:
                return urljoin(site_url, str(href_str))

        og_image = soup.find("meta", attrs={"property": "og:image"})
        if isinstance(og_image, Tag):
            content = og_image.get("content")
            content_str = content[0] if isinstance(content, list) else content
            if content_str:
                return urljoin(site_url, str(content_str))

        logo_img = soup.find("img", alt=re.compile(r"logo", re.I))
        if isinstance(logo_img, Tag):
            src = logo_img.get("src")
            src_str = src[0] if isinstance(src, list) else src
            if src_str:
                return urljoin(site_url, str(src_str))

        parsed = urlparse(site_url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
        return None
