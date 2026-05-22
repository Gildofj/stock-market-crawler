from crawler.spiders.cvm_spider import _derive_ebit


def test_uses_pretax_minus_financial_result():
    assert _derive_ebit(net_income=80, income_tax=20, pretax=100, financial_result=-30) == 130


def test_falls_back_to_net_income_plus_tax_minus_financial_result():
    assert _derive_ebit(net_income=70, income_tax=30, pretax=None, financial_result=-20) == 120


def test_returns_none_without_financial_result():
    assert _derive_ebit(net_income=70, income_tax=30, pretax=100, financial_result=None) is None


def test_returns_none_when_neither_pretax_nor_full_net_income_chain_available():
    assert _derive_ebit(net_income=70, income_tax=None, pretax=None, financial_result=-20) is None
    assert _derive_ebit(net_income=None, income_tax=30, pretax=None, financial_result=-20) is None


def test_positive_financial_result_reduces_ebit():
    assert _derive_ebit(net_income=80, income_tax=20, pretax=100, financial_result=15) == 85
