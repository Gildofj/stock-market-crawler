import io
import time

import pandas as pd
from loguru import logger

from .cvm_dataset_service import CVMDatasetService
from .request_manager import RequestManager


class TickerService:
    B3_INSTRUMENTS_URL = "https://arquivos.b3.com.br/apinegocios/tickercsv"

    BLUE_CHIPS = [
        "PETR3",
        "PETR4",
        "VALE3",
        "ITUB4",
        "BBDC4",
        "BBAS3",
        "ABEV3",
        "JBSS3",
        "SANB11",
        "MGLU3",
        "WEGE3",
        "RENT3",
        "SUZB3",
        "B3SA3",
        "LREN3",
        "HAPV3",
        "GGBR4",
        "ITSA4",
        "RDOR3",
        "RAIL3",
        "EQTL3",
        "VBBR3",
        "CSAN3",
        "RADL3",
        "CPLE6",
        "VIVT3",
        "EMBR3",
        "CMIG4",
        "BBSE3",
        "SBSP3",
        "ELET3",
        "ELET6",
        "UGPA3",
        "PRIO3",
        "TIMS3",
        "ENEV3",
        "EGIE3",
        "ASAI3",
        "TOTS3",
        "RECV3",
        "GOAU4",
        "CPFE3",
        "CCRO3",
        "BRAP4",
        "CYRE3",
        "MRFG3",
        "CIEL3",
        "MULT3",
        "CRFB3",
        "FLRY3",
        "BRFS3",
        "HYPE3",
        "ALPA4",
        "MRVE3",
        "YDUQ3",
        "BEEF3",
    ]

    _cached_tickers: list[str] = []
    _last_fetch: float = 0

    def __init__(self, dataset_service: CVMDatasetService | None = None):
        from core.config import settings

        proxies = []
        if settings.CRAWLER_HTTP_PROXY:
            proxies.append(settings.CRAWLER_HTTP_PROXY)
        if settings.CRAWLER_HTTPS_PROXY:
            proxies.append(settings.CRAWLER_HTTPS_PROXY)

        self.request_manager = RequestManager(proxies=proxies if proxies else None)
        self.dataset_service = dataset_service or CVMDatasetService(self.request_manager)

    def get_all_tickers(self) -> list[str]:
        if self._cached_tickers and (time.time() - self._last_fetch < 3600):
            logger.info("Using cached ticker list.")
            return self._cached_tickers

        logger.info("Discovering active tickers from public sources...")

        tickers: list[str] = []
        for source_name, fetcher in (
            ("B3 instruments CSV", self._fetch_from_b3_instruments),
            ("CVM CAD registry", self._fetch_from_cvm_cad),
        ):
            try:
                logger.info(f"Trying {source_name}...")
                tickers = fetcher()
                if tickers:
                    break
            except Exception as exc:
                logger.warning(f"{source_name} failed: {exc}")

        if not tickers:
            logger.error("All dynamic sources failed. Using Blue Chips fallback.")
            unique_tickers = sorted(set(self.BLUE_CHIPS))
        else:
            clean_tickers = [t for t in tickers if t.isalnum() and 4 <= len(t) <= 6]
            unique_tickers = sorted(set(clean_tickers))

        TickerService._cached_tickers = unique_tickers
        TickerService._last_fetch = time.time()

        logger.info(f"Successfully discovered {len(unique_tickers)} tickers.")
        return unique_tickers


    def _fetch_from_b3_instruments(self) -> list[str]:
        response = self.request_manager.get(self.B3_INSTRUMENTS_URL, timeout=30)
        response.raise_for_status()
        try:
            df = pd.read_csv(io.BytesIO(response.content), encoding="latin-1")
        except Exception:
            return []
        if df.empty:
            return []
        first_col = df.columns[0]
        return [str(v).strip() for v in df[first_col].dropna()]

    def _fetch_from_cvm_cad(self) -> list[str]:
        cad = self.dataset_service.get_cad()
        if cad is None or cad.empty:
            return []
        return list(self.BLUE_CHIPS)
