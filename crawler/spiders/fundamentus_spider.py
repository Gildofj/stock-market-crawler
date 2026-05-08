import requests
from bs4 import BeautifulSoup
from loguru import logger

from ..models.schemas import CompanySchema, FundamentalSchema
from .base_spider import BaseSpider


class FundamentusSpider(BaseSpider):
    BASE_URL = "https://www.fundamentus.com.br/detalhes.php?papel="

    def crawl_ticker(self, symbol: str):
        url = f"{self.BASE_URL}{symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"  # noqa: E501
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # Basic Company Info (if not exists)
            # Fundamentus tables are a bit messy, we extract specific <span> or <td>
            # This is a simplified example of scraping Fundamentus
            company_name = soup.find("td", string="Empresa").find_next_sibling("td").text.strip()

            company_schema = CompanySchema(
                symbol=symbol,
                name=company_name,
                sector=None,  # Extract from soup if needed
                sub_sector=None,
                segment=None,
            )
            company = self.data_service.get_or_create_company(company_schema)

            # Extract Fundamentals
            # Note: Fundamentus uses different labels, mapping is required
            p_l = self._parse_val(soup, "P/L")
            p_vp = self._parse_val(soup, "P/VP")
            dy = self._parse_val(soup, "Div. Yield")
            roe = self._parse_val(soup, "ROE")

            fundamental_schema = FundamentalSchema(p_l=p_l, p_vp=p_vp, dy=dy, roe=roe)

            self.data_service.save_fundamentals(company.id, fundamental_schema)
            logger.info(f"Fundamentus: Saved fundamentals for {symbol}")

        except Exception as e:
            logger.error(f"Fundamentus error for {symbol}: {e}")

    def _parse_val(self, soup, label):
        try:
            element = soup.find("span", string=label).parent.find_next_sibling("td").text
            val = element.replace(".", "").replace(",", ".").replace("%", "").strip()
            return float(val) if val else None
        except Exception:
            return None
