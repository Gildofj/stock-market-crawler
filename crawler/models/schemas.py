from datetime import datetime

from pydantic import BaseModel


class StockPriceSchema(BaseModel):
    time: datetime
    open: float | None
    high: float | None
    low: float | None
    close: float
    adj_close: float | None
    volume: int | None


class CompanySchema(BaseModel):
    symbol: str
    name: str | None = None
    sector: str | None = None
    sub_sector: str | None = None
    segment: str | None = None
    is_active: int = 1


class FundamentalSchema(BaseModel):
    p_l: float | None = None
    p_vp: float | None = None
    ev_ebitda: float | None = None
    roe: float | None = None
    roic: float | None = None
    net_margin: float | None = None
    dy: float | None = None
    liquid_debt_ebitda: float | None = None
    cagr_revenue_5y: float | None = None
    cagr_profit_5y: float | None = None
