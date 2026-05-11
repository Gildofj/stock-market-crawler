import asyncio
import re
import time
from typing import Any

from bs4 import BeautifulSoup, Tag
from loguru import logger

from ..models.contract import CrawlResult
from ..services.request_manager import RequestManager
from .base_spider import BaseSpider


class StatusInvestSpider(BaseSpider):
    """
    Spider for extracting data from StatusInvest.

    Uses a combination of an advanced search API (for fast bulk indicators)
    and individual company profiles (for logos and websites).
    """

    API_URL = (
        "https://statusinvest.com.br/category/advancedsearchresult?"
        "search=%7B%22Sector%22%3A%22%22%2C%22SubSector%22%3A%22%22%2C"
        "%22Segment%22%3A%22%22%2C%22Ranking%22%3A%5B%5D%2C%22IndicatorQuery"
        "%22%3A%5B%5D%2C%22MyStocks%22%3Afalse%7D&CategoryType=1"
    )
    BASE_URL = "https://statusinvest.com.br/acoes/"

    def __init__(self, request_manager: RequestManager | None = None):
        self.request_manager = request_manager or RequestManager()
        self._cache: dict[str, Any] = {}
        self._last_api_failure = 0.0
        self._api_cooldown = 300.0  # 5 minutes cooldown after a failure

    def _fetch_all_data(self) -> dict[str, Any]:
        """Fetches all companies from the StatusInvest API and caches them."""
        if self._cache:
            return self._cache

        # Check if we are in cooldown
        if time.time() - self._last_api_failure < self._api_cooldown:
            logger.debug("StatusInvest API: In cooldown, skipping fetch")
            return {}

        try:
            response = self.request_manager.get(self.API_URL, timeout=30)
            response.raise_for_status()
            data = response.json()
            self._cache = {item["ticker"]: item for item in data}
            logger.info(f"StatusInvest API: Cached {len(self._cache)} companies")
            return self._cache
        except Exception as e:
            logger.error(f"StatusInvest API error: {e}")
            self._last_api_failure = time.time()
            return {}

    def crawl_ticker(self, symbol: str) -> CrawlResult:
        result = CrawlResult(symbol=symbol)
        all_data = self._fetch_all_data()

        item = all_data.get(symbol.upper())
        if not item:
            logger.warning(f"StatusInvest: {symbol} not found in API response")
            return result

        try:
            # Mapping API fields to CrawlResult
            result.name = str(item.get("companyName")) if item.get("companyName") else None
            result.p_l = float(item.get("p_L")) if item.get("p_L") else None
            result.p_vp = float(item.get("p_VP")) if item.get("p_VP") else None
            result.dy = float(item.get("dy")) if item.get("dy") else 0
            result.roe = float(item.get("roe")) if item.get("roe") else None
            result.roic = float(item.get("roic")) if item.get("roic") else None
            result.ev_ebitda = float(item.get("ev_Ebitda")) if item.get("ev_Ebitda") else None
            result.net_margin = float(item.get("margemLiquida")) if item.get("margemLiquida") else None
            result.liquid_debt_ebitda = (
                float(item.get("dividaliquidaEbitda")) if item.get("dividaliquidaEbitda") else None
            )
            result.cagr_revenue_5y = float(item.get("receitas_cagr5")) if item.get("receitas_cagr5") else None
            result.cagr_profit_5y = float(item.get("lucros_cagr5")) if item.get("lucros_cagr5") else None
            result.debt_to_equity = (
                float(item.get("dividaLiquidaPatrimonioLiquido"))
                if item.get("dividaLiquidaPatrimonioLiquido")
                else None
            )
            result.market_cap = float(item.get("valorMercado")) if item.get("valorMercado") else None
            result.eps = float(item.get("lpa")) if item.get("lpa") else None

            # Enrich with Logo and Website from profile page
            self._enrich_from_profile(result)

        except Exception as e:
            logger.error(f"StatusInvest mapping error for {symbol}: {e}")

        return result

    async def crawl_ticker_async(self, symbol: str) -> CrawlResult:
        """Asynchronously crawls a ticker from StatusInvest."""
        # API fetch is usually done once and cached
        all_data = await asyncio.to_thread(self._fetch_all_data)
        item = all_data.get(symbol.upper())
        result = CrawlResult(symbol=symbol)

        if item:
            # Map standard fields
            result.dy = float(item.get("dy", 0))
            result.p_l = float(item.get("p_L", 0))
            # ... (more fields could be added here similar to crawl_ticker)

        await self._enrich_from_profile_async(result)
        return result

    def _enrich_from_profile(self, result: CrawlResult):
        """Fetches the company profile page to extract logo and website."""
        url = f"{self.BASE_URL}{result.symbol.lower()}"
        try:
            response = self.request_manager.get(url, timeout=10)
            if response.status_code == 200:
                self._parse_profile_html(response.text, result)
        except Exception as e:
            logger.debug(f"StatusInvest profile enrichment failed for {result.symbol}: {e}")

    async def _enrich_from_profile_async(self, result: CrawlResult):
        """Async version of profile enrichment."""
        url = f"{self.BASE_URL}{result.symbol.lower()}"
        try:
            response = await self.request_manager.get_async(url)
            if response.status_code == 200:
                self._parse_profile_html(response.text, result)
        except Exception as e:
            logger.debug(f"StatusInvest profile enrichment failed for {result.symbol}: {e}")

    def _parse_profile_html(self, html: str, result: CrawlResult):
        """Shared logic to parse profile HTML."""
        soup = BeautifulSoup(html, "lxml")

        # 1. Extract Logo
        avatar_div: Any = soup.find("div", class_="avatar")
        if isinstance(avatar_div, Tag) and avatar_div.has_attr("style"):
            style = str(avatar_div.get("style"))
            match = re.search(r"url\((.*?)\)", style)
            if match:
                logo_path = match.group(1).replace("'", "").replace('"', "")
                result.logo_url = (
                    f"https://statusinvest.com.br{logo_path}"
                    if logo_path.startswith("/")
                    else logo_path
                )

        # 2. Extract Website
        site_link: Any = soup.find("a", title=re.compile(r"Site oficial", re.I))
        if isinstance(site_link, Tag) and site_link.has_attr("href"):
            href = site_link.get("href")
            if isinstance(href, list):
                href = href[0]
            result.website = str(href)
