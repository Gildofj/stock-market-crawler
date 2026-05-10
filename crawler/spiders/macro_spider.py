from datetime import datetime, timedelta

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

        # BCB daily series (like SELIC) require a date window (max 10 years)
        # We'll fetch the last 90 days to ensure we get the latest data,
        # especially for monthly indicators like IPCA which are dated on the 1st of the month.
        end_date = datetime.now().strftime("%d/%m/%Y")
        start_date = (datetime.now() - timedelta(days=90)).strftime("%d/%m/%Y")

        selic_url = f"{self.SELIC_URL}&dataInicial={start_date}&dataFinal={end_date}"
        ipca_url = f"{self.IPCA_URL}&dataInicial={start_date}&dataFinal={end_date}"

        headers = {"Accept": "application/json"}

        try:
            # 1. Fetch SELIC
            selic_response = self.request_manager.get(selic_url, headers=headers, timeout=20)
            if selic_response.status_code == 404:
                logger.warning(f"No SELIC data found for the period {start_date} to {end_date}.")
            else:
                selic_response.raise_for_status()
                selic_data = selic_response.json()
                if selic_data:
                    latest_selic = selic_data[-1]["valor"]
                    logger.info(f"Latest SELIC Rate: {latest_selic}%")

            # 2. Fetch IPCA
            ipca_response = self.request_manager.get(ipca_url, headers=headers, timeout=20)
            if ipca_response.status_code == 404:
                logger.warning(f"No IPCA data found for the period {start_date} to {end_date}.")
            else:
                ipca_response.raise_for_status()
                if "application/json" in ipca_response.headers.get("Content-Type", ""):
                    ipca_data = ipca_response.json()
                    if ipca_data:
                        latest_ipca = ipca_data[-1]["valor"]
                        logger.info(f"Latest IPCA (Inflation): {latest_ipca}%")
                else:
                    logger.warning("IPCA API returned non-JSON content.")

        except Exception as e:
            logger.error(f"Failed to fetch macro data: {e}")
