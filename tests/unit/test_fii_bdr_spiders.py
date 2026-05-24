"""Unit tests for FIISpider and BDRSpider routing/parsing."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from core.services.brapi_client import BrapiClient, BrapiQuote
from crawler.models.contract import CrawlResult
from crawler.spiders.bdr_spider import BDRSpider
from crawler.spiders.fii_spider import FIISpider


def _make_client(quote: BrapiQuote | None = None, enabled: bool = True) -> BrapiClient:
    client = BrapiClient(token="t" if enabled else None, monthly_budget=1000)
    client.fetch_quote = lambda *_args, **_kwargs: quote  # type: ignore[assignment]
    return client


@pytest.mark.asyncio
async def test_fii_spider_skips_without_token():
    spider = FIISpider(client=_make_client(enabled=False))
    result = CrawlResult(symbol="MXRF11")
    await spider.enrich(result)
    # No token → nothing populated.
    assert result.dy is None
    assert result.p_vp is None


@pytest.mark.asyncio
async def test_fii_spider_populates_from_brapi():
    quote = BrapiQuote(
        ticker="MXRF11",
        cnpj="97521080000139",
        long_name="Maxi Renda FII",
        sector="Real Estate",
        industry="REIT",
        asset_type="FII",
        market_cap=1_500_000_000.0,
        raw={
            "defaultKeyStatistics": {"priceToBook": 0.95, "trailingEps": 0.12},
            "fundsData": {"dividendYield": 10.2},
        },
    )
    spider = FIISpider(client=_make_client(quote))
    result = CrawlResult(symbol="MXRF11")
    await spider.enrich(result)

    assert result.dy == pytest.approx(10.2)
    assert result.p_vp == pytest.approx(0.95)
    assert result.market_cap == pytest.approx(1_500_000_000.0)
    assert result.segment == "FII"
    assert result.provenance["asset_type"] == "FII"


@pytest.mark.asyncio
async def test_fii_spider_handles_missing_brapi_response():
    spider = FIISpider(client=_make_client(quote=None))
    result = CrawlResult(symbol="MXRF11")
    await spider.enrich(result)
    assert result.dy is None
    assert "asset_type" not in result.provenance


@pytest.mark.asyncio
async def test_bdr_spider_uses_explicit_underlying():
    quote = BrapiQuote(
        ticker="AAPL34",
        cnpj=None,
        long_name="Apple Inc BDR",
        sector="Technology",
        industry="Consumer Electronics",
        asset_type="BDR",
        market_cap=None,
        raw={"bdrRatio": 100.0},
    )
    spider = BDRSpider(client=_make_client(quote))

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
    spider = BDRSpider(client=_make_client(quote=None, enabled=False))
    result = CrawlResult(symbol="AAPL34")
    await spider.enrich(result)
    # No underlying resolvable → enrichment skipped.
    assert result.p_l is None
    assert result.eps is None
