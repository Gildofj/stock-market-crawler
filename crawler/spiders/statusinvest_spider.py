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

    async def crawl_ticker_async(self, symbol: str, enrich_metadata: bool = True) -> CrawlResult:
        """Asynchronously crawls a ticker from StatusInvest."""
        # API fetch is usually done once and cached
        all_data = await asyncio.to_thread(self._fetch_all_data)
        item = all_data.get(symbol.upper())
        result = CrawlResult(symbol=symbol)

        if item:
            self._map_api_item(item, result)

        if enrich_metadata:
            await self._enrich_from_profile_async(result)
        return result

    @staticmethod
    def _opt_float(value: Any) -> float | None:
        """Coerces a truthy value to float, returning None otherwise."""
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _map_api_item(self, item: dict[str, Any], result: CrawlResult):
        """Maps API dictionary item to CrawlResult."""
        company_name = item.get("companyName")
        result.name = str(company_name) if company_name else None
        result.p_l = self._opt_float(item.get("p_L"))
        result.p_vp = self._opt_float(item.get("p_VP"))
        result.dy = self._opt_float(item.get("dy")) or 0.0
        result.roe = self._opt_float(item.get("roe"))
        result.roic = self._opt_float(item.get("roic"))
        result.ev_ebitda = self._opt_float(item.get("ev_Ebitda"))
        result.net_margin = self._opt_float(item.get("margemLiquida"))
        result.liquid_debt_ebitda = self._opt_float(item.get("dividaliquidaEbitda"))
        result.cagr_revenue_5y = self._opt_float(item.get("receitas_cagr5"))
        result.cagr_profit_5y = self._opt_float(item.get("lucros_cagr5"))
        result.debt_to_equity = self._opt_float(item.get("dividaLiquidaPatrimonioLiquido"))
        result.market_cap = self._opt_float(item.get("valorMercado"))
        result.eps = self._opt_float(item.get("lpa"))

    def crawl_ticker(self, symbol: str) -> CrawlResult:
        result = CrawlResult(symbol=symbol)
        all_data = self._fetch_all_data()

        item = all_data.get(symbol.upper())
        if not item:
            logger.warning(f"StatusInvest: {symbol} not found in API response")
            return result

        try:
            self._map_api_item(item, result)

            # Enrich with Logo and Website from profile page
            self._enrich_from_profile(result)

        except Exception as e:
            logger.error(f"StatusInvest mapping error for {symbol}: {e}")

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
