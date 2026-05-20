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
def test_crawler_to_etl_full_flow(db_session, mocker):
    """End-to-end pipeline with CVM-derived fundamentals (mocked).

    The B3 spider supplies prices + shares + a snapshot of yfinance's
    Ticker.info numeric fields. The CVM spider is the authoritative source
    for every indicator computed from CVM Dados Abertos. The reconciliation
    service emits one row per indicator into the data lake.
    """
    engine = CrawlerEngine(db=db_session)

    mocker.patch.object(
        engine.b3_spider,
        "crawl_ticker",
        return_value=CrawlResult(
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
        ),
    )

    # Fundamentals computed locally — the spider returns indicator values that
    # would normally come from running the calculator over CVM line items.
    def _cvm_enrich(result: CrawlResult) -> None:
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

    result = engine.run_for_ticker("FLOW3")

    # Graham: sqrt(22.5 * 10.0 * (110.0 / 2.0)) ≈ 111.24
    assert result.valuation_graham == pytest.approx(111.24, rel=1e-3)
    # Bazin: ((5.0 / 100) * 110.0) / 0.06 = 5.5 / 0.06 ≈ 91.66
    assert result.valuation_bazin == pytest.approx(91.66, rel=1e-3)
    assert result.quality_score == 70

    company = db_session.query(Company).filter_by(symbol="FLOW3").first()
    assert company is not None
    assert company.name == "Flow Corp"

    fundamental = db_session.query(Fundamental).filter_by(company_id=company.id).first()
    assert float(fundamental.valuation_graham) == pytest.approx(111.24, rel=1e-3)
    assert fundamental.quality_score == 70

    # Reconciliation rows: one per upstream indicator that was reported.
    # Fixture supplies forwardPE, priceToBook and dividendYield → 3 rows.
    reconciliations = (
        db_session.query(LakeIndicatorReconciliation)
        .filter_by(company_id=company.id)
        .all()
    )
    assert len(reconciliations) == 3
    indicators = {row.indicator for row in reconciliations}
    assert indicators == {"p_l", "p_vp", "dy"}

    etl = ETLService(db=db_session)

    base_date = datetime(2023, 1, 3)
    for i in range(65):
        engine.price_repo.save_bulk(
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

    feature = (
        db_session.query(MLFeature)
        .filter_by(company_id=company.id)
        .order_by(MLFeature.time.desc())
        .first()
    )
    assert feature is not None
    # Latest stored feature is PENULTIMATE price: i=63 -> close = 110 + 63 = 173.0
    # p_l_ratio = close / EPS = 173.0 / 10.0 = 17.3
    assert float(feature.p_l_ratio) == pytest.approx(17.3)
    assert feature.sma_20 is not None
