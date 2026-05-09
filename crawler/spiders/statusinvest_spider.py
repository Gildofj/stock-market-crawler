import requests
from bs4 import BeautifulSoup
from loguru import logger
from .base_spider import BaseSpider
from ..models.schemas import FundamentalSchema

class StatusInvestSpider(BaseSpider):
    """
    Highly reliable scraper for StatusInvest.
    Used for cross-referencing fundamentals and fetching dividend history.
    """
    BASE_URL = "https://statusinvest.com.br/acoes/"

    def crawl_ticker(self, symbol: str):
        url = f"{self.BASE_URL}{symbol.lower()}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                logger.warning(f"StatusInvest: Symbol {symbol} not found or blocked (Status: {response.status_code})")
                return

            soup = BeautifulSoup(response.text, 'lxml')

            # StatusInvest stores indicators in divs with class 'value'
            # This is a simplified extraction of common indicators
            dy = self._parse_indicator(soup, "Dividend Yield")
            p_l = self._parse_indicator(soup, "P/L")
            p_vp = self._parse_indicator(soup, "P/VP")
            roe = self._parse_indicator(soup, "ROE")

            if dy or p_l or p_vp:
                company = self.data_service.get_company_by_symbol(symbol)
                if company:
                    fundamental_schema = FundamentalSchema(
                        p_l=p_l,
                        p_vp=p_vp,
                        dy=dy,
                        roe=roe
                    )
                    self.data_service.save_fundamentals(company.id, fundamental_schema)
                    logger.info(f"StatusInvest: Enriched fundamentals for {symbol}")

        except Exception as e:
            logger.error(f"StatusInvest error for {symbol}: {e}")

    def _parse_indicator(self, soup, label):
        try:
            # StatusInvest structure is complex, we look for the title and get the value next to it
            element = soup.find('h3', string=lambda t: t and label in t)
            if element:
                value_div = element.parent.find('strong', class_='value')
                if value_div:
                    val = value_div.text.replace('.', '').replace(',', '.').replace('%', '').strip()
                    return float(val) if val and val != '-' else None
            return None
        except:
            return None
