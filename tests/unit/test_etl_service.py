import uuid
from datetime import datetime

import pytest

from core.services.etl_service import ETLService


@pytest.mark.asyncio
async def test_generate_features_calculation(mocker):
    # Mock DB session
    mock_db = mocker.Mock()
    mock_db.execute = mocker.AsyncMock()
    mock_db.commit = mocker.AsyncMock()
    mock_db.rollback = mocker.AsyncMock()
    # add is sync in SQLAlchemy
    mock_db.add = mocker.Mock()

    from datetime import timedelta

    # Create dummy price data
    mock_prices = [
        mocker.Mock(
            time=datetime(2023, 1, 1) + timedelta(days=i),
            close=100.0 + i,
            volume=1000,
        )
        for i in range(60)
    ]

    # Mock Fundamental object
    mock_fundamental = mocker.Mock()
    mock_fundamental.eps = 10.0

    # Setup the sequence of results for db.execute().scalars()
    # 1. prices
    # 2. latest_fundamental
    # 3+ (inside loop) existence checks

    mock_result_prices = mocker.Mock()
    mock_result_prices.scalars.return_value.all.return_value = mock_prices

    mock_result_fundamental = mocker.Mock()
    mock_result_fundamental.scalars.return_value.first.return_value = mock_fundamental

    mock_result_existing = mocker.Mock()
    mock_result_existing.scalars.return_value.first.return_value = None

    mock_db.execute.side_effect = [
        mock_result_prices,
        mock_result_fundamental,
    ] + [mock_result_existing] * 60

    etl = ETLService(mock_db)
    # Use a real UUID string to satisfy type checkers
    test_uuid = uuid.UUID("00000000-0000-0000-0000-000000000001")
    await etl.generate_features(company_id=test_uuid)

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
