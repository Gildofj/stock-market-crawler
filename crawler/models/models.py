import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BIGINT,
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..services.database import Base


class DataSource(Base):
    """Canonical registry of every third-party data source the crawler talks to.

    Used for three things:

    * UI attribution — every API response can join here to expose ``via X``
      with a clickable link back to the source homepage.
    * DMCA / takedown response — flipping ``enabled`` to False stops new
      collection from that source immediately (no deploy) and lets the
      operator filter affected rows via the per-table ``source_id`` FK.
    * Public transparency endpoint (`GET /sources`) so anyone can audit
      which feeds power the deployment.
    """

    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Short stable identifier used in code (e.g. ``'cvm'``, ``'infomoney'``).
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    homepage_url: Mapped[str] = mapped_column(String(500), nullable=False)
    tos_url: Mapped[str | None] = mapped_column(String(500))
    # 'public-domain' | 'rss-fair-use' | 'tos-restricted' | 'unknown'
    license_label: Mapped[str | None] = mapped_column(String(60))
    legal_basis: Mapped[str | None] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    # 'low' | 'medium' | 'high' — informal heuristic; see DISCLAIMER.md.
    risk_tier: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    # Operator kill switch: spiders skip on False, /sources hides on False.
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    sector: Mapped[str | None] = mapped_column(String(100))
    sub_sector: Mapped[str | None] = mapped_column(String(100))
    segment: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[int] = mapped_column(Integer, default=1)  # 1 for Active, 0 for Inactive
    logo_url: Mapped[str | None] = mapped_column(String(500))
    website: Mapped[str | None] = mapped_column(String(255))
    # Provenance: which spider populated the metadata (name/sector/logo).
    # Nullable for legacy rows; new rows should populate via SourceRegistry.
    metadata_source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("data_sources.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    prices: Mapped[list["StockPrice"]] = relationship("StockPrice", back_populates="company")
    fundamentals: Mapped[list["Fundamental"]] = relationship(
        "Fundamental", back_populates="company"
    )
    reliability: Mapped["CompanyReliability | None"] = relationship(
        "CompanyReliability", back_populates="company", uselist=False
    )
    metadata_source: Mapped["DataSource | None"] = relationship(
        "DataSource", foreign_keys=[metadata_source_id]
    )


class StockPrice(Base):
    __tablename__ = "stock_prices"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    open: Mapped[float | None] = mapped_column(Numeric(12, 4))
    high: Mapped[float | None] = mapped_column(Numeric(12, 4))
    low: Mapped[float | None] = mapped_column(Numeric(12, 4))
    close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    adj_close: Mapped[float | None] = mapped_column(Numeric(12, 4))
    volume: Mapped[int | None] = mapped_column(BIGINT)
    # Provenance: which spider produced this row (e.g. yfinance, b3). Nullable
    # for legacy rows. Populated via SourceRegistry from new spiders.
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("data_sources.id", ondelete="SET NULL")
    )

    __table_args__ = (PrimaryKeyConstraint("time", "company_id"),)

    company: Mapped["Company"] = relationship("Company", back_populates="prices")
    source: Mapped["DataSource | None"] = relationship("DataSource")


class Fundamental(Base):
    __tablename__ = "fundamentals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )

    # Valuation
    p_l: Mapped[float | None] = mapped_column(Numeric(10, 2))
    p_vp: Mapped[float | None] = mapped_column(Numeric(10, 2))
    ev_ebitda: Mapped[float | None] = mapped_column(Numeric(10, 2))

    # Profitability
    roe: Mapped[float | None] = mapped_column(Numeric(8, 2))
    roic: Mapped[float | None] = mapped_column(Numeric(8, 2))
    net_margin: Mapped[float | None] = mapped_column(Numeric(8, 2))

    # Dividends
    dy: Mapped[float | None] = mapped_column(Numeric(8, 2))

    # Debt
    liquid_debt_ebitda: Mapped[float | None] = mapped_column(Numeric(10, 2))

    # Growth
    cagr_revenue_5y: Mapped[float | None] = mapped_column(Numeric(8, 2))
    cagr_profit_5y: Mapped[float | None] = mapped_column(Numeric(8, 2))

    # New Fields for AI Analysis
    debt_to_equity: Mapped[float | None] = mapped_column(Numeric(10, 2))
    market_cap: Mapped[float | None] = mapped_column(Numeric(20, 2))
    eps: Mapped[float | None] = mapped_column(Numeric(10, 2))

    # Calculated
    valuation_graham: Mapped[float | None] = mapped_column(Numeric(12, 4))
    valuation_bazin: Mapped[float | None] = mapped_column(Numeric(12, 4))

    quality_score: Mapped[int | None] = mapped_column(Integer)
    # Provenance: the *last* spider to touch this snapshot in the enrichment
    # chain (b3 prices → cvm fundamentals). For per-field attribution,
    # `contributing_sources` lists every slug that contributed.
    primary_source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("data_sources.id", ondelete="SET NULL")
    )
    contributing_sources: Mapped[list[str] | None] = mapped_column(JSON)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    company: Mapped["Company"] = relationship("Company", back_populates="fundamentals")
    primary_source: Mapped["DataSource | None"] = relationship("DataSource")


