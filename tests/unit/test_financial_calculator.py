"""Unit tests for the universal financial-indicator formulas.

Every test pins one indicator against a hand-calculated reference so any
future tweak to the formula has to be explicit.
"""

import math

import pytest

from crawler.services.financial_calculator import (
    ComputedIndicators,
    RawFinancials,
    bazin_fair_value,
    bvps,
    cagr,
    cash_position,
    compute_all,
    current_ratio,
    debt_to_equity,
    dividend_yield,
    ebit_margin,
    ebitda_margin,
    eps,
    ev_ebitda,
    graham_fair_value,
    gross_margin,
    market_cap,
    net_debt,
    net_debt_to_ebitda,
    net_margin,
    pl_ratio,
    pvp_ratio,
    roe,
    roic,
    total_debt,
)


def test_market_cap_basic():
    assert market_cap(10.0, 1_000_000) == 10_000_000.0


def test_market_cap_invalid_inputs():
    assert market_cap(None, 1000) is None
    assert market_cap(10.0, None) is None
    assert market_cap(10.0, 0) is None
    assert market_cap(10.0, -1) is None


def test_eps_and_bvps():
    assert eps(1_000_000, 200_000) == 5.0
    assert bvps(500_000, 100_000) == 5.0
    assert eps(1_000_000, 0) is None
    assert bvps(None, 100_000) is None


def test_total_debt_and_cash_position():
    assert total_debt(100, 200) == 300
    assert total_debt(None, 200) == 200
    assert total_debt(None, None) is None
    assert cash_position(50, 25) == 75
    assert cash_position(50, None) == 50
    assert cash_position(None, None) is None


def test_net_debt():
    assert net_debt(500, 200) == 300
    assert net_debt(500, None) == 500
    assert net_debt(None, None) is None


def test_pl_ratio_only_positive_eps():
    assert pl_ratio(20.0, 2.0) == 10.0
    assert pl_ratio(20.0, 0) is None
    assert pl_ratio(20.0, -1.0) is None
    assert pl_ratio(20.0, None) is None


def test_pvp_ratio_only_positive_bvps():
    assert pvp_ratio(20.0, 10.0) == 2.0
    assert pvp_ratio(20.0, 0) is None
    assert pvp_ratio(20.0, -1) is None


def test_ev_ebitda_includes_net_debt():
    # market_cap=1000, debt=300, cash=100, ebitda=200
    # EV = 1000 + (300-100) = 1200 -> 1200/200 = 6.0
    assert ev_ebitda(1000, 300, 100, 200) == 6.0


def test_ev_ebitda_missing_inputs():
    assert ev_ebitda(None, 300, 100, 200) is None
    assert ev_ebitda(1000, 300, 100, 0) is None
    assert ev_ebitda(1000, None, None, 200) == pytest.approx(5.0)


def test_roe_percent():
    assert roe(150, 1000) == pytest.approx(15.0)
    assert roe(150, 0) is None
    assert roe(None, 1000) is None


def test_roic_uses_effective_tax_when_available():
    # ebit=200, income_tax=40, pretax=200 -> rate 0.2 -> nopat = 200 * 0.8 = 160
    # invested capital = equity(1000) + debt(300) - cash(100) = 1200
    # ROIC = 160 / 1200 = 13.333...%
    result = roic(200, 40, 200, 1000, 300, 100)
    assert result == pytest.approx(13.333, rel=1e-3)


def test_roic_falls_back_to_headline_rate():
    # No tax inputs -> assume 34% Brazilian headline rate
    # nopat = 200 * 0.66 = 132, invested capital = 1200 -> 11.0%
    result = roic(200, None, None, 1000, 300, 100)
    assert result == pytest.approx(11.0, rel=1e-3)


def test_roic_returns_none_for_invalid_invested_capital():
    # equity + debt - cash = 0 -> divide-by-zero territory
    assert roic(200, 40, 200, 0, 0, 0) is None


