from datetime import datetime, timedelta

import requests
from loguru import logger

from ..services.data_service import DataService


class MacroSpider:
    """
    Scrapes macroeconomic data from the Brazilian Central Bank (BCB) API.
    Essential for ML features like Interest Rates (SELIC) and Inflation (IPCA).
    """
    # BCB SGS API URLs
    SELIC_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados?formato=json"
    IPCA_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )

    def __init__(self, data_service: DataService):
        self.data_service = data_service

    def crawl_macro_indicators(self):
        logger.info("Fetching macroeconomic indicators from BCB...")

        try:
            # Get SELIC (last 30 days)
            end_date = datetime.now().strftime("%d/%m/%Y")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%d/%m/%Y")

            selic_uri = f"{self.SELIC_URL}&dataInicial={start_date}&dataFinal={end_date}"
            headers = {"User-Agent": self.USER_AGENT}

            response = requests.get(selic_uri, headers=headers, timeout=20)
            response.raise_for_status()
            selic_data = response.json()

            if selic_data:
                latest_selic = selic_data[-1]['valor']
                logger.info(f"Latest SELIC Rate: {latest_selic}%")

            # Get IPCA (last 2 months)
            ipca_response = requests.get(self.IPCA_URL, headers=headers, timeout=20)
            ipca_response.raise_for_status()

            if "application/json" in ipca_response.headers.get("Content-Type", ""):
                ipca_data = ipca_response.json()
                if ipca_data:
                    latest_ipca = ipca_data[-1]['valor']
                    logger.info(f"Latest IPCA (Inflation): {latest_ipca}%")
            else:
                logger.warning(f"IPCA API returned non-JSON content: {ipca_response.text[:100]}...")

        except Exception as e:
            logger.error(f"Failed to fetch macro data: {e}")
