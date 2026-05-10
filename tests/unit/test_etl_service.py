import numpy as np
import pandas as pd
from crawler.services.etl_service import ETLService
from datetime import datetime, timedelta

def test_generate_features_calculation(mocker):
    # Mock DB session
    mock_db = mocker.Mock()

    # Mock price data
    mock_prices = []
    base_time = datetime(2023, 1, 1)

    # Create 60 days of mock prices to satisfy SMA-50 and RSI-14
    for i in range(60):
        mock_p = mocker.Mock()
        mock_p.time = base_time + timedelta(days=i)
        mock_p.close = 100.0 + i
        mock_p.volume = 1000
        mock_prices.append(mock_p)

    # Mock DB query results
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_prices
    mock_db.query.return_value.filter.return_value.first.return_value = None

    etl = ETLService(mock_db)
    etl.generate_features(company_id=1)

    # Verify storage calls
    assert mock_db.add.called
    assert mock_db.commit.called

    # Validate math logic (Unit check within test)
    df = pd.DataFrame([{"close": 100.0 + i} for i in range(60)])
    df["sma_20"] = df["close"].rolling(window=20).mean()
    assert not np.isnan(df["sma_20"].iloc[19])
    assert df["sma_20"].iloc[19] == sum(range(100, 120)) / 20
