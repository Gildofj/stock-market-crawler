import asyncio
import datetime
import os
from typing import Any

import pandas as pd
import yfinance as yf
from loguru import logger

from core.models.schemas import StockPriceSchema

from ..models.contract import CrawlResult
from .base_spider import BaseSpider


class B3Spider(BaseSpider):
    async def crawl_batch_async(self, symbols: list[str]) -> dict[str, CrawlResult]:
        period = os.getenv("YF_HISTORY_PERIOD", "1y")

        yf_symbols = [f"{s}.SA" if not s.endswith(".SA") else s for s in symbols]
        logger.info(f"Batch crawling {len(yf_symbols)} tickers (period: {period})")

        def _download():
            return yf.download(
                yf_symbols, period=period, group_by="ticker", threads=True, progress=False
            )

        try:
            df = await asyncio.to_thread(_download)
            results = {}

            for symbol in symbols:
                yf_s = f"{symbol}.SA" if not symbol.endswith(".SA") else symbol
                ticker_df: pd.DataFrame = df[yf_s] if len(symbols) > 1 else df  # type: ignore[assignment] - Motivo: Injeção mock

                result = CrawlResult(symbol=symbol)
                if ticker_df is None or ticker_df.empty or ticker_df.dropna(how="all").empty:
                    results[symbol] = result
                    continue

                for index, row in ticker_df.dropna(subset=["Close"]).iterrows():  # type: ignore[arg-type] - Motivo: Mock incompatível
                    ts = pd.to_datetime(index)  # type: ignore[call-overload]
                    time_val: datetime.datetime = ts.to_pydatetime()  # type: ignore[union-attr]

                    result.prices.append(
                        StockPriceSchema(
                            time=time_val,
                            open=float(row["Open"]),  # type: ignore[arg-type] - Motivo: Mock incompatível
                            high=float(row["High"]),  # type: ignore[arg-type] - Motivo: Mock incompatível
                            low=float(row["Low"]),  # type: ignore[arg-type] - Motivo: Mock incompatível
                            close=float(row["Close"]),  # type: ignore[arg-type] - Motivo: Mock incompatível
                            adj_close=float(row.get("Adj Close", row["Close"])),  # type: ignore[arg-type] - Motivo: Mock incompatível
                            volume=int(row["Volume"]),  # type: ignore[arg-type] - Motivo: Mock incompatível
                        )
                    )
                results[symbol] = result

            return results
        except Exception as e:
            logger.error(f"B3 Batch Spider error: {e}")
            return {s: CrawlResult(symbol=s) for s in symbols}

    async def crawl_ticker(self, symbol: str) -> CrawlResult:
        period = os.getenv("YF_HISTORY_PERIOD", "1y")

        yf_symbol = f"{symbol}.SA" if not symbol.endswith(".SA") else symbol
        logger.info(f"Crawling ticker: {yf_symbol} (period: {period})")

        result = CrawlResult(symbol=symbol)
        ticker = yf.Ticker(yf_symbol)

        try:
            history = await asyncio.to_thread(ticker.history, period=period)

            if history.empty:
                logger.warning(
                    f"ACTION REQUIRED: {yf_symbol} is INACTIVE or DELISTED. Skipping collection."
                )
                return result

            vol_series = history["Volume"]
            recent_volume = float(vol_series.tail(5).sum())  # type: ignore - Motivo: Tipagem externa
            if recent_volume == 0:
                logger.warning(
                    f"ACTION REQUIRED: {yf_symbol} has NO TRADING VOLUME. Marking as INACTIVE."
                )
                result.is_active = 0

            info: dict[str, Any] = await asyncio.to_thread(lambda: ticker.info)

            display_name = str(info.get("longName") or info.get("shortName") or symbol)
            if display_name.upper() == symbol.upper():
                display_name = symbol.replace(".SA", "")

            result.name = display_name
            result.sector = str(info.get("sector")) if info.get("sector") else None
            result.sub_sector = str(info.get("industry")) if info.get("industry") else None
            result.segment = str(info.get("quoteType")) if info.get("quoteType") else None
            result.website = str(info.get("website")) if info.get("website") else None

            for index, row in history.iterrows():
                ts = pd.to_datetime(index)  # type: ignore - Motivo: Tipagem externa
                time_val: datetime.datetime = ts.to_pydatetime()

                result.prices.append(
                    StockPriceSchema(
                        time=time_val,
                        open=float(row["Open"]),  # type: ignore - Motivo: Tipagem externa
                        high=float(row["High"]),  # type: ignore - Motivo: Tipagem externa
                        low=float(row["Low"]),  # type: ignore - Motivo: Tipagem externa
                        close=float(row["Close"]),  # type: ignore - Motivo: Tipagem externa
                        adj_close=float(row.get("Adj Close", row["Close"])),  # type: ignore - Motivo: Tipagem externa
                        volume=int(row["Volume"]),  # type: ignore - Motivo: Tipagem externa
                    )
                )

            try:
                shares_series = await asyncio.to_thread(ticker.get_shares_full)
                if shares_series is not None and not shares_series.empty:
                    result.shares_outstanding = float(shares_series.iloc[-1])
            except Exception as exc:
                logger.warning(f"get_shares_full failed for {symbol}: {exc}")

            if result.shares_outstanding is None and info:
                shares_fallback = info.get("sharesOutstanding") or info.get(
                    "impliedSharesOutstanding"
                )
                if shares_fallback:
                    result.shares_outstanding = float(shares_fallback)

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

    def _to_float(self, val: Any) -> float | None:
        try:
            if val is None:
                return None
            return float(val)  # type: ignore - Motivo: Tipagem externa
        except (ValueError, TypeError):
            return None
