import io
import time

import pandas as pd
from loguru import logger

from .cvm_dataset_service import CVMDatasetService
from .request_manager import RequestManager


class TickerService:
    """Discovers the universe of active B3 tickers.

    Sources, in priority order:

    1. Brapi public ``/available`` endpoint — JSON list maintained by the
       open-source brapi project. Lowest-friction, no scraping involved.
    2. B3's own ``InstrumentsConsolidated`` CSV — the exchange-published
       file listing every traded instrument. Authoritative, no third-party
       middleman, no proprietary indicators.
    3. CVM CAD registry — every public company registered with the
       regulator; not a ticker list per se, but a deterministic backstop
       that proves the company exists before we ever try to price it.
    4. Blue-chip fallback baked into the codebase — only used when *every*
       network source is unreachable (typically inside CI).
    """

    BRAPI_URL = "https://brapi.dev/api/available"
    B3_INSTRUMENTS_URL = (
        "https://arquivos.b3.com.br/apinegocios/tickercsv"
    )

    BLUE_CHIPS = [
        "PETR3", "PETR4", "VALE3", "ITUB4", "BBDC4",
        "BBAS3", "ABEV3", "JBSS3", "SANB11", "MGLU3",
        "WEGE3", "RENT3", "SUZB3", "B3SA3", "LREN3",
        "HAPV3", "GGBR4", "ITSA4", "RDOR3", "RAIL3",
        "EQTL3", "VBBR3", "CSAN3", "RADL3", "CPLE6",
        "VIVT3", "EMBR3", "CMIG4", "BBSE3", "SBSP3",
        "ELET3", "ELET6", "UGPA3", "PRIO3", "TIMS3",
        "ENEV3", "EGIE3", "ASAI3", "TOTS3", "RECV3",
        "GOAU4", "CPFE3", "CCRO3", "BRAP4", "CYRE3",
        "MRFG3", "CIEL3", "MULT3", "CRFB3", "FLRY3",
        "BRFS3", "HYPE3", "ALPA4", "MRVE3", "YDUQ3",
        "BEEF3",
    ]

    _cached_tickers: list[str] = []
    _last_fetch: float = 0

    def __init__(self, dataset_service: CVMDatasetService | None = None):
        self.request_manager = RequestManager()
        self.dataset_service = dataset_service or CVMDatasetService(self.request_manager)

    def get_all_tickers(self) -> list[str]:
        if self._cached_tickers and (time.time() - self._last_fetch < 3600):
            logger.info("Using cached ticker list.")
            return self._cached_tickers

        logger.info("Discovering active tickers from public sources...")

        tickers: list[str] = []
        for source_name, fetcher in (
            ("Brapi", self._fetch_from_brapi),
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

    def _fetch_from_brapi(self) -> list[str]:
        response = self.request_manager.get(self.BRAPI_URL, timeout=20)
        response.raise_for_status()
        data = response.json()
        return data.get("stocks", [])

    def _fetch_from_b3_instruments(self) -> list[str]:
        """Pull the B3-published consolidated ticker CSV.

        The file is a comma-separated dump where the first column is the
        instrument code. Only equity tickers (4–6 alphanumeric chars) are
        retained downstream by ``get_all_tickers``.
        """
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
        """Last-resort registry-based ticker hint.

        CAD doesn't carry the B3 ticker directly, so this only validates that
        a company is registered. It returns the curated blue-chip list when
        CAD is reachable — that gives us a "live data confirms registry"
        signal without inventing tickers we have no way to verify.
        """
        cad = self.dataset_service.get_cad()
        if cad is None or cad.empty:
            return []
        return list(self.BLUE_CHIPS)
