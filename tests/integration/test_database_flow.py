from datetime import datetime

import pytest

from crawler.models.models import StockPrice
from crawler.models.schemas import CompanySchema, StockPriceSchema


@pytest.mark.integration
def test_repository_flow(company_repo, price_repo, db_session):
    """
    Test using the high-performance db_session fixture from conftest.py
    """
    # 1. Create Company
    company_in = CompanySchema(symbol="TEST3", name="Test Corp")
    company = company_repo.get_or_create(company_in)
    assert company.id is not None

    # 2. Save Prices
    price_in = StockPriceSchema(
        time=datetime(2023, 1, 1, 10, 0),
        open=10.0,
        high=11.0,
        low=9.0,
        close=10.5,
        adj_close=10.5,
        volume=1000,
    )
    price_repo.save_bulk(company.id, [price_in])

    # Verify persistence within the transaction
    saved_price = db_session.query(StockPrice).filter_by(company_id=company.id).first()
    assert saved_price.close == 10.5
