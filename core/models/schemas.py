import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StockPriceSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    time: datetime
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    adj_close: float | None = None
    volume: int | None = None
    source_id: uuid.UUID | None = None


class CompanySchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    id: uuid.UUID | None = None
    symbol: str
    name: str | None = None
    sector: str | None = None
    sub_sector: str | None = None
    segment: str | None = None
    logo_url: str | None = None
    website: str | None = None
    is_active: int = 1
    cnpj: str | None = None
    cd_cvm: str | None = None
    asset_type: str | None = None
    underlying_ticker: str | None = None


class FundamentalSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

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
    debt_to_equity: float | None = None
    market_cap: float | None = None
    eps: float | None = None
    valuation_graham: float | None = None
    valuation_bazin: float | None = None
    quality_score: int | None = None
    asset_type: str = "EQUITY"
    primary_source_id: uuid.UUID | None = None
    contributing_sources: list[str] = Field(default_factory=list)
    provenance: dict[str, str] | None = Field(default_factory=dict)


class SourceAttributionSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    slug: str
    display_name: str
    homepage_url: str
    original_url: str | None = None


class LakeNewsSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    id: uuid.UUID | None = None
    source: str
    title: str
    summary: str | None = None
    url: str
    url_hash: str
    sentiment: str | None = None
    published_at: datetime | None = None
    tickers: list[str] = Field(default_factory=list)


class LakeRIDocumentSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    id: uuid.UUID | None = None
    doc_id: str
    ticker: str
    category: str
    title: str
    pdf_url: str | None = None
    reference_date: date | None = None
    delivered_at: date | None = None
    pdf_source: str = "CVM (dados.cvm.gov.br)"
    source_id: uuid.UUID | None = None


class LakeRIDocumentInternalSchema(LakeRIDocumentSchema):
    text_excerpt: str | None = None


class LakeInsightSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    ticker: str
    insight: dict[str, Any] | None = None
    score: float | None = None
    dy_adjusted: float | None = None
    pl_adjusted: float | None = None
    updated_at: datetime | None = None
    expires_at: datetime | None = None


class LakeIndicatorReconciliationSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    id: uuid.UUID | None = None
    company_id: uuid.UUID
    ticker: str
    indicator: str
    source_slug: str = "yfinance_info"
    source_field: str | None = None
    source_value_raw: float | None = None
    source_value_normalised: float | None = None
    cvm_value: float | None = None
    delta_abs: float | None = None
    delta_pct: float | None = None
    is_outlier: bool = False
    collected_at: datetime | None = None
