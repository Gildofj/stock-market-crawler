from datetime import datetime

import pytest

from core.models.models import StockPrice
from core.models.schemas import CompanySchema, StockPriceSchema


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repository_flow(company_repo, price_repo, db_session):
    """
    Test using the high-performance db_session fixture from conftest.py
    """
    company_in = CompanySchema(symbol="TEST3", name="Test Corp")
    company = await company_repo.get_or_create(company_in)
    assert company.id is not None

    price_in = StockPriceSchema(
        time=datetime(2023, 1, 1, 10, 0),
        open=10.0,
        high=11.0,
        low=9.0,
        close=10.5,
        adj_close=10.5,
        volume=1000,
    )
    await price_repo.save_bulk(company.id, [price_in])

    from sqlalchemy import select

    result = await db_session.execute(select(StockPrice).filter_by(company_id=company.id))
    saved_price = result.scalars().first()
    assert saved_price.close == 10.5
