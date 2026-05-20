import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from core.models.schemas import LakeNewsSchema


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


class ReliabilityResponse(BaseModel):
    company_id: uuid.UUID
    profit_consistency_score: int | None = None
    debt_control_score: int | None = None
    tag_along_score: int | None = None
    perennial_sector_score: int | None = None
    profitable_years_verified: int | None = None
    max_years_available: int | None = None
    debt_snapshots_compliant: int | None = None
    debt_snapshots_total: int | None = None
    tag_along_pct: int | None = None
    is_perennial_sector: bool | None = None
    reliability_score: int | None = None
    reliability_grade: str | None = None
    computed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TickerDetail(BaseModel):
    company: CompanyRead
    latest_fundamental: FundamentalRead | None = None
    recent_prices: list[StockPriceRead] = []


class PortfolioSnapshotItem(BaseModel):
    """One entry in the batch portfolio snapshot.

    `found=False` means the symbol was not present in the companies table.
    All optional sections are returned as null so callers can render a
    placeholder without re-parsing an error envelope.
    """

    symbol: str
    found: bool
    company: CompanyRead | None = None
    fundamentals: FundamentalRead | None = None
    reliability: ReliabilityResponse | None = None
    news: list[LakeNewsSchema] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PortfolioSnapshotResponse(BaseModel):
    items: list[PortfolioSnapshotItem]
    requested: int
    found: int
    missing: list[str] = Field(default_factory=list)
