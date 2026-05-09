from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from decimal import Decimal

class CompanyBase(BaseModel):
    symbol: str
    name: Optional[str] = None
    sector: Optional[str] = None
    sub_sector: Optional[str] = None
    segment: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None

class CompanyRead(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

class StockPriceRead(BaseModel):
    time: date
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Decimal
    volume: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)

class FundamentalRead(BaseModel):
    # Valuation
    p_l: Optional[Decimal] = None
    p_vp: Optional[Decimal] = None
    ev_ebitda: Optional[Decimal] = None

    # Profitability
    roe: Optional[Decimal] = None
    roic: Optional[Decimal] = None
    net_margin: Optional[Decimal] = None

    # Dividends
    dy: Optional[Decimal] = None

    # Debt
    liquid_debt_ebitda: Optional[Decimal] = None

    # Growth
    cagr_revenue_5y: Optional[Decimal] = None
    cagr_profit_5y: Optional[Decimal] = None

    # New Fields for AI Analysis
    debt_to_equity: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None
    eps: Optional[Decimal] = None

    # Calculated
    valuation_graham: Optional[Decimal] = None
    valuation_bazin: Optional[Decimal] = None

    quality_score: Optional[Decimal] = None
    collected_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TickerDetail(BaseModel):
    company: CompanyRead
    latest_fundamental: Optional[FundamentalRead] = None
    recent_prices: List[StockPriceRead] = []
