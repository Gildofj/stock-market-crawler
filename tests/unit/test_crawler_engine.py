from datetime import datetime

import pytest

from core.models.schemas import StockPriceSchema
from crawler.engine.crawler_engine import CrawlerEngine
from crawler.models.contract import CrawlResult


@pytest.mark.asyncio
async def test_calculate_advanced_metrics(mocker):
    mock_db = mocker.Mock()
    engine = CrawlerEngine(db=mock_db)

    result = CrawlResult(
        symbol="TEST3",
        eps=2.0,
        p_vp=1.0,
        dy=6.0,
        roe=16.0,
        roic=13.0,
        net_margin=11.0,
        liquid_debt_ebitda=1.5,
        cagr_revenue_5y=6.0,
        prices=[StockPriceSchema(time=datetime.now(), close=20.0)],
    )

    engine._calculate_advanced_metrics(result)

    assert result.valuation_graham == pytest.approx(30.0)

    assert result.valuation_bazin == pytest.approx(20.0)

    assert result.quality_score == 100


@pytest.mark.asyncio
async def test_calculate_advanced_metrics_partial(mocker):
    mock_db = mocker.Mock()
    engine = CrawlerEngine(db=mock_db)

    result = CrawlResult(
        symbol="TEST3",
        eps=1.0,
        p_vp=2.0,
        dy=3.0,
        roe=12.0,
        roic=7.0,
        net_margin=6.0,
        liquid_debt_ebitda=4.0,
        cagr_revenue_5y=2.0,
        prices=[StockPriceSchema(time=datetime.now(), close=10.0)],
    )

    engine._calculate_advanced_metrics(result)

    assert result.valuation_graham == pytest.approx(10.6066, rel=1e-4)

    assert result.valuation_bazin == pytest.approx(5.0)

    assert result.quality_score == 30
