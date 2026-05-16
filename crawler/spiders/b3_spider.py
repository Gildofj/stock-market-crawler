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

            # 1. Company Metadata
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

            # 3. Fundamentals
            result.p_l = self._to_float(info.get("forwardPE") or info.get("trailingPE"))
            result.p_vp = self._to_float(info.get("priceToBook"))
            result.ev_ebitda = self._to_float(info.get("enterpriseToEbitda"))

            roe_val = self._to_float(info.get("returnOnEquity"))
            result.roe = roe_val * 100 if roe_val is not None else None

            dy_val = self._to_float(info.get("dividendYield"))
            result.dy = dy_val * 100 if dy_val is not None else 0.0

            margin_val = self._to_float(info.get("profitMargins"))
            result.net_margin = margin_val * 100 if margin_val is not None else None

            result.liquid_debt_ebitda = self._to_float(info.get("debtToEbitda"))
            result.debt_to_equity = self._to_float(info.get("debtToEquity"))
            result.market_cap = self._to_float(info.get("marketCap"))
            result.eps = self._to_float(info.get("trailingEps"))

        except Exception as e:
            logger.error(f"B3 Spider error for {symbol}: {e}")

        return result

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
