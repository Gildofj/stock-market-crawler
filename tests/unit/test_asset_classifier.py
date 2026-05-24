from core.services.asset_classifier import classify_asset_type


def test_classifier_returns_etf_when_quote_type_is_etf():
    # BOVA11 has the FII suffix but is actually an ETF — the explicit hint wins.
    assert classify_asset_type(quote_type="ETF", symbol="BOVA11") == "ETF"


def test_classifier_returns_fii_for_suffix_11_without_etf_hint():
    assert classify_asset_type(quote_type=None, symbol="MXRF11") == "FII"
    assert classify_asset_type(quote_type="STOCK", symbol="HGLG11") == "FII"


def test_classifier_returns_bdr_for_bdr_suffixes():
    for symbol in ("AAPL34", "MSFT35", "BERK33", "VISA32"):
        assert classify_asset_type(quote_type=None, symbol=symbol) == "BDR"


def test_classifier_strips_fractional_f_suffix():
    assert classify_asset_type(quote_type=None, symbol="AAPL34F") == "BDR"
    assert classify_asset_type(quote_type=None, symbol="MXRF11F") == "FII"


def test_classifier_strips_dot_sa_suffix():
    assert classify_asset_type(quote_type=None, symbol="PETR4.SA") == "EQUITY"
    assert classify_asset_type(quote_type=None, symbol="MXRF11.SA") == "FII"


def test_classifier_uses_mutualfund_fallback_for_non_11():
    assert classify_asset_type(quote_type="MUTUALFUND", symbol="FUND4") == "FII"


def test_classifier_defaults_to_equity():
    for symbol in ("PETR4", "VALE3", "ITUB4", "ABEV3"):
        assert classify_asset_type(quote_type=None, symbol=symbol) == "EQUITY"


def test_classifier_normalises_lowercase_input():
    assert classify_asset_type(quote_type="etf", symbol="bova11") == "ETF"
    assert classify_asset_type(quote_type=None, symbol="aapl34") == "BDR"
