import re
import time

from bs4 import BeautifulSoup, Tag
from loguru import logger

from ..models.contract import CrawlResult
from ..services.request_manager import RequestManager
from .base_spider import BaseSpider


class FundamentusSpider(BaseSpider):
    """
    Spider for extracting fundamental data from Fundamentus.com.br.

    This spider parses the HTML response of the details page for a specific ticker.
    """

    BASE_URL = "https://www.fundamentus.com.br/detalhes.php?papel="

    def __init__(self, request_manager: RequestManager | None = None):
        self.request_manager = request_manager or RequestManager()
        self._last_failure = 0.0
        self._cooldown = 300.0  # 5 minutes cooldown

    async def crawl_ticker_async(self, symbol: str) -> CrawlResult:
        """Asynchronously crawls a ticker from Fundamentus."""
        result = CrawlResult(symbol=symbol)

        if time.time() - self._last_failure < self._cooldown:
            return result

        url = f"{self.BASE_URL}{symbol}"
        try:
            response = await self.request_manager.get_async(url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "lxml")
                self._parse_metadata(soup, result)
                self._parse_fundamentals(soup, result)
            elif response.status_code in [403, 429]:
                self._last_failure = time.time()
        except Exception as e:
            logger.error(f"Fundamentus async error for {symbol}: {e}")

        return result

    def crawl_ticker(self, symbol: str) -> CrawlResult:
        """Synchronously crawls a ticker from Fundamentus."""
        result = CrawlResult(symbol=symbol)

        if time.time() - self._last_failure < self._cooldown:
            return result

        url = f"{self.BASE_URL}{symbol}"
        try:
            response = self.request_manager.get(url, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "lxml")
                self._parse_metadata(soup, result)
                self._parse_fundamentals(soup, result)
            elif response.status_code in [403, 429]:
                self._last_failure = time.time()
                logger.warning(
                    f"Fundamentus blocked (HTTP {response.status_code}). "
                    "Entering cooldown."
                )

        except Exception as e:
            logger.error(f"Fundamentus error for {symbol}: {e}")

        return result

    def _parse_metadata(self, soup: BeautifulSoup, result: CrawlResult) -> None:
        """Extracts company metadata from the soup object."""
        # Mapping for metadata
        mappings = {
            "Empresa": "name",
            "Setor": "sector",
            "Subsetor": "sub_sector",
        }

        all_tds = soup.find_all("td")
        for label, attr in mappings.items():
            pattern = re.compile(f"^{re.escape(label)}$")
            for td in all_tds:
                if isinstance(td, Tag) and td.string and pattern.match(td.string):
                    next_td = td.find_next_sibling("td")
                    if isinstance(next_td, Tag):
                        setattr(result, attr, next_td.get_text().strip())
                    break

        # Extract Website
        for td in all_tds:
            if isinstance(td, Tag) and td.string and td.string == "Site Oficial":
                next_td = td.find_next_sibling("td")
                if isinstance(next_td, Tag):
                    site_link = next_td.find("a")
                    if isinstance(site_link, Tag) and site_link.has_attr("href"):
                        href = site_link.get("href")
                        if isinstance(href, list):
                            href = href[0]
                        result.website = str(href) if href else None
                break

        # Extract Logo
        img = soup.find("img", alt=re.compile(r"logo", re.I))
        if isinstance(img, Tag) and img.has_attr("src"):
            src = img.get("src")
            if src:
                if isinstance(src, list):
                    src = src[0]
                src_str = str(src)
                result.logo_url = (
                    f"https://www.fundamentus.com.br/{src_str}"
                    if src_str.startswith("/")
                    else src_str
                )

    def _parse_fundamentals(self, soup: BeautifulSoup, result: CrawlResult) -> None:
        """Helper to parse all fundamental metrics."""
        result.p_l = self._extract_value(soup, "P/L")
        result.p_vp = self._extract_value(soup, "P/VP")
        result.dy = self._extract_value(soup, "Div. Yield")
        result.roe = self._extract_value(soup, "ROE")
        result.roic = self._extract_value(soup, "ROIC")
        result.ev_ebitda = self._extract_value(soup, "EV / EBITDA")
        result.net_margin = self._extract_value(soup, "Margem Líquida")
        result.liquid_debt_ebitda = self._extract_value(soup, "Dív. Líq / EBITDA")
        result.cagr_revenue_5y = self._extract_value(soup, "Cres. Rec. (5a)")
        result.cagr_profit_5y = self._extract_value(soup, "Cres. Lucro (5a)")
        result.market_cap = self._extract_value(soup, "Valor de mercado")
        result.debt_to_equity = self._extract_value(soup, "Dív. Líq / Patrim. Líq")
        result.eps = self._extract_value(soup, "LPA")

    def _extract_value(self, soup: BeautifulSoup, label: str) -> float | None:
        """Helper to extract and format a numerical value from a labeled span."""
        try:
            pattern = re.compile(f"^{re.escape(label)}$")
            all_spans = soup.find_all("span")
            span: Tag | None = None
            for s in all_spans:
                if isinstance(s, Tag) and s.string and pattern.match(s.string):
                    span = s
                    break

            if span is None:
                return None

            parent = span.parent
            if not isinstance(parent, Tag):
                return None

            td = parent.find_next_sibling("td")
            if not isinstance(td, Tag):
                return None

            val_str = (
                td.get_text().replace(".", "").replace(",", ".").replace("%", "").strip()
            )
            return float(val_str) if val_str and val_str != "-" else None
        except (ValueError, AttributeError):
            return None
