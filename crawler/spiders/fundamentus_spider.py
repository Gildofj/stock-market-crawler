import re
from bs4 import BeautifulSoup
from loguru import logger

from ..models.contract import CrawlResult
from ..services.request_manager import RequestManager
from .base_spider import BaseSpider


class FundamentusSpider(BaseSpider):
    BASE_URL = "https://www.fundamentus.com.br/detalhes.php?papel="

    def __init__(self, request_manager: RequestManager = None):
        self.request_manager = request_manager or RequestManager()

    def crawl_ticker(self, symbol: str) -> CrawlResult:
        url = f"{self.BASE_URL}{symbol}"
        result = CrawlResult(symbol=symbol)

        try:
            response = self.request_manager.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # 1. Enrich Company Metadata
            empresa_td = soup.find("td", string="Empresa")
            company_name = next_td.text.strip() if empresa_td and (next_td := empresa_td.find_next_sibling("td")) else None
            
            setor_td = soup.find("td", string="Setor")
            setor = next_td.text.strip() if setor_td and (next_td := setor_td.find_next_sibling("td")) else None
            
            subsetor_td = soup.find("td", string="Subsetor")
            subsetor = next_td.text.strip() if subsetor_td and (next_td := subsetor_td.find_next_sibling("td")) else None

            # Extract Logo
            logo_url = None
            img = soup.find("img", alt=re.compile(r"logo", re.I))
            if img and "src" in img.attrs:
                src = img["src"]
                logo_url = f"https://www.fundamentus.com.br/{src}" if src.startswith("/") else src

            result.name = company_name
            result.sector = setor
            result.sub_sector = subsetor
            result.logo_url = logo_url

            # 2. Extract Fundamentals
            result.p_l = self._parse_val(soup, "P/L")
            result.p_vp = self._parse_val(soup, "P/VP")
            result.dy = self._parse_val(soup, "Div. Yield")
            result.roe = self._parse_val(soup, "ROE")
            result.market_cap = self._parse_val(soup, "Valor de mercado")
            result.debt_to_equity = self._parse_val(soup, "Dív. Líq / Patrim. Líq")
            result.eps = self._parse_val(soup, "LPA")

        except Exception as e:
            logger.error(f"Fundamentus error for {symbol}: {e}")

        return result

    def _parse_val(self, soup, label):
        try:
            element = soup.find("span", string=label).parent.find_next_sibling("td").text
            val = element.replace(".", "").replace(",", ".").replace("%", "").strip()
            return float(val) if val else None
        except Exception:
            return None
