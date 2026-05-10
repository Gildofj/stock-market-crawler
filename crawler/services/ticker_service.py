import time

from bs4 import BeautifulSoup
from loguru import logger

from .request_manager import RequestManager


class TickerService:
    # URL configurations
    FUNDAMENTUS_LIST_URL = "https://www.fundamentus.com.br/detalhes.php"
    FUNDAMENTUS_RESULT_URL = "https://www.fundamentus.com.br/resultado.php"
    STATUS_INVEST_URL = "https://statusinvest.com.br/category/advancedsearchresult?CategoryType=1&search={}"
    
    # Expanded Blue Chips fallback (Top 50+ by relevance/volume)
    BLUE_CHIPS = [
        "PETR3", "PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "ABEV3", "JBSS3", 
        "SANB11", "MGLU3", "WEGE3", "RENT3", "SUZB3", "B3SA3", "LREN3", "HAPV3",
        "GGBR4", "ITSA4", "RDOR3", "RAIL3", "EQTL3", "VBBR3", "CSAN3", "RADL3",
        "CPLE6", "VIVT3", "EMBR3", "CMIG4", "BBSE3", "SBSP3", "ELET3", "ELET6",
        "UGPA3", "PRIO3", "TIMS3", "ENEV3", "EGIE3", "ASAI3", "TOTS3", "RECV3",
        "GOAU4", "CPFE3", "CCRO3", "BRAP4", "CYRE3", "MRFG3", "CIEL3", "MULT3",
        "CRFB3", "FLRY3", "BRFS3", "HYPE3", "ALPA4", "MRVE3", "YDUQ3", "BEEF3"
    ]
    
    _cached_tickers = []
    _last_fetch = 0

    def __init__(self):
        self.request_manager = RequestManager()

    def get_all_tickers(self) -> list[str]:
        """
        Scrapes all available tickers from multiple sources with in-memory caching.
        Sources: Fundamentus (2 URLs), StatusInvest, and Blue Chips Fallback.
        """
        # Cache for 1 hour
        if self._cached_tickers and (time.time() - self._last_fetch < 3600):
            logger.info("Using cached ticker list.")
            return self._cached_tickers

        logger.info("Discovering active tickers from B3...")

        tickers = []
        
        # 1. Try Fundamentus Primary
        try:
            tickers = self._fetch_from_fundamentus(self.FUNDAMENTUS_LIST_URL)
        except Exception as e:
            logger.warning(f"Fundamentus Primary failed: {e}")

        # 2. Try StatusInvest (JSON API - usually more robust)
        if not tickers:
            try:
                logger.info("Trying StatusInvest source...")
                tickers = self._fetch_from_statusinvest()
            except Exception as e:
                logger.warning(f"StatusInvest failed: {e}")

        # 3. Try Fundamentus Secondary
        if not tickers:
            try:
                logger.info("Trying Fundamentus secondary source...")
                tickers = self._fetch_from_fundamentus(self.FUNDAMENTUS_RESULT_URL)
            except Exception as e:
                logger.warning(f"Fundamentus Secondary failed: {e}")

        if not tickers:
            logger.error("All dynamic sources failed (possible GitHub Action block). Using expanded Blue Chips list.")
            unique_tickers = sorted(set(self.BLUE_CHIPS))
        else:
            clean_tickers = [t for t in tickers if t.isalnum() and 4 <= len(t) <= 6]
            unique_tickers = sorted(set(clean_tickers))

        # Update cache
        TickerService._cached_tickers = unique_tickers
        TickerService._last_fetch = time.time()

        logger.info(f"Successfully discovered {len(unique_tickers)} tickers.")
        return unique_tickers

    def _fetch_from_fundamentus(self, url: str) -> list[str]:
        response = self.request_manager.get(url, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')
        links = soup.find_all("a", href=True)
        return [link.text.strip() for link in links if "detalhes.php?papel=" in link["href"]]

    def _fetch_from_statusinvest(self) -> list[str]:
        headers = {
            "Referer": "https://statusinvest.com.br/acoes/busca-avancada",
            "X-Requested-With": "XMLHttpRequest"
        }
        response = self.request_manager.get(self.STATUS_INVEST_URL, headers=headers, timeout=20)
        response.raise_for_status()
        
        data = response.json()
        if isinstance(data, list):
            return [item.get("ticker") for item in data if item.get("ticker")]
        return []
