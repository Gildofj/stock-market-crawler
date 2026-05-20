import asyncio
import datetime
import os
from typing import Any

import pandas as pd
import yfinance as yf
from loguru import logger

from ..models.contract import CrawlResult
from ..models.schemas import StockPriceSchema
from .base_spider import BaseSpider


class B3Spider(BaseSpider):
    """
    Spider for extracting data from B3 (Brazilian Stock Exchange) using yfinance.

    This spider handles price history and basic company metadata.
    """

    async def crawl_batch_async(self, symbols: list[str]) -> dict[str, CrawlResult]:
        """Asynchronously crawls a batch of tickers from B3 using yfinance.download."""
        period = os.getenv("YF_HISTORY_PERIOD", "1y")

        # B3 symbols in yfinance need .SA suffix
        yf_symbols = [f"{s}.SA" if not s.endswith(".SA") else s for s in symbols]
        logger.info(f"Batch crawling {len(yf_symbols)} tickers (period: {period})")

        # yfinance download is synchronous
        def _download():
            return yf.download(
                yf_symbols, period=period, group_by="ticker", threads=True, progress=False
            )

        try:
            df = await asyncio.to_thread(_download)
            results = {}

            for symbol in symbols:
                yf_s = f"{symbol}.SA" if not symbol.endswith(".SA") else symbol
                ticker_df: pd.DataFrame = df[yf_s] if len(symbols) > 1 else df  # type: ignore[assignment]

                result = CrawlResult(symbol=symbol)
                if ticker_df is None or ticker_df.empty or ticker_df.dropna(how="all").empty:
                    results[symbol] = result
                    continue

                # Prices
                for index, row in ticker_df.dropna(subset=["Close"]).iterrows():  # type: ignore[arg-type]
                    ts = pd.to_datetime(index)  # type: ignore[call-overload]
                    time_val: datetime.datetime = ts.to_pydatetime()  # type: ignore[union-attr]

                    result.prices.append(
                        StockPriceSchema(
                            time=time_val,
                            open=float(row["Open"]),  # type: ignore[arg-type]
                            high=float(row["High"]),  # type: ignore[arg-type]
                            low=float(row["Low"]),  # type: ignore[arg-type]
                            close=float(row["Close"]),  # type: ignore[arg-type]
                            adj_close=float(row.get("Adj Close", row["Close"])),  # type: ignore[arg-type]
                            volume=int(row["Volume"]),  # type: ignore[arg-type]
                        )
                    )
                results[symbol] = result

            return results
        except Exception as e:
            logger.error(f"B3 Batch Spider error: {e}")
            return {s: CrawlResult(symbol=s) for s in symbols}

    def crawl_ticker(self, symbol: str) -> CrawlResult:
        """Synchronously crawls a ticker from B3 (yfinance)."""
        period = os.getenv("YF_HISTORY_PERIOD", "1y")

        # B3 symbols in yfinance need .SA suffix
        yf_symbol = f"{symbol}.SA" if not symbol.endswith(".SA") else symbol
        logger.info(f"Crawling ticker: {yf_symbol} (period: {period})")

        result = CrawlResult(symbol=symbol)
        ticker = yf.Ticker(yf_symbol)

        try:
            # Fast fail if no data (e.g. 404 Not Found or delisted)
            history = ticker.history(period=period)

            if history.empty:
                logger.warning(
                    f"ACTION REQUIRED: {yf_symbol} is INACTIVE or DELISTED. Skipping collection."
                )
                return result

            # Check for liquidity (last 5 trading days volume)
            vol_series = history["Volume"]
            recent_volume = float(vol_series.tail(5).sum())  # type: ignore
            if recent_volume == 0:
                logger.warning(
                    f"ACTION REQUIRED: {yf_symbol} has NO TRADING VOLUME. Marking as INACTIVE."
                )
                result.is_active = 0

            # 1. Company metadata (best-effort: Ticker.info is an undocumented
            # dict — only textual fields are read here, never numeric ones).
            info: dict[str, Any] = ticker.info

            # Priority: longName -> shortName -> symbol
            display_name = str(info.get("longName") or info.get("shortName") or symbol)
            if display_name.upper() == symbol.upper():
                display_name = symbol.replace(".SA", "")

            result.name = display_name
            result.sector = str(info.get("sector")) if info.get("sector") else None
            result.sub_sector = str(info.get("industry")) if info.get("industry") else None
            result.segment = str(info.get("quoteType")) if info.get("quoteType") else None
            result.website = str(info.get("website")) if info.get("website") else None

            # 2. Historical Prices
            for index, row in history.iterrows():
                # Handling pandas timestamp safely
                ts = pd.to_datetime(index)  # type: ignore
                time_val: datetime.datetime = ts.to_pydatetime()

                result.prices.append(
                    StockPriceSchema(
                        time=time_val,
                        open=float(row["Open"]),  # type: ignore
                        high=float(row["High"]),  # type: ignore
                        low=float(row["Low"]),  # type: ignore
                        close=float(row["Close"]),  # type: ignore
                        adj_close=float(row.get("Adj Close", row["Close"])),  # type: ignore
                        volume=int(row["Volume"]),  # type: ignore
                    )
                )

            # 3. Shares outstanding via the documented Ticker.get_shares_full()
            # API. Needed by the CVM-based calculator to convert absolute BRL
            # line items into per-share metrics. Falls back to None on failure;
            # the calculator already handles missing shares gracefully.
            try:
                shares_series = ticker.get_shares_full()
                if shares_series is not None and not shares_series.empty:
                    result.shares_outstanding = float(shares_series.iloc[-1])
            except Exception as exc:
                logger.warning(f"shares_outstanding unavailable for {symbol}: {exc}")

            # 4. Snapshot of quantitative .info fields — read for reconciliation
            # only. The CVMSpider (clean-room, CVM Dados Abertos) is the source
            # of truth that lands in `fundamentals`. This snapshot is consumed
            # by ReconciliationService and written to lake_indicator_reconciliation.
            result.yahoo_info_indicators = self._collect_info_snapshot(info)

        except Exception as e:
            logger.error(f"B3 Spider error for {symbol}: {e}")

        return result

    _INFO_INDICATOR_KEYS: tuple[str, ...] = (
        "forwardPE",
        "trailingPE",
        "priceToBook",
        "enterpriseToEbitda",
        "returnOnEquity",
        "dividendYield",
        "profitMargins",
        "debtToEbitda",
        "debtToEquity",
        "marketCap",
        "trailingEps",
    )

    def _collect_info_snapshot(self, info: dict[str, Any]) -> dict[str, float] | None:
        snapshot: dict[str, float] = {}
        for key in self._INFO_INDICATOR_KEYS:
            value = self._to_float(info.get(key))
            if value is not None:
                snapshot[key] = value
        return snapshot or None

    async def crawl_ticker_async(self, symbol: str) -> CrawlResult:
        """Asynchronously crawls a ticker from B3 (yfinance)."""
        # yfinance is synchronous, so we run it in a thread pool
        return await asyncio.to_thread(self.crawl_ticker, symbol)

    def _to_float(self, val: Any) -> float | None:
        """Safely converts a value to float."""
        try:
            if val is None:
                return None
            # Handle potential pandas types or other numeric types
            return float(val)  # type: ignore
        except (ValueError, TypeError):
            return None
