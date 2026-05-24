"""Unit tests for FIISpider and BDRSpider routing/parsing."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from crawler.models.contract import CrawlResult
from crawler.spiders.bdr_spider import BDRSpider
from crawler.spiders.fii_spider import FIISpider


@pytest.mark.asyncio
async def test_fii_spider_populates_from_yfinance():
    spider = FIISpider()
    result = CrawlResult(symbol="MXRF11")

    fake_info = {
        "longName": "Maxi Renda FII",
        "sector": "Real Estate",
        "industry": "REIT",
        "priceToBook": 0.95,
        "trailingEps": 0.12,
        "dividendYield": 0.102,
        "marketCap": 1_500_000_000.0,
    }

    with patch(
        "crawler.spiders.fii_spider._fetch_yfinance_info",
        return_value=fake_info,
    ):
        await spider.enrich(result)

    # yfinance fraction to percentage
    assert result.dy == pytest.approx(10.2)
    assert result.p_vp == pytest.approx(0.95)
    assert result.market_cap == pytest.approx(1_500_000_000.0)
    assert result.segment == "FII"
    assert result.provenance["asset_type"] == "FII"
    assert result.provenance["source"] == "yfinance"


@pytest.mark.asyncio
async def test_fii_spider_handles_missing_yfinance_response():
    spider = FIISpider()
    result = CrawlResult(symbol="MXRF11")

    with patch(
        "crawler.spiders.fii_spider._fetch_yfinance_info",
        return_value={},
    ):
        await spider.enrich(result)

    assert result.dy is None
    assert "asset_type" not in result.provenance


@pytest.mark.asyncio
async def test_bdr_spider_uses_explicit_underlying():
    spider = BDRSpider()

    fake_info = {
        "longName": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "trailingPE": 30.0,
        "priceToBook": 50.0,
        "returnOnEquity": 1.5,  # yfinance fraction
        "profitMargins": 0.25,  # yfinance fraction
        "marketCap": 3_000_000_000_000.0,
        "trailingEps": 6.5,
        "dividendYield": 0.005,
    }
    with patch(
        "crawler.spiders.bdr_spider._fetch_underlying_info",
        return_value=fake_info,
    ):
        result = CrawlResult(symbol="AAPL34")
        await spider.enrich(result, underlying="AAPL", ratio=100.0)

    assert result.p_l == pytest.approx(30.0)
    assert result.p_vp == pytest.approx(50.0)
    # yfinance fractions are converted to percentage (BR convention).
    assert result.roe == pytest.approx(150.0)
    assert result.net_margin == pytest.approx(25.0)
    # EPS is scaled by 1/ratio to reflect the BR-listed share, not the foreign one.
    assert result.eps == pytest.approx(6.5 / 100.0)
    assert result.provenance["underlying_ticker"] == "AAPL"
    assert result.provenance["bdr_ratio"] == "100.0"


@pytest.mark.asyncio
async def test_bdr_spider_warns_when_underlying_missing():
    spider = BDRSpider()
    result = CrawlResult(symbol="AAPL34")
    await spider.enrich(result)
    # No underlying resolvable → enrichment skipped.
    assert result.p_l is None
    assert result.eps is None
