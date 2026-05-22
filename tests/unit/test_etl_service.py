import uuid
from datetime import datetime

import pytest

from core.services.etl_service import ETLService


@pytest.mark.asyncio
async def test_generate_features_calculation(mocker):
    mock_db = mocker.Mock()
    mock_db.execute = mocker.AsyncMock()
    mock_db.commit = mocker.AsyncMock()
    mock_db.rollback = mocker.AsyncMock()
    mock_db.add = mocker.Mock()

    from datetime import timedelta

    mock_prices = [
        mocker.Mock(
            time=datetime(2023, 1, 1) + timedelta(days=i),
            close=100.0 + i,
            volume=1000,
        )
        for i in range(60)
    ]

    mock_fundamental = mocker.Mock()
    mock_fundamental.eps = 10.0

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
    test_uuid = uuid.UUID("00000000-0000-0000-0000-000000000001")
    await etl.generate_features(company_id=test_uuid)

    assert mock_db.add.called

    first_feature_added = mock_db.add.call_args_list[0][0][0]
    assert float(first_feature_added.p_l_ratio) == 14.9

    assert mock_db.commit.called
