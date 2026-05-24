"""Spider for Brazilian REITs (FIIs — Fundos de Investimento Imobiliário).

FIIs don't file DFP/ITR like a S/A would, so the CVMSpider has nothing useful
to say about them. We now rely on yfinance for base indicators.

Persisted shape mirrors EQUITY fundamentals where the field makes sense
(DY, P/VP, market_cap), leaves the rest null, and stamps ``asset_type='FII'``
so the discriminator lets cross-asset reports filter correctly.
"""

from __future__ import annotations

import asyncio
from typing import Any

import yfinance as yf
from loguru import logger

from crawler.services.metadata_overrides import get_override

from ..models.contract import CrawlResult
from .base_spider import BaseSpider


class FIISpider(BaseSpider):
    def __init__(self) -> None:
        pass

    async def crawl_ticker(self, symbol: str) -> CrawlResult:
        result = CrawlResult(symbol=symbol)
        await self.enrich(result)
        return result

    async def enrich(self, result: CrawlResult) -> None:
        info = await asyncio.to_thread(_fetch_yfinance_info, result.symbol)

        if not info:
            logger.warning(f"FIISpider: no yfinance data for {result.symbol}")
            return

        if result.name is None or result.name == result.symbol:
            result.name = info.get("longName") or info.get("shortName") or result.name

        result.sector = "Real Estate"

        override = get_override(result.symbol)
        result.sub_sector = override.get("sub_sector") or info.get("industry")
        result.segment = result.segment or "FII"

        result.market_cap = result.market_cap or _to_float(info.get("marketCap"))
        result.p_vp = result.p_vp or _to_float(info.get("priceToBook"))

        # yfinance returns fraction for DY, multiply by 100
        dy = _to_float(info.get("dividendYield"))
        if dy is not None:
            result.dy = result.dy or (dy * 100.0)

        result.eps = result.eps or _to_float(info.get("trailingEps"))

        result.provenance.setdefault("asset_type", "FII")
        result.provenance.setdefault("source", "yfinance")


def _fetch_yfinance_info(symbol: str) -> dict[str, Any]:
    try:
        ticker = yf.Ticker(f"{symbol}.SA")
        return ticker.info or {}
    except Exception as exc:
        logger.warning(f"FIISpider: yfinance lookup failed for {symbol}.SA: {exc}")
        return {}


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
