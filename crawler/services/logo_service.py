"""Best-effort logo discovery for companies that don't carry one yet.

Logos are sourced *only* from each company's own website (or its public
favicon endpoint). We deliberately do not scrape proprietary aggregators
because their logo assets are part of their bundled product offering and
attract the same database-protection risk as their indicators.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from loguru import logger

from ..services.data_service import DataService
from ..services.request_manager import RequestManager


class LogoService:
    """Resolves a logo URL for a company directly from its own site."""

    def __init__(self, data_service: DataService) -> None:
        self.data_service = data_service
        self.request_manager = RequestManager()

    def update_logo_if_missing(self, symbol: str) -> str | None:
        company = self.data_service.get_company_by_symbol(symbol)
        if company is None:
            return None
        if company.logo_url:
            return str(company.logo_url)

        website = getattr(company, "website", None)
        if not website:
            return None

        logo_url = self._extract_logo_from_site(str(website))
        if logo_url:
            self.data_service.update_company_info(symbol, {"logo_url": logo_url})
            logger.info(f"Logo for {symbol} resolved from official site.")
        return logo_url

    def _extract_logo_from_site(self, site_url: str) -> str | None:
        try:
            response = self.request_manager.get(site_url, timeout=10)
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

        # Last resort: assume there's a /favicon.ico at the site root.
        parsed = urlparse(site_url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
        return None
