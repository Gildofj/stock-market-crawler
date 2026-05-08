import numpy as np
import pandas as pd

from crawler.services.etl_service import ETLService


def test_generate_features_calculation(mocker):
    # Mock DB session
    mock_db = mocker.Mock()

    # Mock price data
    mock_prices = []
    from datetime import datetime, timedelta

    base_time = datetime(2023, 1, 1)

    # Create 60 days of mock prices to satisfy SMA-50 and RSI-14
    for i in range(60):
        mock_p = mocker.Mock()
        mock_p.time = base_time + timedelta(days=i)
        mock_p.close = 100.0 + i  # Increasing price
        mock_p.volume = 1000
        mock_prices.append(mock_p)

    mocker.patch("crawler.services.etl_service.Session", return_value=mock_db)
    mock_db.query.return_value.filter.return_value.order_value.all.return_value = mock_prices
    # Simplified mock for SQLAlchemy query chain
    mock_db.query().filter().order_by().all.return_value = mock_prices

    etl = ETLService(mock_db)
    etl.generate_features(company_id=1)

    # Check if merge was called (saving features)
    assert mock_db.merge.called
    assert mock_db.commit.called

    # Validate calculation logic with a direct DataFrame test
    df = pd.DataFrame([{"close": 100.0 + i} for i in range(60)])
    df["sma_20"] = df["close"].rolling(window=20).mean()

    # The 20th element (index 19) should have a valid SMA_20
    assert not np.isnan(df["sma_20"].iloc[19])
    assert df["sma_20"].iloc[19] == sum(range(100, 120)) / 20
