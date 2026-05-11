import uuid
from datetime import datetime

from sqlalchemy import (
    BIGINT,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
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
