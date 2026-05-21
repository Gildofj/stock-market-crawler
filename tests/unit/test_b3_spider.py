"""Unit tests for B3Spider.

The spider's responsibility was narrowed: it now only collects prices,
textual company metadata, ``shares_outstanding`` via the documented
``Ticker.get_shares_full()`` API, and a raw snapshot of the numeric
``Ticker.info`` fields. Every fundamentals indicator (p_l, roe, dy, ...)
is computed downstream by CVMSpider — those attributes on ``CrawlResult``
must remain ``None`` after B3Spider runs.
"""

import pandas as pd
import pytest

from crawler.spiders.b3_spider import B3Spider


@pytest.fixture
def _history_df():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    return pd.DataFrame(
        {
            "Open": [10.0, 11.0],
            "High": [11.5, 12.0],
            "Low": [9.5, 10.5],
            "Close": [11.0, 11.8],
            "Adj Close": [11.0, 11.8],
            "Volume": [1000, 1500],
        },
        index=idx,
    )


@pytest.fixture
def _info_dict():
    return {
        "longName": "Flow Corp SA",
        "sector": "Industrials",
        "industry": "Heavy Industry",
        "quoteType": "EQUITY",
        "website": "https://flow.example",
        # Numeric fields — captured as a snapshot, NOT written to result.X.
        "forwardPE": 12.5,
        "trailingPE": 13.0,
        "priceToBook": 2.1,
        "enterpriseToEbitda": 8.4,
        "returnOnEquity": 0.18,
        "dividendYield": 0.05,
        "profitMargins": 0.12,
        "debtToEbitda": 1.5,
        "debtToEquity": 65.0,
        "marketCap": 5_000_000_000.0,
        "trailingEps": 3.4,
    }


def _patch_ticker(mocker, info: dict, history: pd.DataFrame, shares=None, shares_exc=None):
    """Patch the yfinance.Ticker constructor used inside b3_spider."""
    ticker = mocker.Mock()
    ticker.info = info
    ticker.history.return_value = history
    if shares_exc is not None:
        ticker.get_shares_full.side_effect = shares_exc
    else:
        ticker.get_shares_full.return_value = shares
    mocker.patch("crawler.spiders.b3_spider.yf.Ticker", return_value=ticker)
    return ticker


@pytest.mark.asyncio
async def test_b3_spider_does_not_write_fundamentals(mocker, _info_dict, _history_df):
    """B3 spider must not populate any numeric indicator on the result —
    those come from CVMSpider. Numeric .info fields are captured into
    `yahoo_info_indicators` for reconciliation only.
    """
    _patch_ticker(mocker, info=_info_dict, history=_history_df, shares=pd.Series([1_000_000.0]))

    result = await B3Spider().crawl_ticker("FLOW3")

    # Metadata: populated
    assert result.name == "Flow Corp SA"
    assert result.sector == "Industrials"
    assert result.sub_sector == "Heavy Industry"
    assert result.segment == "EQUITY"
    assert result.website == "https://flow.example"

    # Prices: populated
    assert len(result.prices) == 2
    assert result.prices[-1].close == pytest.approx(11.8)

    # Shares: populated via the documented API
    assert result.shares_outstanding == 1_000_000.0

    # Numeric indicators: STILL NONE — CVMSpider will fill these later.
    assert result.p_l is None
    assert result.p_vp is None
    assert result.ev_ebitda is None
    assert result.roe is None
    assert result.dy is None  # default field value, not 0.0
    assert result.net_margin is None
    assert result.liquid_debt_ebitda is None
    assert result.debt_to_equity is None
    assert result.market_cap is None
    assert result.eps is None


@pytest.mark.asyncio
async def test_b3_spider_captures_info_snapshot(mocker, _info_dict, _history_df):
    """All numeric fields present in .info must round-trip into the snapshot
    untouched (no normalisation at this layer — the reconciliation service
    handles unit conversion).
    """
    _patch_ticker(mocker, info=_info_dict, history=_history_df, shares=pd.Series([1_000_000.0]))

    result = await B3Spider().crawl_ticker("FLOW3")

    snapshot = result.yahoo_info_indicators
    assert snapshot is not None
    assert snapshot["dividendYield"] == 0.05  # raw decimal, untouched
    assert snapshot["returnOnEquity"] == 0.18
    assert snapshot["marketCap"] == 5_000_000_000.0
    assert snapshot["forwardPE"] == 12.5
    assert snapshot["debtToEquity"] == 65.0
    # Textual metadata stays out of the snapshot — only numeric.
    assert "longName" not in snapshot


@pytest.mark.asyncio
async def test_b3_spider_missing_info_fields(mocker, _history_df):
    """An info dict with no numeric fields should produce an empty snapshot
    (represented as None to stay consistent with the field type).
    """
    info = {"longName": "Bare Corp"}
    _patch_ticker(mocker, info=info, history=_history_df, shares=pd.Series([500.0]))

    result = await B3Spider().crawl_ticker("BARE3")

    assert result.yahoo_info_indicators is None
    assert result.shares_outstanding == 500.0


@pytest.mark.asyncio
async def test_b3_spider_handles_get_shares_full_failure(mocker, _info_dict, _history_df):
    """get_shares_full() raising must not break the crawl; shares_outstanding
    stays None and the rest of the snapshot still lands.
    """
    _patch_ticker(
        mocker,
        info=_info_dict,
        history=_history_df,
        shares_exc=RuntimeError("yfinance is down"),
    )

    result = await B3Spider().crawl_ticker("FLOW3")

    assert result.shares_outstanding is None
    assert result.yahoo_info_indicators is not None
    assert len(result.prices) == 2  # history still populated


@pytest.mark.asyncio
async def test_b3_spider_handles_empty_shares_series(mocker, _info_dict, _history_df):
    """An empty shares Series is a soft miss, not a fatal error."""
    _patch_ticker(mocker, info=_info_dict, history=_history_df, shares=pd.Series([], dtype=float))

    result = await B3Spider().crawl_ticker("FLOW3")

    assert result.shares_outstanding is None


@pytest.mark.asyncio
async def test_b3_spider_returns_empty_result_for_delisted(mocker, _info_dict):
    """An empty history (delisted / unknown ticker) short-circuits before
    any .info read."""
    _patch_ticker(
        mocker,
        info=_info_dict,
        history=pd.DataFrame(),
        shares=pd.Series([1.0]),
    )

    result = await B3Spider().crawl_ticker("DEAD3")

    assert result.prices == []
    assert result.yahoo_info_indicators is None
    # Empty default — no info was read because history short-circuit fired.
    assert result.name is None


@pytest.mark.asyncio
async def test_b3_spider_marks_zero_volume_inactive(mocker, _info_dict):
    """Five trading days of zero volume → is_active flipped to 0."""
    idx = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    df = pd.DataFrame(
        {
            "Open": [1.0] * 5,
            "High": [1.0] * 5,
            "Low": [1.0] * 5,
            "Close": [1.0] * 5,
            "Adj Close": [1.0] * 5,
            "Volume": [0, 0, 0, 0, 0],
        },
        index=idx,
    )
    _patch_ticker(mocker, info=_info_dict, history=df, shares=pd.Series([1.0]))

    result = await B3Spider().crawl_ticker("DULL3")

    assert result.is_active == 0
