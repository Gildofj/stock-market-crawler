from loguru import logger

from ..models.contract import CrawlResult
from ..services.request_manager import RequestManager
from .base_spider import BaseSpider


class StatusInvestSpider(BaseSpider):
    API_URL = "https://statusinvest.com.br/category/advancedsearchresult?search=%7B%22Sector%22%3A%22%22%2C%22SubSector%22%3A%22%22%2C%22Segment%22%3A%22%22%2C%22Ranking%22%3A%5B%5D%2C%22IndicatorQuery%22%3A%5B%5D%2C%22MyStocks%22%3Afalse%7D&CategoryType=1"

    def __init__(self, request_manager: RequestManager = None):
        self.request_manager = request_manager or RequestManager()
        self._cache = {}

    def _fetch_all_data(self):
        """Fetches all companies from the StatusInvest API and caches them."""
        if not self._cache:
            try:
                response = self.request_manager.get(self.API_URL, timeout=30)
                response.raise_for_status()
                data = response.json()
                self._cache = {item['ticker']: item for item in data}
                logger.info(f"StatusInvest API: Cached {len(self._cache)} companies")
            except Exception as e:
                logger.error(f"StatusInvest API error: {e}")
        return self._cache

    def crawl_ticker(self, symbol: str) -> CrawlResult:
        result = CrawlResult(symbol=symbol)
        all_data = self._fetch_all_data()
        
        item = all_data.get(symbol.upper())
        if not item:
            logger.warning(f"StatusInvest: {symbol} not found in API response")
            return result

        try:
            # Mapping API fields to CrawlResult
            # Note: StatusInvest API uses different names
            result.name = item.get('companyName')
            result.p_l = item.get('p_L')
            result.p_vp = item.get('p_VP')
            result.dy = item.get('dy')
            result.roe = item.get('roe')
            result.roic = item.get('roic')
            result.ev_ebitda = item.get('ev_Ebitda')
            result.net_margin = item.get('margemLiquida')
            result.liquid_debt_ebitda = item.get('dividaliquidaEbitda')
            result.debt_to_equity = item.get('dividaLiquidaPatrimonioLiquido')
            result.market_cap = item.get('valorMercado')
            result.eps = item.get('lpa')
            
            # StatusInvest usually provides sector info in a separate call or we can infer it
            # For now we use what's available in the search result
            
        except Exception as e:
            logger.error(f"StatusInvest mapping error for {symbol}: {e}")

        return result
