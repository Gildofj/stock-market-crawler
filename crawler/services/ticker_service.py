import time

from bs4 import BeautifulSoup
from loguru import logger

from .request_manager import RequestManager


class TickerService:
    # This URL provides a CSV-like display of all companies in Fundamentus
    LIST_URL = "https://www.fundamentus.com.br/detalhes.php"
    RESULT_URL = "https://www.fundamentus.com.br/resultado.php"
    
    # Critical Blue Chips fallback to ensure the crawler doesn't abort completely
    BLUE_CHIPS = [
        "PETR3", "PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "ABEV3", "JBSS3", 
        "SANB11", "MGLU3", "WEGE3", "RENT3", "SUZB3", "B3SA3", "LREN3", "HAPV3"
    ]
    
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

        tickers = []
        
        # Try primary URL
        try:
            tickers = self._fetch_from_url(self.LIST_URL)
        except Exception as e:
            logger.warning(f"Failed to fetch from primary URL: {e}")

        # Try secondary URL if primary failed
        if not tickers:
            try:
                logger.info("Trying secondary Fundamentus URL...")
                tickers = self._fetch_from_url(self.RESULT_URL)
            except Exception as e:
                logger.warning(f"Failed to fetch from secondary URL: {e}")

        if not tickers:
            logger.error("All ticker sources failed. Using Blue Chips fallback list.")
            unique_tickers = sorted(set(self.BLUE_CHIPS))
        else:
            clean_tickers = [t for t in tickers if t.isalnum() and 4 <= len(t) <= 6]
            unique_tickers = sorted(set(clean_tickers))

        # Update cache
        TickerService._cached_tickers = unique_tickers
        TickerService._last_fetch = time.time()

        logger.info(f"Successfully discovered {len(unique_tickers)} tickers.")
        return unique_tickers

    def _fetch_from_url(self, url: str) -> list[str]:
        response = self.request_manager.get(url, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')
        
        # Attempt to find tickers in links first (works for both URLs)
        links = soup.find_all("a", href=True)
        tickers = [
            link.text.strip()
            for link in links
            if "detalhes.php?papel=" in link["href"]
        ]
        
        # If no links, try to find in tables
        if not tickers:
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cols = row.find_all('td')
                    if cols and cols[0].find('a'):
                        tickers.append(cols[0].find('a').text.strip())
        
        return tickers
