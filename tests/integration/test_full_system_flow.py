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
from tests.unit.test_cvm_spider import CVM_CODE, _synthetic_year


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

    # Use a ticker with the .SA suffix to ensure our pipeline is robust
    mock_result = CrawlResult(
        symbol="FLOW3.SA",
        name="Flow Corp",
        shares_outstanding=100.0,
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

    # Seed the synthetic DFP and mapping into the CVM Spider cache
    engine.cvm_spider._ticker_index = {"FLOW3": CVM_CODE}
    for y in range(datetime.now().year - 6, datetime.now().year + 1):
        engine.cvm_spider._dfp_cache[y] = _synthetic_year()
        engine.cvm_spider._itr_cache[y] = None

    result = await engine.run_for_ticker("FLOW3.SA")

    # The synthetic fundamentals:
    # EPS = 150 / 100 = 1.5
    # Equity = 1000. Shares = 100. BVPS = 10.0
    # P/VP = Price / BVPS = 110.0 / 10.0 = 11.0
    # Graham: sqrt(22.5 * 1.5 * 10.0) ≈ 18.371
    assert result.valuation_graham == pytest.approx(18.371, rel=1e-3)

    # Verify persistence
    from sqlalchemy import select

    res = await db_session.execute(select(Company).filter_by(symbol="FLOW3.SA"))
    company = res.scalars().first()
    assert company is not None

    res = await db_session.execute(select(Fundamental).filter_by(company_id=company.id))
    fundamental = res.scalars().first()
    # P_L = Price / EPS = 110 / 1.5 = 73.333
    assert float(fundamental.p_l) == pytest.approx(73.333, rel=1e-2)

    # Verify reconciliation rows (observation)
    res = await db_session.execute(select(LakeIndicatorReconciliation).filter_by(ticker="FLOW3.SA"))
    recons = res.scalars().all()
    # dividendYield, forwardPE, priceToBook
    assert len(recons) == 3
    dy_row = next(r for r in recons if r.indicator == "dy")
    assert float(dy_row.source_value_normalised) == 5.0
    # Synthetic cvm_value for dy = DPS / Price = (60/100) / 110 = 0.6 / 110 ≈ 0.545%
    assert float(dy_row.cvm_value) == pytest.approx(0.545, rel=1e-3)

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
        select(MLFeature).filter_by(company_id=company.id).order_by(MLFeature.time.desc()).limit(1)
    )
    feature = res.scalars().first()
    assert feature is not None
    # Latest stored feature is PENULTIMATE price: i=63 -> close = 110 + 63 = 173.0
    # p_l_ratio = close / EPS = 173.0 / 1.5 = 115.333
    assert float(feature.p_l_ratio) == pytest.approx(115.333, rel=1e-2)
    assert feature.sma_20 is not None
