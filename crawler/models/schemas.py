from datetime import datetime

from pydantic import BaseModel, Field


class StockPriceSchema(BaseModel):
    """Schema for historical stock price data points."""
    time: datetime = Field(..., description="Timestamp of the price data point")
    open: float | None = Field(None, description="Opening price")
    high: float | None = Field(None, description="Highest price during the period")
    low: float | None = Field(None, description="Lowest price during the period")
    close: float = Field(..., description="Closing price")
    adj_close: float | None = Field(None, description="Adjusted closing price")
    volume: int | None = Field(None, description="Trading volume")


class CompanySchema(BaseModel):
    """Schema for company metadata."""
    symbol: str = Field(..., description="Stock ticker symbol")
    name: str | None = Field(None, description="Full name of the company")
    sector: str | None = Field(None, description="Economic sector")
    sub_sector: str | None = Field(None, description="Industrial sub-sector")
    segment: str | None = Field(None, description="Business segment")
    logo_url: str | None = Field(None, description="URL for company logo")
    website: str | None = Field(None, description="Company website URL")
    is_active: int = Field(1, description="Binary flag for active status (1: active, 0: inactive)")


class FundamentalSchema(BaseModel):
    """Schema for company fundamental indicators."""
    p_l: float | None = Field(None, description="Price to Earnings ratio")
    p_vp: float | None = Field(None, description="Price to Book Value ratio")
    ev_ebitda: float | None = Field(None, description="Enterprise Value to EBITDA ratio")
    roe: float | None = Field(None, description="Return on Equity percentage")
    roic: float | None = Field(None, description="Return on Invested Capital percentage")
    net_margin: float | None = Field(None, description="Net Margin percentage")
    dy: float | None = Field(None, description="Dividend Yield percentage")
    liquid_debt_ebitda: float | None = Field(None, description="Net Debt to EBITDA ratio")
    cagr_revenue_5y: float | None = Field(None, description="5-Year Revenue CAGR percentage")
    cagr_profit_5y: float | None = Field(None, description="5-Year Profit CAGR percentage")
    debt_to_equity: float | None = Field(None, description="Debt to Equity ratio")
    market_cap: float | None = Field(None, description="Total Market Capitalization")
    eps: float | None = Field(None, description="Earnings Per Share")
