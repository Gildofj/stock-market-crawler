import uuid
from sqlalchemy import (
    BIGINT,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Uuid,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..services.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255))
    sector = Column(String(100))
    sub_sector = Column(String(100))
    segment = Column(String(100))
    is_active = Column(Integer, default=1) # 1 for Active, 0 for Inactive
    logo_url = Column(String(500))
    website = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    prices = relationship("StockPrice", back_populates="company")
    fundamentals = relationship("Fundamental", back_populates="company")


class StockPrice(Base):
    __tablename__ = "stock_prices"

    time = Column(DateTime(timezone=True), nullable=False)
    company_id = Column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    open = Column(Numeric(12, 4))
    high = Column(Numeric(12, 4))
    low = Column(Numeric(12, 4))
    close = Column(Numeric(12, 4), nullable=False)
    adj_close = Column(Numeric(12, 4))
    volume = Column(BIGINT)

    __table_args__ = (PrimaryKeyConstraint("time", "company_id"),)

    company = relationship("Company", back_populates="prices")


class Fundamental(Base):
    __tablename__ = "fundamentals"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)

    # Valuation
    p_l = Column(Numeric(10, 2))
    p_vp = Column(Numeric(10, 2))
    ev_ebitda = Column(Numeric(10, 2))

    # Profitability
    roe = Column(Numeric(8, 2))
    roic = Column(Numeric(8, 2))
    net_margin = Column(Numeric(8, 2))

    # Dividends
    dy = Column(Numeric(8, 2))

    # Debt
    liquid_debt_ebitda = Column(Numeric(10, 2))

    # Growth
    cagr_revenue_5y = Column(Numeric(8, 2))
    cagr_profit_5y = Column(Numeric(8, 2))

    # New Fields for AI Analysis
    debt_to_equity = Column(Numeric(10, 2))
    market_cap = Column(Numeric(20, 2))
    eps = Column(Numeric(10, 2))

    # Calculated
    valuation_graham = Column(Numeric(12, 4))
    valuation_bazin = Column(Numeric(12, 4))

    quality_score = Column(Integer)
    collected_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="fundamentals")


class MLFeature(Base):
    __tablename__ = "ml_features"

    time = Column(DateTime(timezone=True), nullable=False)
    company_id = Column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)

    # Technical Indicators
    sma_20 = Column(Numeric(12, 4))
    sma_50 = Column(Numeric(12, 4))
    rsi_14 = Column(Numeric(12, 4))
    volatility_20 = Column(Numeric(12, 4))

    # Fundamental Ratios at the time
    p_l_ratio = Column(Numeric(12, 4))

    target_next_day_change = Column(Numeric(12, 4))  # For Training

    __table_args__ = (PrimaryKeyConstraint("time", "company_id"),)

    company = relationship("Company")
