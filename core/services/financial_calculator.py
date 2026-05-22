from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RawFinancials:
    revenue: float | None = None
    gross_profit: float | None = None
    ebit: float | None = None
    ebitda: float | None = None
    net_income: float | None = None
    income_tax_expense: float | None = None
    pretax_income: float | None = None
    financial_result: float | None = None

    total_assets: float | None = None
    current_assets: float | None = None
    cash_and_equivalents: float | None = None
    short_term_investments: float | None = None
    current_liabilities: float | None = None
    short_term_debt: float | None = None
    long_term_debt: float | None = None
    equity: float | None = None

    dividends_paid_ttm: float | None = None

    current_price: float | None = None
    shares_outstanding: float | None = None


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def market_cap(price: float | None, shares: float | None) -> float | None:
    if price is None or shares is None or shares <= 0:
        return None
    return price * shares


def eps(net_income: float | None, shares: float | None) -> float | None:
    return _safe_div(net_income, shares)


def bvps(equity: float | None, shares: float | None) -> float | None:
    return _safe_div(equity, shares)


def total_debt(short_term: float | None, long_term: float | None) -> float | None:
    if short_term is None and long_term is None:
        return None
    return (short_term or 0.0) + (long_term or 0.0)


def cash_position(cash: float | None, short_term_inv: float | None) -> float | None:
    if cash is None and short_term_inv is None:
        return None
    return (cash or 0.0) + (short_term_inv or 0.0)


def net_debt(debt: float | None, cash: float | None) -> float | None:
    if debt is None and cash is None:
        return None
    return (debt or 0.0) - (cash or 0.0)


def pl_ratio(price: float | None, earnings_per_share: float | None) -> float | None:
    if earnings_per_share is None or earnings_per_share <= 0:
        return None
    return _safe_div(price, earnings_per_share)


def pvp_ratio(price: float | None, book_value_per_share: float | None) -> float | None:
    if book_value_per_share is None or book_value_per_share <= 0:
        return None
    return _safe_div(price, book_value_per_share)


def ev_ebitda(
    mkt_cap: float | None,
    debt: float | None,
    cash: float | None,
    ebitda_value: float | None,
) -> float | None:
    if mkt_cap is None or ebitda_value is None or ebitda_value == 0:
        return None
    nd = net_debt(debt, cash)
    enterprise_value = mkt_cap + (nd or 0.0)
    return enterprise_value / ebitda_value


def roe(net_income: float | None, equity: float | None) -> float | None:
    ratio = _safe_div(net_income, equity)
    return ratio * 100 if ratio is not None else None


def roic(
    ebit_value: float | None,
    income_tax: float | None,
    pretax: float | None,
    equity: float | None,
    debt: float | None,
    cash: float | None,
) -> float | None:
    if ebit_value is None or equity is None:
        return None

    invested_capital = equity + (debt or 0.0) - (cash or 0.0)
    if invested_capital <= 0:
        invested_capital = equity + (debt or 0.0)
    if invested_capital <= 0:
        return None

    effective_rate: float
    if income_tax is not None and pretax is not None and pretax > 0:
        rate = income_tax / pretax
        effective_rate = rate if 0 <= rate <= 0.6 else 0.34
    else:
        effective_rate = 0.34

    nopat = ebit_value * (1 - effective_rate)
    return (nopat / invested_capital) * 100


def gross_margin(gross: float | None, revenue: float | None) -> float | None:
    return _multiplied_ratio(gross, revenue)


def ebit_margin(ebit_value: float | None, revenue: float | None) -> float | None:
    return _multiplied_ratio(ebit_value, revenue)


def ebitda_margin(ebitda_value: float | None, revenue: float | None) -> float | None:
    return _multiplied_ratio(ebitda_value, revenue)


def net_margin(net_income: float | None, revenue: float | None) -> float | None:
    return _multiplied_ratio(net_income, revenue)


def dividend_yield(
    dividends_paid: float | None,
    shares: float | None,
    price: float | None,
) -> float | None:
    dps = _safe_div(dividends_paid, shares)
    return _multiplied_ratio(dps, price)


