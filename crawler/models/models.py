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

    __table_args__ = (PrimaryKeyConstraint("time", "company_id"),)

    company: Mapped["Company"] = relationship("Company", back_populates="prices")


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
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    company: Mapped["Company"] = relationship("Company", back_populates="fundamentals")


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


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    portfolios: Mapped[list["Portfolio"]] = relationship(
        "Portfolio", back_populates="user", cascade="all, delete-orphan"
    )


class LakeNews(Base):
    __tablename__ = "lake_news"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    sentiment: Mapped[str | None] = mapped_column(String(20))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tickers: Mapped[list["LakeNewsTicker"]] = relationship(
        "LakeNewsTicker", back_populates="news", cascade="all, delete-orphan"
    )


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
    r2_key: Mapped[str | None] = mapped_column(String(500))
    r2_public_url: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Reference to the original spreadsheet uploaded by the user (stored in
    # the private R2 bucket). None when the portfolio was created from JSON.
    source_r2_key: Mapped[str | None] = mapped_column(String(500))
    source_filename: Mapped[str | None] = mapped_column(String(255))
    source_content_type: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="portfolios")
    assets: Mapped[list["PortfolioAsset"]] = relationship(
        "PortfolioAsset", back_populates="portfolio", cascade="all, delete-orphan"
    )


class PortfolioAsset(Base):
    __tablename__ = "portfolio_assets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    avg_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    asset_type: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(String(500))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="assets")
