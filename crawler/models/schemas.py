import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StockPriceSchema(BaseModel):
    """Schema for historical stock price data points."""

    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    time: datetime = Field(..., description="Timestamp of the price point")
    open: float | None = Field(default=None, description="Opening price")
    high: float | None = Field(default=None, description="Highest price of the session")
    low: float | None = Field(default=None, description="Lowest price of the session")
    close: float = Field(..., description="Closing price")
    adj_close: float | None = Field(default=None, description="Adjusted closing price")
    volume: int | None = Field(default=None, description="Trading volume")


class CompanySchema(BaseModel):
    """Schema for company profile and metadata."""

    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    id: uuid.UUID | None = Field(default=None, description="Unique internal identifier")
    symbol: str = Field(..., description="Stock ticker symbol")
    name: str | None = Field(default=None, description="Company full name")
    sector: str | None = Field(default=None, description="Economic sector")
    sub_sector: str | None = Field(default=None, description="Economic sub-sector")
    segment: str | None = Field(default=None, description="Market segment")
    logo_url: str | None = Field(default=None, description="URL for company logo")
    website: str | None = Field(default=None, description="Company website URL")
    is_active: int = Field(default=1, description="Status (1: active, 0: inactive)")


class FundamentalSchema(BaseModel):
    """Schema for fundamental indicators and valuation metrics."""

    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    p_l: float | None = Field(default=None, description="Price to Earnings ratio")
    p_vp: float | None = Field(default=None, description="Price to Book Value ratio")
    ev_ebitda: float | None = Field(default=None, description="Enterprise Value / EBITDA")
    roe: float | None = Field(default=None, description="Return on Equity (%)")
    roic: float | None = Field(default=None, description="Return on Invested Capital (%)")
    net_margin: float | None = Field(default=None, description="Net Profit Margin (%)")
    dy: float | None = Field(default=None, description="Dividend Yield (%)")
    liquid_debt_ebitda: float | None = Field(default=None, description="Net Debt / EBITDA ratio")
    cagr_revenue_5y: float | None = Field(default=None, description="Revenue CAGR (5Y) (%)")
    cagr_profit_5y: float | None = Field(default=None, description="Profit CAGR (5Y) (%)")
    debt_to_equity: float | None = Field(default=None, description="Debt to Equity ratio")
    market_cap: float | None = Field(default=None, description="Total Market Capitalization")
    eps: float | None = Field(default=None, description="Earnings Per Share")
    valuation_graham: float | None = Field(default=None, description="Graham Fair Value Price")
    valuation_bazin: float | None = Field(default=None, description="Bazin Fair Value Price")
    quality_score: int | None = Field(default=None, description="Composite Quality Score")


class UserSchema(BaseModel):
    """Schema for user identity and premium status."""

    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User email")
    is_premium: bool = Field(default=False, description="Premium plan flag")


class SourceAttributionSchema(BaseModel):
    """Attribution block surfaced on every record that came from a third party.

    The front-end uses this to render "via {display_name}" with a link back
    to the original. The slug is also the kill-switch handle: if a takedown
    is filed and the operator sets ``data_sources.enabled=false``, the slug
    here still identifies which past records the complaint affected.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    slug: str = Field(..., description="Stable source identifier (e.g. 'cvm', 'infomoney').")
    display_name: str = Field(..., description="Human-readable source name shown in the UI.")
    homepage_url: str = Field(..., description="Source homepage; click-through target for 'via X'.")
    original_url: str | None = Field(
        default=None,
        description="Specific upstream URL for this record (e.g. CVM PDF, news article).",
    )


class LakeNewsSchema(BaseModel):
    """Schema for news item collected from RSS feeds.

    Attribution (``source`` + ``url``) is part of the contract: every news
    response surfaces both fields so the consumer can render "via {source}"
    with a click-through link.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    id: uuid.UUID | None = Field(default=None)
    source: str = Field(..., description="Feed source identifier (legacy free-form slug).")
    title: str = Field(..., description="News headline")
    summary: str | None = Field(default=None, description="News summary / excerpt")
    url: str = Field(..., description="Original article URL")
    url_hash: str = Field(..., description="MD5 hash of the URL")
    sentiment: str | None = Field(default=None, description="Sentiment label (filled by AI)")
    published_at: datetime | None = Field(default=None, description="Publication timestamp")
    tickers: list[str] = Field(default_factory=list, description="Tickers mentioned in the news")


