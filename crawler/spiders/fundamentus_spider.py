import requests
from bs4 import BeautifulSoup
from loguru import logger

from ..models.schemas import CompanySchema, FundamentalSchema
from .base_spider import BaseSpider
from ..services.logo_service import LogoService


class FundamentusSpider(BaseSpider):
    BASE_URL = "https://www.fundamentus.com.br/detalhes.php?papel="

    def __init__(self, data_service):
        super().__init__(data_service)
        self.logo_service = LogoService(data_service)

    def crawl_ticker(self, symbol: str):
        url = f"{self.BASE_URL}{symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"  # noqa: E501
        }

        try:
            # Ensure logo is present (with fallback)
            self.logo_service.update_logo_if_missing(symbol)

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # Basic Company Info (if not exists)
            # Fundamentus tables are a bit messy, we extract specific <span> or <td>
            # This is a simplified example of scraping Fundamentus
            empresa_td = soup.find("td", string="Empresa")
            company_name = symbol
            if empresa_td:
                next_td = empresa_td.find_next_sibling("td")
                if next_td:
                    company_name = next_td.text.strip()

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
            
            # New fields
            market_cap = self._parse_val(soup, "Valor de mercado")
            debt_to_equity = self._parse_val(soup, "Dív. Líq / Patrim. Líq")
            eps = self._parse_val(soup, "LPA")

            fundamental_schema = FundamentalSchema(
                p_l=p_l, 
                p_vp=p_vp, 
                dy=dy, 
                roe=roe,
                market_cap=market_cap,
                debt_to_equity=debt_to_equity,
                eps=eps
            )

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
