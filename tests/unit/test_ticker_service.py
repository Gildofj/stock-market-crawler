import pytest
from unittest.mock import MagicMock, patch
from crawler.services.ticker_service import TickerService

@pytest.fixture(autouse=True)
def reset_ticker_cache():
    TickerService._cached_tickers = []
    TickerService._last_fetch = 0

def test_fetch_from_brapi_success():
    service = TickerService()
    mock_response = MagicMock()
    mock_response.json.return_value = {"stocks": ["AAPL34", "GOOGL34", "PETR4"]}
    mock_response.status_code = 200
    
    with patch.object(service.request_manager, 'get', return_value=mock_response):
        tickers = service._fetch_from_brapi()
        assert tickers == ["AAPL34", "GOOGL34", "PETR4"]

def test_get_all_tickers_brapi_first():
    service = TickerService()
    mock_response = MagicMock()
    mock_response.json.return_value = {"stocks": ["PETR4", "VALE3"]}
    mock_response.status_code = 200
    
    # We want to ensure it calls brapi first and returns if successful
    with patch.object(service, '_fetch_from_brapi', return_value=["PETR4", "VALE3"]) as mock_brapi:
        with patch.object(service, '_fetch_from_fundamentus') as mock_fundamentus:
            tickers = service.get_all_tickers()
            assert "PETR4" in tickers
            assert "VALE3" in tickers
            mock_brapi.assert_called_once()
            mock_fundamentus.assert_not_called()

def test_get_all_tickers_fallback_to_fundamentus():
    service = TickerService()
    
    # Brapi fails, Fundamentus succeeds
    with patch.object(service, '_fetch_from_brapi', side_effect=Exception("API Down")):
        with patch.object(service, '_fetch_from_fundamentus', return_value=["ITUB4", "BBDC4"]) as mock_fundamentus:
            tickers = service.get_all_tickers()
            assert "ITUB4" in tickers
            assert "BBDC4" in tickers
            mock_fundamentus.assert_called()

def test_get_all_tickers_fallback_to_blue_chips():
    service = TickerService()
    
    # All dynamic sources fail
    with patch.object(service, '_fetch_from_brapi', side_effect=Exception("Error")):
        with patch.object(service, '_fetch_from_fundamentus', side_effect=Exception("Error")):
            with patch.object(service, '_fetch_from_statusinvest', side_effect=Exception("Error")):
                tickers = service.get_all_tickers()
                # Should contain PETR4 from the BLUE_CHIPS list
                assert "PETR4" in tickers
                # BLUE_CHIPS has 56 tickers
                assert len(tickers) >= 56
