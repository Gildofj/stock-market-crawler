import requests
from bs4 import BeautifulSoup
from loguru import logger
from .request_manager import RequestManager

class TickerService:
    # This URL provides a CSV-like display of all companies in Fundamentus
    LIST_URL = "https://www.fundamentus.com.br/detalhes.php"

    def __init__(self):
        self.request_manager = RequestManager()

    def get_all_tickers(self) -> list[str]:
        """
        Scrapes all available tickers from Fundamentus.
        """
        logger.info("Fetching all active tickers from B3 via Fundamentus...")
        
        try:
            response = self.request_manager.get(self.LIST_URL, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find the main table with all symbols
            # Symbols are usually inside <a> tags in the first column of each row
            table = soup.find('table', {'id': 'testesu'})
            if not table:
                logger.warning("Could not find the ticker table. Using fallback method.")
                # Fallback: Find all links that look like ticker details
                links = soup.find_all('a', href=True)
                tickers = [link.text.strip() for link in links if 'detalhes.php?papel=' in link['href']]
            else:
                tickers = [row.find('a').text.strip() for row in table.find_all('tr')[1:] if row.find('a')]

            # Clean and filter only alphanumeric tickers (usually 5 or 6 chars)
            clean_tickers = [t for t in tickers if t.isalnum() and 4 <= len(t) <= 6]
            
            unique_tickers = sorted(list(set(clean_tickers)))
            logger.info(f"Successfully discovered {len(unique_tickers)} tickers.")
            
            return unique_tickers

        except Exception as e:
            logger.error(f"Failed to fetch ticker list: {e}")
            return []