def test_margins_percent():
    assert gross_margin(300, 1000) == pytest.approx(30.0)
    assert ebit_margin(150, 1000) == pytest.approx(15.0)
    assert ebitda_margin(200, 1000) == pytest.approx(20.0)
    assert net_margin(100, 1000) == pytest.approx(10.0)


def test_dividend_yield_percent():
    # dividends_paid=10_000, shares=1_000 -> DPS=10
    # price=200 -> DY = 10/200 = 5%
    assert dividend_yield(10_000, 1000, 200) == pytest.approx(5.0)


def test_net_debt_to_ebitda():
    # debt=300, cash=100 -> net debt=200, ebitda=100 -> ratio=2.0
    assert net_debt_to_ebitda(300, 100, 100) == 2.0


def test_debt_to_equity():
    assert debt_to_equity(500, 1000) == 0.5
    assert debt_to_equity(500, 0) is None


def test_current_ratio():
    assert current_ratio(2000, 1000) == 2.0
    assert current_ratio(2000, 0) is None


def test_cagr_universal_formula():
    # (200/100)^(1/4) - 1 = 0.1892... -> 18.92%
    assert cagr(100, 200, 4) == pytest.approx(18.9207, rel=1e-3)


def test_cagr_handles_invalid_inputs():
    assert cagr(None, 200, 4) is None
    assert cagr(100, None, 4) is None
    assert cagr(0, 200, 4) is None
    assert cagr(100, -200, 4) is None
    assert cagr(100, 200, 0) is None


def test_graham_fair_value():
    # sqrt(22.5 * 5 * 10) = sqrt(1125) ~ 33.541
    assert graham_fair_value(5, 10) == pytest.approx(math.sqrt(1125))
    assert graham_fair_value(-1, 10) is None
    assert graham_fair_value(0, 10) is None


def test_bazin_fair_value_uses_default_yield():
    assert bazin_fair_value(1.20) == pytest.approx(20.0)


def test_bazin_fair_value_invalid_inputs():
    assert bazin_fair_value(None) is None
    assert bazin_fair_value(0) is None
    assert bazin_fair_value(1.20, 0) is None


def test_compute_all_pipes_indicators_through():
    raw = RawFinancials(
        revenue=1000.0,
        gross_profit=400.0,
        ebit=250.0,
        ebitda=300.0,
        net_income=150.0,
        income_tax_expense=50.0,
        pretax_income=200.0,
        total_assets=2000.0,
        current_assets=600.0,
        cash_and_equivalents=100.0,
        short_term_investments=50.0,
        current_liabilities=300.0,
        short_term_debt=80.0,
        long_term_debt=220.0,
        equity=1000.0,
        dividends_paid_ttm=30.0,
        current_price=20.0,
        shares_outstanding=100.0,
    )
    result = compute_all(raw)

    assert isinstance(result, ComputedIndicators)
    assert result.market_cap == pytest.approx(2000.0)
    assert result.eps == pytest.approx(1.5)
    assert result.bvps == pytest.approx(10.0)
    assert result.p_l == pytest.approx(20.0 / 1.5)
    assert result.p_vp == pytest.approx(2.0)
    # net debt = 300 - 150 = 150 -> EV = 2000 + 150 = 2150; EV/EBITDA = 2150/300
    assert result.ev_ebitda == pytest.approx(2150.0 / 300.0)
    assert result.roe == pytest.approx(15.0)
    assert result.net_margin == pytest.approx(15.0)
    # DY: dps = 0.3, price=20 -> 0.3/20 = 1.5%
    assert result.dy == pytest.approx(1.5)
    assert result.current_ratio == pytest.approx(2.0)
    assert result.debt_to_equity == pytest.approx(0.3)
    assert result.net_debt_ebitda == pytest.approx(0.5)


def test_compute_all_handles_missing_inputs_gracefully():
    raw = RawFinancials()  # everything None
    result = compute_all(raw)
    # Every indicator should be None without raising
    assert result.p_l is None
    assert result.p_vp is None
    assert result.roe is None
    assert result.market_cap is None
