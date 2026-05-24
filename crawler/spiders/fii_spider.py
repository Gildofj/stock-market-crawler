"""Spider for Brazilian REITs (FIIs — Fundos de Investimento Imobiliário).

FIIs don't file DFP/ITR like a S/A would, so the CVMSpider has nothing useful
to say about them. Brapi exposes monthly informe data through its
``defaultKeyStatistics`` and ``fundsData`` modules — that's the canonical
source for DY, P/VP and net asset value.

Persisted shape mirrors EQUITY fundamentals where the field makes sense
(DY, P/VP, market_cap), leaves the rest null, and stamps ``asset_type='FII'``
so the discriminator lets cross-asset reports filter correctly.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from core.services.brapi_client import (
    BrapiClient,
    BrapiQuotaExceededError,
    BrapiUnauthorizedError,
    get_brapi_client,
)

from ..models.contract import CrawlResult
from .base_spider import BaseSpider

_MODULES = ("defaultKeyStatistics", "fundsData", "summaryProfile")


class FIISpider(BaseSpider):
    def __init__(self, client: BrapiClient | None = None) -> None:
        self._client = client or get_brapi_client()

    async def crawl_ticker(self, symbol: str) -> CrawlResult:
        result = CrawlResult(symbol=symbol)
        await self.enrich(result)
        return result

    async def enrich(self, result: CrawlResult) -> None:
        if not self._client.enabled:
            logger.warning(
                f"FIISpider: BRAPI_TOKEN not configured; skipping enrichment for {result.symbol}"
            )
            return

        try:
            quote = await asyncio.to_thread(
                self._client.fetch_quote, result.symbol, _MODULES
            )
        except BrapiUnauthorizedError:
            logger.warning(f"FIISpider: Brapi auth failed for {result.symbol}")
            return
        except BrapiQuotaExceededError:
            logger.warning(f"FIISpider: Brapi quota exhausted; skipping {result.symbol}")
            return

        if quote is None:
            logger.info(f"FIISpider: no Brapi data for {result.symbol}")
            return

        raw = quote.raw or {}
        stats = raw.get("defaultKeyStatistics") or {}
        funds = raw.get("fundsData") or {}

        if result.name is None or result.name == result.symbol:
            result.name = quote.long_name or result.name

        result.sector = result.sector or quote.sector or "Real Estate"
        result.sub_sector = result.sub_sector or quote.industry
        result.segment = result.segment or "FII"

        result.market_cap = result.market_cap or quote.market_cap or _to_float(
            stats.get("netAssetsCurrent")
        )
        result.p_vp = result.p_vp or _to_float(stats.get("priceToBook")) or _to_float(
            funds.get("priceToBook")
        )
        # FIIs report DY as a percentage already (12.5 == 12.5% over 12m).
        result.dy = result.dy or _to_float(funds.get("dividendYield")) or _to_float(
            stats.get("trailingAnnualDividendYield")
        )
        result.eps = result.eps or _to_float(stats.get("trailingEps"))

        result.provenance.setdefault("asset_type", "FII")
        result.provenance.setdefault("brapi_modules", ",".join(_MODULES))


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
