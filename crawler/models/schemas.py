from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class StockPriceSchema(BaseModel):
    time: datetime
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: float
    adj_close: Optional[float]
    volume: Optional[int]

class CompanySchema(BaseModel):
    symbol: str
    name: Optional[str] = None
    sector: Optional[str] = None
    sub_sector: Optional[str] = None
    segment: Optional[str] = None

class FundamentalSchema(BaseModel):
    p_l: Optional[float] = None
    p_vp: Optional[float] = None
    ev_ebitda: Optional[float] = None
    roe: Optional[float] = None
    roic: Optional[float] = None
    net_margin: Optional[float] = None
    dy: Optional[float] = None
    liquid_debt_ebitda: Optional[float] = None
    cagr_revenue_5y: Optional[float] = None
    cagr_profit_5y: Optional[float] = None
