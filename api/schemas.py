from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CompanyBase(BaseModel):
    symbol: str
    name: str | None = None
    sector: str | None = None
    sub_sector: str | None = None
    segment: str | None = None
    logo_url: str | None = None
    website: str | None = None

class CompanyRead(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

class StockPriceRead(BaseModel):
    time: datetime
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    volume: int | None = None

    model_config = ConfigDict(from_attributes=True)

class FundamentalRead(BaseModel):
    # Valuation
    p_l: Decimal | None = None
    p_vp: Decimal | None = None
    ev_ebitda: Decimal | None = None

    # Profitability
    roe: Decimal | None = None
    roic: Decimal | None = None
    net_margin: Decimal | None = None

    # Dividends
    dy: Decimal | None = None

    # Debt
    liquid_debt_ebitda: Decimal | None = None

    # Growth
    cagr_revenue_5y: Decimal | None = None
    cagr_profit_5y: Decimal | None = None

    # New Fields for AI Analysis
    debt_to_equity: Decimal | None = None
    market_cap: Decimal | None = None
    eps: Decimal | None = None

    # Calculated
    valuation_graham: Decimal | None = None
    valuation_bazin: Decimal | None = None

    quality_score: Decimal | None = None
    collected_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TickerDetail(BaseModel):
    company: CompanyRead
    latest_fundamental: FundamentalRead | None = None
    recent_prices: list[StockPriceRead] = []
