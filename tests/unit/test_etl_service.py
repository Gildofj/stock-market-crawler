import uuid
from datetime import datetime

import pytest
from crawler.models.schemas import CompanySchema, StockPriceSchema
from crawler.services.etl_service import ETLService


def test_generate_features_calculation(mocker):
    # Mock DB session
    mock_db = mocker.Mock()

    from datetime import timedelta
    # Create dummy price data
    mock_prices = [
        StockPriceSchema(
            time=datetime(2023, 1, 1) + timedelta(days=i),
            open=100.0 + i,
            high=105.0 + i,
            low=95.0 + i,
            close=100.0 + i,
            adj_close=100.0 + i,
            volume=1000,
        )
        for i in range(60)
    ]

    # Mock DB query results
    # First query is for StockPrice, second is for Fundamental
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
        mock_prices
    )

    mock_fundamental = mocker.Mock()
    mock_fundamental.eps = 10.0
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
        mock_fundamental
    )

    # For the existence check inside the loop
    mock_db.query.return_value.filter.return_value.first.return_value = None

    etl = ETLService(mock_db)
    # Use a real UUID string to satisfy type checkers
    test_uuid = uuid.UUID("00000000-0000-0000-0000-000000000001")
    etl.generate_features(company_id=test_uuid)

    # Verify storage calls
    assert mock_db.add.called

    # Check the first feature added
    # SMA 50 needs 50 rows, so dropped rows will be first 49 (indices 0-48).
    # Index 49 is the 50th row.
    first_feature_added = mock_db.add.call_args_list[0][0][0]
    # At index 49, close is 100 + 49 = 149.0
    # EPS is 10.0. p_l_ratio = 149.0 / 10.0 = 14.9
    # Use float conversion for comparison since it might be Decimal
    assert float(first_feature_added.p_l_ratio) == 14.9

    assert mock_db.commit.called
