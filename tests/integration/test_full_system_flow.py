from datetime import datetime

import pytest

from crawler.engine.crawler_engine import CrawlerEngine
from crawler.models.contract import CrawlResult
from crawler.models.models import Company, Fundamental, MLFeature
from crawler.models.schemas import StockPriceSchema
from crawler.services.etl_service import ETLService


def test_crawler_to_etl_full_flow(db_session, mocker):
    """
    Tests the full flow from CrawlerEngine (mocked spiders) to Database,
    including advanced metrics calculation and ML feature generation.
    """
    # 1. Setup Engine and Mocks
    engine = CrawlerEngine(db=db_session)

    # Mock spiders to avoid network calls but simulate real data return
    mocker.patch.object(
        engine.b3_spider,
        "crawl_ticker",
        return_value=CrawlResult(
            symbol="FLOW3",
            name="Flow Corp",
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
        ),
    )

    # Simulate enrichment from Fundamentus
    mocker.patch.object(
        engine.fundamentus_spider,
        "crawl_ticker",
        return_value=CrawlResult(
            symbol="FLOW3",
            p_l=10.0,
            p_vp=2.0,
            dy=5.0,
            roe=15.0,
            roic=12.0,
            eps=10.0,
            liquid_debt_ebitda=1.5,
            cagr_revenue_5y=8.0,
            net_margin=10.0,
        ),
    )

    # Simulate enrichment from StatusInvest
    mocker.patch.object(
        engine.status_spider, "crawl_ticker", return_value=CrawlResult(symbol="FLOW3")
    )

    # 2. Run Engine
    result = engine.run_for_ticker("FLOW3")

    # Verify Engine Calculations
    # Graham: sqrt(22.5 * 10.0 * (110.0 / 2.0)) = sqrt(22.5 * 10 * 55) = sqrt(12375) ≈ 111.24
    assert result.valuation_graham == pytest.approx(111.24, rel=1e-3)
    # Bazin: ((5.0 / 100) * 110.0) / 0.06 = 5.5 / 0.06 = 91.66
    assert result.valuation_bazin == pytest.approx(91.66, rel=1e-3)
    # Quality Score: ROE(15>10:10), ROIC(12>8:10), NetMargin(10>5:10), Debt(1.5<2.0:20), CAGR(8>5:20) = 70
    assert result.quality_score == 70

    # 3. Verify Database Persistence
    company = db_session.query(Company).filter_by(symbol="FLOW3").first()
    assert company is not None
    assert company.name == "Flow Corp"

    fundamental = db_session.query(Fundamental).filter_by(company_id=company.id).first()
    assert float(fundamental.valuation_graham) == pytest.approx(111.24, rel=1e-3)
    assert fundamental.quality_score == 70

    # 4. Run ETL Service
    etl = ETLService(db=db_session)

    # Add more prices to satisfy rolling windows (SMA-50 needs 50 rows)
    # Use StockPriceSchema instead of dict
    from datetime import timedelta

    base_date = datetime(2023, 1, 3)
    for i in range(65):
        engine.data_service.save_prices(
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

    etl.generate_features(company.id)

    # 5. Verify ML Features
    feature = (
        db_session.query(MLFeature)
        .filter_by(company_id=company.id)
        .order_by(MLFeature.time.desc())
        .first()
    )
    assert feature is not None
    # Latest stored feature is PENULTIMATE price because last price has no target_next_day_change
    # i=63 -> close = 110 + 63 = 173.0
    # EPS: 10.0 -> p_l_ratio: 17.3
    assert float(feature.p_l_ratio) == pytest.approx(17.3)
    assert feature.sma_20 is not None
