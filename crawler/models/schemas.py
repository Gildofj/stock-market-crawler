import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StockPriceSchema(BaseModel):
    """Schema for historical stock price data points."""

    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    time: datetime = Field(..., description="Timestamp of the price point")
    open: float | None = Field(None, description="Opening price")
    high: float | None = Field(None, description="Highest price of the session")
    low: float | None = Field(None, description="Lowest price of the session")
    close: float = Field(..., description="Closing price")
    adj_close: float | None = Field(None, description="Adjusted closing price")
    volume: int | None = Field(None, description="Trading volume")


class CompanySchema(BaseModel):
    """Schema for company profile and metadata."""

    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique internal identifier")
    symbol: str = Field(..., description="Stock ticker symbol")
    name: str | None = Field(None, description="Company full name")
    sector: str | None = Field(None, description="Economic sector")
    sub_sector: str | None = Field(None, description="Economic sub-sector")
    segment: str | None = Field(None, description="Market segment")
    logo_url: str | None = Field(None, description="URL for company logo")
    website: str | None = Field(None, description="Company website URL")
    is_active: int = Field(1, description="Status (1: active, 0: inactive)")


class FundamentalSchema(BaseModel):
    """Schema for fundamental indicators and valuation metrics."""

    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    p_l: float | None = Field(None, description="Price to Earnings ratio")
    p_vp: float | None = Field(None, description="Price to Book Value ratio")
    ev_ebitda: float | None = Field(None, description="Enterprise Value / EBITDA")
    roe: float | None = Field(None, description="Return on Equity (%)")
    roic: float | None = Field(None, description="Return on Invested Capital (%)")
    net_margin: float | None = Field(None, description="Net Profit Margin (%)")
    dy: float | None = Field(None, description="Dividend Yield (%)")
    liquid_debt_ebitda: float | None = Field(None, description="Net Debt / EBITDA ratio")
    cagr_revenue_5y: float | None = Field(None, description="Revenue CAGR (5Y) (%)")
    cagr_profit_5y: float | None = Field(None, description="Profit CAGR (5Y) (%)")
    debt_to_equity: float | None = Field(None, description="Debt to Equity ratio")
    market_cap: float | None = Field(None, description="Total Market Capitalization")
    eps: float | None = Field(None, description="Earnings Per Share")
    valuation_graham: float | None = Field(None, description="Graham Fair Value Price")
    valuation_bazin: float | None = Field(None, description="Bazin Fair Value Price")
    quality_score: int | None = Field(None, description="Composite Quality Score")