class LakeRIDocumentSchema(BaseModel):
    """Public schema for an RI document (CVM filing).

    Intentionally omits ``text_excerpt`` and ``r2_public_url``:
    * ``text_excerpt`` lives in the DB so internal AI consumers can read it,
      but is not part of the public API contract.
    * ``r2_public_url`` is a legacy mirror field that is no longer populated.

    See ``LakeRIDocumentInternalSchema`` for the unfiltered variant intended
    for in-process consumers (LagoAI insight pipeline).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    id: uuid.UUID | None = Field(default=None)
    doc_id: str = Field(..., description="Unique CVM document identifier")
    ticker: str = Field(..., description="Associated ticker symbol")
    category: str = Field(..., description="Document category (ITR, DFP, IPE, etc.)")
    title: str = Field(..., description="Document title")
    pdf_url: str | None = Field(
        default=None,
        description="Upstream CVM PDF URL — canonical reference.",
    )
    reference_date: date | None = Field(default=None, description="Reference date of the document")
    pdf_source: str = Field(
        default="CVM (dados.cvm.gov.br)",
        description="Static attribution string for the original publisher.",
    )


class LakeRIDocumentInternalSchema(LakeRIDocumentSchema):
    """Internal RI schema with the full text excerpt + mirror fields.

    Used by in-process consumers (e.g. the LagoAI insight generator) that
    need the text body to reason about the filing. **Never** returned by
    public HTTP routes — they always use the parent class.
    """

    text_excerpt: str | None = Field(
        default=None, description="First chunk of extracted text (legacy column)."
    )
    r2_public_url: str | None = Field(
        default=None, description="Deprecated mirror URL — kept for backwards compat."
    )


class LakeInsightSchema(BaseModel):
    """Schema for cached AI insight per ticker."""

    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    ticker: str = Field(..., description="Ticker symbol")
    insight: dict[str, Any] | None = Field(default=None, description="Full AI insight payload")
    score: float | None = Field(default=None, description="AI quality score")
    dy_adjusted: float | None = Field(default=None, description="AI-adjusted Dividend Yield")
    pl_adjusted: float | None = Field(default=None, description="AI-adjusted P/L")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp")
    expires_at: datetime | None = Field(default=None, description="Cache expiration timestamp")


class PortfolioAssetInput(BaseModel):
    """Input schema for a single portfolio asset."""

    ticker: str = Field(..., description="Asset ticker symbol")
    quantity: float = Field(..., gt=0, description="Number of shares")
    avg_price: float = Field(..., gt=0, description="Average purchase price")
    asset_type: str | None = Field(default=None, description="Asset type (stock, fii, bdr)")
    notes: str | None = Field(default=None, max_length=500, description="User notes")


class PortfolioAssetSchema(BaseModel):
    """Schema for a portfolio asset row."""

    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    id: uuid.UUID | None = Field(default=None)
    ticker: str = Field(..., description="Asset ticker symbol")
    quantity: float = Field(..., description="Number of shares")
    avg_price: float = Field(..., description="Average purchase price")
    asset_type: str | None = Field(default=None)
    notes: str | None = Field(default=None)


class PortfolioCreateSchema(BaseModel):
    """Input schema for creating a portfolio via JSON body."""

    name: str = Field(..., min_length=1, max_length=100, description="Portfolio name")
    assets: list[PortfolioAssetInput] = Field(..., min_length=1, description="Portfolio assets")


class PortfolioSchema(BaseModel):
    """Schema for a portfolio with its assets."""

    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    id: uuid.UUID = Field(...)
    name: str = Field(...)
    assets: list[PortfolioAssetSchema] = Field(default_factory=list)
    source_filename: str | None = Field(
        default=None, description="Original spreadsheet filename (if uploaded)"
    )
    created_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)
