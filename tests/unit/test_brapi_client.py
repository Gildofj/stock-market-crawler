"""Unit tests for the Brapi client wrapper."""

from __future__ import annotations

import pytest

from core.services.brapi_client import (
    BrapiClient,
    BrapiQuotaExceededError,
    BrapiUnauthorizedError,
    _normalise_asset_type,
)


def test_asset_type_inferred_from_b3_suffix_fii():
    assert _normalise_asset_type(quote_type=None, symbol="MXRF11") == "FII"


def test_asset_type_inferred_from_b3_suffix_bdr():
    for bdr in ("AAPL34", "MSFT34", "GOGL35", "ITLC33", "AMZO32"):
        assert _normalise_asset_type(quote_type="EQUITY", symbol=bdr) == "BDR", bdr


def test_asset_type_suffix_overrides_brapi_quotetype_mismatch():
    # Brapi may incorrectly tag a FII as EQUITY; suffix is authoritative.
    assert _normalise_asset_type(quote_type="EQUITY", symbol="HGLG11") == "FII"


def test_asset_type_fractional_suffix_treated_as_parent():
    assert _normalise_asset_type(quote_type="EQUITY", symbol="PETR4F") == "EQUITY"
    assert _normalise_asset_type(quote_type="EQUITY", symbol="MXRF11F") == "FII"


def test_asset_type_defaults_to_equity_for_unknown():
    assert _normalise_asset_type(quote_type=None, symbol="PETR4") == "EQUITY"
    assert _normalise_asset_type(quote_type="EQUITY", symbol="VALE3") == "EQUITY"


def test_asset_type_etf_quotetype_wins_over_suffix_11():
    # BOVA11 is an ETF (iShares Bovespa) even though it uses the 11 suffix.
    # Brapi's quote_type="ETF" disambiguates from FIIs that share the suffix.
    assert _normalise_asset_type(quote_type="ETF", symbol="BOVA11") == "ETF"


def test_asset_type_mutualfund_fallback_for_non_11_funds():
    assert _normalise_asset_type(quote_type="MUTUALFUND", symbol="ABCD3") == "FII"


def test_client_disabled_without_token(monkeypatch):
    # BrapiClient(token=None) falls back to settings.BRAPI_TOKEN; the local
    # .env may set it, so neutralise the source-of-truth for this test.
    monkeypatch.setattr("core.services.brapi_client.settings.BRAPI_TOKEN", None)
    client = BrapiClient(token=None, monthly_budget=100)
    assert client.enabled is False
    with pytest.raises(BrapiUnauthorizedError):
        client._request("/quote/PETR4")


def test_quota_enforced():
    client = BrapiClient(token="t", monthly_budget=1)
    client._check_quota()
    with pytest.raises(BrapiQuotaExceededError):
        client._check_quota()


def test_quota_counter_resets_on_month_rollover():
    client = BrapiClient(token="t", monthly_budget=2)
    client._calls_this_month = 2
    client._month_key = "2026-04"  # simulate stale counter
    # Next check should reset because current month differs from cached.
    client._check_quota()
    assert client.calls_used == 1
