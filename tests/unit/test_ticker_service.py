from unittest.mock import patch

import pytest

from crawler.services.ticker_service import TickerService


@pytest.fixture(autouse=True)
def reset_ticker_cache():
    TickerService._cached_tickers = []
    TickerService._last_fetch = 0


def test_get_all_tickers_b3_first():
    service = TickerService()

    with patch.object(
        service, "_fetch_from_b3_instruments", return_value=["PETR4", "VALE3"]
    ) as mock_b3:
        tickers = service.get_all_tickers()
        assert "PETR4" in tickers
        assert "VALE3" in tickers
        mock_b3.assert_called_once()


def test_get_all_tickers_fallback_to_cvm_cad():
    service = TickerService()

    with patch.object(service, "_fetch_from_b3_instruments", side_effect=Exception("API Down")):
        with patch.object(
            service, "_fetch_from_cvm_cad", return_value=["ITUB4", "BBDC4"]
        ) as mock_cvm:
            tickers = service.get_all_tickers()
            assert "ITUB4" in tickers
            assert "BBDC4" in tickers
            mock_cvm.assert_called()


def test_get_all_tickers_fallback_to_blue_chips():
    service = TickerService()

    with patch.object(service, "_fetch_from_b3_instruments", side_effect=Exception("Error")):
        with patch.object(service, "_fetch_from_cvm_cad", side_effect=Exception("Error")):
            tickers = service.get_all_tickers()
            assert "PETR4" in tickers
            assert len(tickers) >= 56
