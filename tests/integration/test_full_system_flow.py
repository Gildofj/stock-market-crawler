import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

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

    mock_result = CrawlResult(
        symbol="FLOW3.SA",
        name="Flow Corp",
        shares_outstanding=100.0,
        yahoo_info_indicators={
            "dividendYield": 5.0,
            "forwardPE": 10.0,
            "priceToBook": 2.0,
        },
        prices=[
            StockPriceSchema(
                time=datetime(2023, 1, 1),
                close=100.0,
                open=100.0,
                high=100.0,
                low=100.0,
                volume=1000,
            ),
            StockPriceSchema(
                time=datetime(2023, 1, 2),
                close=110.0,
                open=110.0,
                high=110.0,
                low=110.0,
                volume=1100,
            ),
        ],
    )

    mocker.patch.object(
        engine.b3_spider,
        "crawl_ticker",
        return_value=mock_result,
    )

    engine.cvm_spider._ticker_index = {"FLOW3": CVM_CODE}
    for y in range(datetime.now().year - 6, datetime.now().year + 1):
        engine.cvm_spider._dfp_cache[y] = _synthetic_year()
        engine.cvm_spider._itr_cache[y] = None

    result = await engine.run_for_ticker("FLOW3.SA")

    assert result.valuation_graham == pytest.approx(18.371, rel=1e-3)

    res = await db_session.execute(select(Company).filter_by(symbol="FLOW3.SA"))
    company = res.scalars().first()
    assert company is not None

    res = await db_session.execute(select(Fundamental).filter_by(company_id=company.id))
    fundamental = res.scalars().first()
    assert float(fundamental.p_l) == pytest.approx(73.333, rel=1e-2)

    res = await db_session.execute(select(LakeIndicatorReconciliation).filter_by(ticker="FLOW3.SA"))
    recons = res.scalars().all()
    assert len(recons) == 3
    dy_row = next(r for r in recons if r.indicator == "dy")
    assert float(dy_row.source_value_raw) == 5.0
    assert float(dy_row.source_value_normalised) == 5.0
    assert float(dy_row.cvm_value) == pytest.approx(0.545, rel=1e-3)

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
    assert float(feature.p_l_ratio) == pytest.approx(115.333, rel=1e-2)
    assert feature.sma_20 is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_engine_skips_fundamentals_when_no_indicators(db_session, mocker):
    """The engine must NOT persist a Fundamental row when CVMSpider produced
    no indicators. Persisting an all-NULL row hides upstream failures (CAD
    or DFP download unreachable) behind a false-positive "we crawled it"
    signal. The previous behavior created exactly this kind of poisoned row
    in production.
    """
    engine = CrawlerEngine(db=db_session)

    empty_result = CrawlResult(
        symbol="EMPTY3",
        name="No Data Corp",
        prices=[
            StockPriceSchema(
                time=datetime(2024, 1, 1),
                close=50.0,
                open=50.0,
                high=50.0,
                low=50.0,
                volume=100,
            )
        ],
    )

    mocker.patch.object(engine.b3_spider, "crawl_ticker", return_value=empty_result)
    mocker.patch.object(engine.cvm_spider, "enrich", return_value=None)

    await engine.run_for_ticker("EMPTY3")

    res = await db_session.execute(select(Company).filter_by(symbol="EMPTY3"))
    company = res.scalars().first()
    assert company is not None, "company row must still be created"

    res = await db_session.execute(select(Fundamental).filter_by(company_id=company.id))
    fundamentals_row = res.scalars().first()
    assert fundamentals_row is None, (
        "no fundamentals row should be persisted when every indicator is None"
    )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="Network test — set RUN_NETWORK_TESTS=1 to hit real CVM endpoints",
)
async def test_real_cvm_endpoint_petr4(db_session):
    """End-to-end smoke against the real CVM Dados Abertos endpoints.

    Skipped by default. Run manually when validating production parity
    (``RUN_NETWORK_TESTS=1 uv run pytest -k test_real_cvm_endpoint_petr4``).
    Asserts that PETR4 (CD_CVM 9512) lands a Fundamental row with at least
    five core indicators populated — the minimum we accept as "working".
    """
    engine = CrawlerEngine(db=db_session)

    await engine.run_for_ticker("PETR4")

    res = await db_session.execute(select(Company).filter_by(symbol="PETR4"))
    company = res.scalars().first()
    assert company is not None

    res = await db_session.execute(select(Fundamental).filter_by(company_id=company.id))
    fundamental = res.scalars().first()
    assert fundamental is not None, "PETR4 must produce a fundamentals row from real CVM data"

    core_fields = (
        fundamental.p_l,
        fundamental.roe,
        fundamental.net_margin,
        fundamental.debt_to_equity,
        fundamental.market_cap,
        fundamental.eps,
        fundamental.liquid_debt_ebitda,
    )
    populated = sum(1 for v in core_fields if v is not None)
    assert populated >= 5, f"expected ≥5 core indicators populated, got {populated}"
