import io
import os
import tempfile
import time
from pathlib import Path

import pandas as pd
from loguru import logger

from core.services.asset_classifier import classify_asset_type
from crawler.services.request_manager import RequestManager

_B3_TICKER_CSV_URL = "https://arquivos.b3.com.br/apinegocios/tickercsv"


def _default_cache_dir() -> Path:
    override = os.getenv("CVM_CACHE_DIR")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "cvm_cache"


class B3CatalogService:
    CACHE_TTL_HOURS = float(os.getenv("CVM_CACHE_TTL_HOURS", "24"))

    def __init__(
        self,
        request_manager: RequestManager | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.request_manager = request_manager or RequestManager()
        self.cache_dir = cache_dir or _default_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._df: pd.DataFrame | None = None

    def _cached_path(self, name: str) -> Path:
        return self.cache_dir / name

    def _is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        age_hours = (time.time() - path.stat().st_mtime) / 3600.0
        return age_hours < self.CACHE_TTL_HOURS

    def _get_catalog(self) -> pd.DataFrame | None:
        if self._df is not None:
            return self._df

        cached = self._cached_path("b3_ticker_catalog.csv")
        if not self._is_fresh(cached):
            try:
                response = self.request_manager.get(_B3_TICKER_CSV_URL, timeout=30)
                response.raise_for_status()
                # Empty response happens sometimes with B3, avoid writing empty cache
                if response.content:
                    cached.write_bytes(response.content)
            except Exception as exc:
                logger.error(f"B3CatalogService: download failed: {exc}")
                if not cached.exists():
                    return None

        if not cached.exists() or cached.stat().st_size == 0:
            return None

        try:
            # We try both separators as B3 sometimes uses ; and sometimes ,
            with open(cached, "rb") as f:
                content = f.read()
            try:
                df = pd.read_csv(io.BytesIO(content), sep=";", encoding="latin-1", dtype=str)
                if len(df.columns) < 2:
                    df = pd.read_csv(io.BytesIO(content), sep=",", encoding="latin-1", dtype=str)
            except Exception:
                df = pd.read_csv(io.BytesIO(content), sep=",", encoding="latin-1", dtype=str)

            # Normalize columns to the expected: ticker, instrument_type, isin, issuer_name
            # Typically B3 CSV has: TckrSymb, SgmtNm or MktNm, ISIN, CrpnNm or Nm
            issuer_keywords = ("crpn", "issuer", "empresa", "nome")
            col_map = {}
            for col in df.columns:
                lower_col = col.lower()
                if "tckr" in lower_col or "ticker" in lower_col:
                    col_map[col] = "ticker"
                elif "sgmt" in lower_col or "segment" in lower_col or "instrument" in lower_col:
                    col_map[col] = "instrument_type"
                elif "isin" in lower_col:
                    col_map[col] = "isin"
                elif any(kw in lower_col for kw in issuer_keywords):
                    col_map[col] = "issuer_name"

            df = df.rename(columns=col_map)

            # Ensure the requested columns exist even if empty
            for expected in ["ticker", "instrument_type", "isin", "issuer_name"]:
                if expected not in df.columns:
                    # Try by positional index if mapping failed
                    if expected == "ticker" and len(df.columns) > 0:
                        df = df.rename(columns={str(df.columns[0]): "ticker"})
                    elif expected == "instrument_type" and len(df.columns) > 1:
                        df = df.rename(columns={str(df.columns[1]): "instrument_type"})
                    else:
                        df[expected] = None

            # Clean strings
            for col in ["ticker", "instrument_type", "isin", "issuer_name"]:
                df[col] = df[col].astype(str).str.strip().replace("nan", None)

            df = df.dropna(subset=["ticker"])
            self._df = df
            return df
        except Exception as exc:
            logger.error(f"B3CatalogService: parse failed: {exc}")
            return None

    def list_tickers(self) -> list[str]:
        df = self._get_catalog()
        if df is None or df.empty:
            return []
        return df["ticker"].dropna().unique().tolist()

    def classify(self, symbol: str) -> str:
        df = self._get_catalog()
        if df is None or df.empty:
            return classify_asset_type(quote_type=None, symbol=symbol)

        row = df[df["ticker"] == symbol]
        if row.empty:
            return classify_asset_type(quote_type=None, symbol=symbol)

        instrument_type = row.iloc[0].get("instrument_type")
        quote_hint = (
            None if instrument_type is None or pd.isna(instrument_type) else str(instrument_type)
        )
        return classify_asset_type(quote_type=quote_hint, symbol=symbol)
