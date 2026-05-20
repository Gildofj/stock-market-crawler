from datetime import datetime, timedelta

import pytest

from core.models.models import (
    Company,
    Fundamental,
    LakeIndicatorReconciliation,
    MLFeature,
)
from core.models.schemas import StockPriceSchema
from core.services.etl_service import ETLService
from crawler.engine.crawler_engine import CrawlerEngine
from crawler.models.contract import CrawlResult


@pytest.mark.integration
@pytest.mark.asyncio
async def test_crawler_to_etl_full_flow(db_session, mocker):
    """End-to-end pipeline with CVM-derived fundamentals (mocked).

    The B3 spider supplies prices + shares + a snapshot of yfinance's
    Ticker.info numeric fields. The CVM spider is the authoritative source
    for every indicator computed from CVM Dados Abertos. The reconciliation
    service emits one row per indicator into the data lake.
    """
    engine = CrawlerEngine(db=db_session)

    mock_result = CrawlResult(
        symbol="FLOW3",
        name="Flow Corp",
        shares_outstanding=22_000_000,
        yahoo_info_indicators={
            "dividendYield": 0.05,
            "forwardPE": 10.0,
            "priceToBook": 2.0,
        },
        prices=[
            {
                "time": datetime(2023, 1, 1),
                "close": 100.0,
                "open": 100.0,
                "high": 100.0,
                "low": 100.0,
                "volume": 1000,
            },
            {
                "time": datetime(2023, 1, 2),
                "close": 110.0,
                "open": 110.0,
                "high": 110.0,
                "low": 110.0,
                "volume": 1100,
            },
        ],
    )

    mocker.patch.object(
        engine.b3_spider,
        "crawl_ticker",
        return_value=mock_result,
    )

    # Fundamentals computed locally
    async def _cvm_enrich(result: CrawlResult) -> None:
        result.p_l = 10.0
        result.p_vp = 2.0
        result.dy = 5.0
        result.roe = 15.0
        result.roic = 12.0
        result.eps = 10.0
        result.liquid_debt_ebitda = 1.5
        result.cagr_revenue_5y = 8.0
        result.net_margin = 10.0

    mocker.patch.object(engine.cvm_spider, "enrich", side_effect=_cvm_enrich)

    result = await engine.run_for_ticker("FLOW3")

    # Graham: sqrt(22.5 * 10.0 * (110.0 / 2.0)) ≈ 111.24
    assert result.valuation_graham == pytest.approx(111.24, rel=1e-3)

    # Verify persistence
    from sqlalchemy import select
    res = await db_session.execute(select(Company).filter_by(symbol="FLOW3"))
    company = res.scalars().first()
    assert company is not None

    res = await db_session.execute(select(Fundamental).filter_by(company_id=company.id))
    fundamental = res.scalars().first()
    assert float(fundamental.p_l) == 10.0

    # Verify reconciliation rows (observation)
    res = await db_session.execute(select(LakeIndicatorReconciliation).filter_by(ticker="FLOW3"))
    recons = res.scalars().all()
    # dividendYield, forwardPE, priceToBook
    assert len(recons) == 3
    dy_row = next(r for r in recons if r.indicator == "dy")
    assert float(dy_row.source_value_normalised) == 5.0
    assert float(dy_row.cvm_value) == 5.0

    # Verify ML feature generation
    etl = ETLService(db=db_session)

    base_date = datetime(2023, 1, 3)
    for i in range(65):
        await engine.price_repo.save_bulk(
            company.id,
            [
                StockPriceSchema(
                    time=base_date + timedelta(days=i),
                    close=110.0 + i,
                    open=110.0,
                    high=110.0,
                    low=110.0,
                    volume=1000,
                )
            ],
        )

    await etl.generate_features(company.id)

    res = await db_session.execute(
        select(MLFeature)
        .filter_by(company_id=company.id)
        .order_by(MLFeature.time.desc())
        .limit(1)
    )
    feature = res.scalars().first()
    assert feature is not None
    # Latest stored feature is PENULTIMATE price: i=63 -> close = 110 + 63 = 173.0
    # p_l_ratio = close / EPS = 173.0 / 10.0 = 17.3
    assert float(feature.p_l_ratio) == pytest.approx(17.3)
    assert feature.sma_20 is not None
