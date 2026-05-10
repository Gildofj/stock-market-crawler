import asyncio
import re
from typing import Any

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

    def crawl_ticker(self, symbol: str) -> CrawlResult:
        """Synchronously crawls a ticker from B3 (yfinance)."""
        # B3 symbols in yfinance need .SA suffix
        yf_symbol = f"{symbol}.SA" if not symbol.endswith(".SA") else symbol
        logger.info(f"Crawling ticker: {yf_symbol}")

        result = CrawlResult(symbol=symbol)
        ticker = yf.Ticker(yf_symbol)

        try:
            # Fast fail if no data (e.g. 404 Not Found or delisted)
            history = ticker.history(period="1y")

            if history.empty:
                logger.warning(
                    f"ACTION REQUIRED: {yf_symbol} is INACTIVE or DELISTED. Skipping collection."
                )
                return result

            # Check for liquidity (last 5 trading days volume)
            vol_series = history["Volume"]
            recent_volume = float(vol_series.tail(5).sum()) # type: ignore
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
            import pandas as pd
            for index, row in history.iterrows():
                # Handling pandas timestamp safely
                import datetime
                
                # Use pd.to_datetime to ensure we have a timestamp
                ts = pd.to_datetime(index) # type: ignore
                time_val: datetime.datetime = ts.to_pydatetime()
                
                result.prices.append(
                    StockPriceSchema(
                        time=time_val,
                        open=float(row["Open"]), # type: ignore
                        high=float(row["High"]), # type: ignore
                        low=float(row["Low"]), # type: ignore
                        close=float(row["Close"]), # type: ignore
                        adj_close=float(row.get("Adj Close", row["Close"])), # type: ignore
                        volume=int(row["Volume"]), # type: ignore
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
            return float(val) # type: ignore
        except (ValueError, TypeError):
            return None