class MLFeature(Base):
    __tablename__ = "ml_features"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )

    # Technical Indicators
    sma_20: Mapped[float] = mapped_column(Numeric(12, 4))
    sma_50: Mapped[float] = mapped_column(Numeric(12, 4))
    rsi_14: Mapped[float] = mapped_column(Numeric(12, 4))
    volatility_20: Mapped[float] = mapped_column(Numeric(12, 4))

    # Fundamental Ratios at the time
    p_l_ratio: Mapped[float | None] = mapped_column(Numeric(12, 4))

    target_next_day_change: Mapped[float] = mapped_column(Numeric(12, 4))  # For Training

    __table_args__ = (PrimaryKeyConstraint("time", "company_id"),)

    company: Mapped["Company"] = relationship("Company")


class CompanyReliability(Base):
    __tablename__ = "company_reliability"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Sub-scores (0-100 cada)
    profit_consistency_score: Mapped[int | None] = mapped_column(SmallInteger)
    debt_control_score: Mapped[int | None] = mapped_column(SmallInteger)
    tag_along_score: Mapped[int | None] = mapped_column(SmallInteger)
    perennial_sector_score: Mapped[int | None] = mapped_column(SmallInteger)

    # Evidências brutas para auditoria
    profitable_years_verified: Mapped[int | None] = mapped_column(SmallInteger)
    max_years_available: Mapped[int | None] = mapped_column(SmallInteger)
    debt_snapshots_compliant: Mapped[int | None] = mapped_column(SmallInteger)
    debt_snapshots_total: Mapped[int | None] = mapped_column(SmallInteger)
    tag_along_pct: Mapped[int | None] = mapped_column(SmallInteger)
    is_perennial_sector: Mapped[bool | None] = mapped_column(Boolean)

    # Output final
    reliability_score: Mapped[int | None] = mapped_column(SmallInteger)
    reliability_grade: Mapped[str | None] = mapped_column(String(3))

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped["Company"] = relationship("Company", back_populates="reliability")


class LakeNews(Base):
    __tablename__ = "lake_news"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Legacy free-form source label (e.g. "infomoney"). Kept for backwards
    # compatibility; new code should prefer the FK below for provenance.
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    sentiment: Mapped[str | None] = mapped_column(String(20))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    # Canonical provenance link. Nullable so existing rows are not blocked;
    # populated for every new row via SourceRegistry.
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("data_sources.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tickers: Mapped[list["LakeNewsTicker"]] = relationship(
        "LakeNewsTicker", back_populates="news", cascade="all, delete-orphan"
    )
    data_source: Mapped["DataSource | None"] = relationship("DataSource")


class LakeNewsTicker(Base):
    __tablename__ = "lake_news_tickers"

    news_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lake_news.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    __table_args__ = (PrimaryKeyConstraint("news_id", "ticker"),)

    news: Mapped["LakeNews"] = relationship("LakeNews", back_populates="tickers")


class LakeRIDocument(Base):
    __tablename__ = "lake_ri_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL")
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(String(1000))
    text_excerpt: Mapped[str | None] = mapped_column(Text)
    reference_date: Mapped[date | None] = mapped_column(Date)
    # Legacy: mirror columns kept for backwards compatibility; new rows leave
    # them NULL (see ``crawler/services/storage_service.py`` upload_ri_pdf).
    r2_key: Mapped[str | None] = mapped_column(String(500))
    r2_public_url: Mapped[str | None] = mapped_column(String(1000))
    # Always CVM today, but keeping the FK lets the operator disable RI
    # collection centrally via the registry kill-switch.
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("data_sources.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    data_source: Mapped["DataSource | None"] = relationship("DataSource")


class LakeInsightCache(Base):
    __tablename__ = "lake_insight_cache"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    insight: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    dy_adjusted: Mapped[float | None] = mapped_column(Numeric(8, 2))
    pl_adjusted: Mapped[float | None] = mapped_column(Numeric(10, 2))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
