import requests
from loguru import logger
from datetime import datetime, timedelta
from ..services.data_service import DataService

class MacroSpider:
    """
    Scrapes macroeconomic data from the Brazilian Central Bank (BCB) API.
    Essential for ML features like Interest Rates (SELIC) and Inflation (IPCA).
    """
    # BCB SGS API URLs
    SELIC_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados?formato=json" # SELIC daily
    IPCA_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json" # IPCA monthly

    def __init__(self, data_service: DataService):
        self.data_service = data_service

    def crawl_macro_indicators(self):
        logger.info("Fetching macroeconomic indicators from BCB...")
        
        # In a real scenario, we would save this to a 'macro_indicators' table
        # For now, let's ensure we can at least fetch the most recent values
        try:
            # Get SELIC (last 30 days)
            end_date = datetime.now().strftime("%d/%m/%Y")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%d/%m/%Y")
            
            selic_uri = f"{self.SELIC_URL}&dataInicial={start_date}&dataFinal={end_date}"
            response = requests.get(selic_uri, timeout=10)
            selic_data = response.json()
            
            if selic_data:
                latest_selic = selic_data[-1]['valor']
                logger.info(f"Latest SELIC Rate: {latest_selic}%")
                # TODO: Implement save_macro_data in DataService
            
            # Get IPCA (last 2 months)
            ipca_response = requests.get(self.IPCA_URL, timeout=10)
            ipca_data = ipca_response.json()
            if ipca_data:
                latest_ipca = ipca_data[-1]['valor']
                logger.info(f"Latest IPCA (Inflation): {latest_ipca}%")

        except Exception as e:
            logger.error(f"Failed to fetch macro data: {e}")
