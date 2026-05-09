import requests
import time
from bs4 import BeautifulSoup
from loguru import logger
from .request_manager import RequestManager

class TickerService:
    # This URL provides a CSV-like display of all companies in Fundamentus
    LIST_URL = "https://www.fundamentus.com.br/detalhes.php"
    _cached_tickers = []
    _last_fetch = 0

    def __init__(self):
        self.request_manager = RequestManager()

    def get_all_tickers(self) -> list[str]:
        """
        Scrapes all available tickers from Fundamentus with basic in-memory caching.
        """
        # Cache for 1 hour
        if self._cached_tickers and (time.time() - self._last_fetch < 3600):
            logger.info("Using cached ticker list.")
            return self._cached_tickers

        logger.info("Fetching all active tickers from B3 via Fundamentus...")
        
        try:
            response = self.request_manager.get(self.LIST_URL, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find the main table with all symbols
            table = soup.find('table', {'id': 'testesu'})
            if not table:
                logger.warning("Could not find the ticker table. Using fallback method.")
                links = soup.find_all('a', href=True)
                tickers = [link.text.strip() for link in links if 'detalhes.php?papel=' in link['href']]
            else:
                tickers = [row.find('a').text.strip() for row in table.find_all('tr')[1:] if row.find('a')]

            clean_tickers = [t for t in tickers if t.isalnum() and 4 <= len(t) <= 6]
            unique_tickers = sorted(list(set(clean_tickers)))
            
            # Update cache
            TickerService._cached_tickers = unique_tickers
            TickerService._last_fetch = time.time()
            
            logger.info(f"Successfully discovered {len(unique_tickers)} tickers.")
            return unique_tickers

        except Exception as e:
            logger.error(f"Failed to fetch ticker list: {e}")
            return []
