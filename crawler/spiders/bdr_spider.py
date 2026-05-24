"""Spider for Brazilian Depositary Receipts (BDRs, suffix 32/33/34/35).

A BDR is a wrapper around a foreign equity (AAPL34 → AAPL, MSFT34 → MSFT).
Fundamentals live with the underlying issuer, so:

1. Resolve the underlying ticker (from companies.underlying_ticker cached by
   refresh_universe).
2. Pull underlying fundamentals via yfinance (already a project dependency).
3. Apply the BDR ratio so per-share metrics (EPS, market_cap) reflect the
   BR-listed share, not the foreign one.

Persisted with ``asset_type='BDR'`` so consumers can distinguish a BR-listed
EPS-in-BRL row from a US-native EPS-in-USD row.
"""

from __future__ import annotations

import asyncio
from typing import Any

import yfinance as yf
from loguru import logger

from ..models.contract import CrawlResult
from .base_spider import BaseSpider


class BDRSpider(BaseSpider):
    async def crawl_ticker(
        self,
        symbol: str,
        underlying: str | None = None,
        ratio: float | None = None,
    ) -> CrawlResult:
        result = CrawlResult(symbol=symbol)
        await self.enrich(result, underlying=underlying, ratio=ratio)
        return result

    async def enrich(
        self,
        result: CrawlResult,
        underlying: str | None = None,
        ratio: float | None = None,
    ) -> None:
        resolved_underlying = underlying
        bdr_ratio = ratio

        if not resolved_underlying:
            logger.warning(
                f"BDRSpider: no underlying ticker resolvable for {result.symbol}; "
                "skipping enrichment"
            )
            return

        info = await asyncio.to_thread(_fetch_underlying_info, resolved_underlying)
        if not info:
            logger.warning(
                f"BDRSpider: yfinance returned nothing for underlying "
                f"{resolved_underlying} (BDR {result.symbol})"
            )
            return

        if result.name is None or result.name == result.symbol:
            result.name = info.get("longName") or info.get("shortName") or result.symbol
        result.sector = result.sector or info.get("sector")
        result.sub_sector = result.sub_sector or info.get("industry")
        result.segment = result.segment or "BDR"

        # Per-share metrics get scaled by the ratio so they reflect the BR-listed share.
        # market_cap is left in USD (issuer-level) — consumers convert if they need BRL.
        scale = bdr_ratio if bdr_ratio and bdr_ratio > 0 else 1.0

        result.p_l = result.p_l or _scale(info.get("trailingPE"), 1.0)
        result.p_vp = result.p_vp or _scale(info.get("priceToBook"), 1.0)
        result.ev_ebitda = result.ev_ebitda or _scale(info.get("enterpriseToEbitda"), 1.0)
        result.roe = result.roe or _percent(info.get("returnOnEquity"))
        result.net_margin = result.net_margin or _percent(info.get("profitMargins"))
        result.market_cap = result.market_cap or _scale(info.get("marketCap"), 1.0)
        result.eps = result.eps or _scale(info.get("trailingEps"), 1.0 / scale)
        result.dy = result.dy or _percent(info.get("dividendYield"))

        result.provenance.setdefault("asset_type", "BDR")
        result.provenance.setdefault("underlying_ticker", resolved_underlying)
        result.provenance.setdefault("bdr_ratio", str(bdr_ratio or "unknown"))



def _fetch_underlying_info(underlying_ticker: str) -> dict[str, Any]:
    try:
        ticker = yf.Ticker(underlying_ticker)
        return ticker.info or {}
    except Exception as exc:
        logger.warning(f"BDRSpider: yfinance lookup failed for {underlying_ticker}: {exc}")
        return {}


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _scale(value: Any, factor: float) -> float | None:
    parsed = _to_float(value)
    if parsed is None:
        return None
    return parsed * factor


def _percent(value: Any) -> float | None:
    # yfinance returns fractions for rates (0.25 == 25%); BR convention stores % directly.
    parsed = _to_float(value)
    if parsed is None:
        return None
    return parsed * 100.0
