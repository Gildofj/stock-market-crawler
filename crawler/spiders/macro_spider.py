from datetime import datetime

from loguru import logger

from ..services.data_service import DataService
from ..services.request_manager import RequestManager


class MacroSpider:
    """
    Scrapes macroeconomic data from the Brazilian Central Bank (BCB) API.
    Essential for ML features like Interest Rates (SELIC) and Inflation (IPCA).
    """
    # BCB SGS API URLs
    SELIC_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados?formato=json"
    IPCA_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json"

    def __init__(self, data_service: DataService, request_manager: RequestManager = None):
        self.data_service = data_service
        self.request_manager = request_manager or RequestManager()

    def crawl_macro_indicators(self):
        logger.info("Fetching macroeconomic indicators from BCB...")

        try:
            # 1. Fetch SELIC
            selic_response = self.request_manager.get(self.SELIC_URL, timeout=20)
            selic_response.raise_for_status()
            selic_data = selic_response.json()

            if selic_data:
                latest_selic = selic_data[-1]['valor']
                logger.info(f"Latest SELIC Rate: {latest_selic}%")

            # 2. Fetch IPCA
            ipca_response = self.request_manager.get(self.IPCA_URL, timeout=20)
            ipca_response.raise_for_status()

            if "application/json" in ipca_response.headers.get("Content-Type", ""):
                ipca_data = ipca_response.json()
                if ipca_data:
                    latest_ipca = ipca_data[-1]['valor']
                    logger.info(f"Latest IPCA (Inflation): {latest_ipca}%")
            else:
                logger.warning(f"IPCA API returned non-JSON content.")

        except Exception as e:
            logger.error(f"Failed to fetch macro data: {e}")