def net_debt_to_ebitda(
    debt: float | None, cash: float | None, ebitda_value: float | None
) -> float | None:
    nd = net_debt(debt, cash)
    return _safe_div(nd, ebitda_value)


def debt_to_equity(debt: float | None, equity: float | None) -> float | None:
    return _safe_div(debt, equity)


def current_ratio(current_assets: float | None, current_liabilities: float | None) -> float | None:
    return _safe_div(current_assets, current_liabilities)


def cagr(start_value: float | None, end_value: float | None, years: int) -> float | None:
    if start_value is None or end_value is None or years < 1:
        return None
    if start_value <= 0 or end_value <= 0:
        return None
    return (math.pow(end_value / start_value, 1 / years) - 1) * 100


def graham_fair_value(
    earnings_per_share: float | None, book_value_per_share: float | None
) -> float | None:
    if earnings_per_share is None or book_value_per_share is None:
        return None
    if earnings_per_share <= 0 or book_value_per_share <= 0:
        return None
    return math.sqrt(22.5 * earnings_per_share * book_value_per_share)


def bazin_fair_value(
    annual_dividend_per_share: float | None, target_yield: float = 0.06
) -> float | None:
    if annual_dividend_per_share is None or annual_dividend_per_share <= 0:
        return None
    if target_yield <= 0:
        return None
    return annual_dividend_per_share / target_yield


def _multiplied_ratio(numerator: float | None, denominator: float | None) -> float | None:
    ratio = _safe_div(numerator, denominator)
    return ratio * 100 if ratio is not None else None


@dataclass(frozen=True)
class ComputedIndicators:
    market_cap: float | None
    eps: float | None
    bvps: float | None
    p_l: float | None
    p_vp: float | None
    ev_ebitda: float | None
    roe: float | None
    roic: float | None
    gross_margin: float | None
    ebit_margin: float | None
    ebitda_margin: float | None
    net_margin: float | None
    dy: float | None
    net_debt_ebitda: float | None
    debt_to_equity: float | None
    current_ratio: float | None
    valuation_graham: float | None
    valuation_bazin: float | None


def compute_all(raw: RawFinancials) -> ComputedIndicators:
    debt = total_debt(raw.short_term_debt, raw.long_term_debt)
    cash = cash_position(raw.cash_and_equivalents, raw.short_term_investments)
    mkt_cap = market_cap(raw.current_price, raw.shares_outstanding)
    earnings_per_share = eps(raw.net_income, raw.shares_outstanding)
    book_value_per_share = bvps(raw.equity, raw.shares_outstanding)
    dps = _safe_div(raw.dividends_paid_ttm, raw.shares_outstanding)

    return ComputedIndicators(
        market_cap=mkt_cap,
        eps=earnings_per_share,
        bvps=book_value_per_share,
        p_l=pl_ratio(raw.current_price, earnings_per_share),
        p_vp=pvp_ratio(raw.current_price, book_value_per_share),
        ev_ebitda=ev_ebitda(mkt_cap, debt, cash, raw.ebitda),
        roe=roe(raw.net_income, raw.equity),
        roic=roic(raw.ebit, raw.income_tax_expense, raw.pretax_income, raw.equity, debt, cash),
        gross_margin=gross_margin(raw.gross_profit, raw.revenue),
        ebit_margin=ebit_margin(raw.ebit, raw.revenue),
        ebitda_margin=ebitda_margin(raw.ebitda, raw.revenue),
        net_margin=net_margin(raw.net_income, raw.revenue),
        dy=dividend_yield(raw.dividends_paid_ttm, raw.shares_outstanding, raw.current_price),
        net_debt_ebitda=net_debt_to_ebitda(debt, cash, raw.ebitda),
        debt_to_equity=debt_to_equity(debt, raw.equity),
        current_ratio=current_ratio(raw.current_assets, raw.current_liabilities),
        valuation_graham=graham_fair_value(earnings_per_share, book_value_per_share),
        valuation_bazin=bazin_fair_value(dps),
    )
