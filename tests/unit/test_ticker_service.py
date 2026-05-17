from unittest.mock import MagicMock, patch

import pytest

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

    with patch.object(service.request_manager, "get", return_value=mock_response):
        tickers = service._fetch_from_brapi()
        assert tickers == ["AAPL34", "GOOGL34", "PETR4"]


def test_get_all_tickers_brapi_first():
    service = TickerService()

    with patch.object(service, "_fetch_from_brapi", return_value=["PETR4", "VALE3"]) as mock_brapi:
        with patch.object(service, "_fetch_from_b3_instruments") as mock_b3:
            tickers = service.get_all_tickers()
            assert "PETR4" in tickers
            assert "VALE3" in tickers
            mock_brapi.assert_called_once()
            mock_b3.assert_not_called()


def test_get_all_tickers_fallback_to_b3_instruments():
    service = TickerService()

    with patch.object(service, "_fetch_from_brapi", side_effect=Exception("API Down")):
        with patch.object(
            service, "_fetch_from_b3_instruments", return_value=["ITUB4", "BBDC4"]
        ) as mock_b3:
            tickers = service.get_all_tickers()
            assert "ITUB4" in tickers
            assert "BBDC4" in tickers
            mock_b3.assert_called()


def test_get_all_tickers_fallback_to_blue_chips():
    service = TickerService()

    with patch.object(service, "_fetch_from_brapi", side_effect=Exception("Error")):
        with patch.object(service, "_fetch_from_b3_instruments", side_effect=Exception("Error")):
            with patch.object(service, "_fetch_from_cvm_cad", side_effect=Exception("Error")):
                tickers = service.get_all_tickers()
                assert "PETR4" in tickers
                assert len(tickers) >= 56
