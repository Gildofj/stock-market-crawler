-- ============================================================
-- 001_initial.sql
-- B3 Stock Market Crawler - Initial Database Schema
-- Standard PostgreSQL (Compatible with Local & Supabase)
-- ============================================================

-- Enable Extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- COMPANIES
-- Master table of all B3-listed companies
-- ============================================================
CREATE TABLE IF NOT EXISTS companies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol      VARCHAR(10) NOT NULL UNIQUE,
    name        VARCHAR(255),
    sector      VARCHAR(100),
    sub_sector  VARCHAR(100),
    segment     VARCHAR(100),
    logo_url    VARCHAR(500),
    website     VARCHAR(255),
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_companies_symbol ON companies(symbol);

-- ============================================================
-- STOCK PRICES
-- Stores OHLCV daily price data
-- Using standard PostgreSQL table for maximum compatibility
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_prices (
    time        TIMESTAMPTZ NOT NULL,
    company_id  UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    open        NUMERIC(12, 4),
    high        NUMERIC(12, 4),
    low         NUMERIC(12, 4),
    close       NUMERIC(12, 4) NOT NULL,
    adj_close   NUMERIC(12, 4),
    volume      BIGINT,
    PRIMARY KEY (time, company_id)
);

CREATE INDEX IF NOT EXISTS idx_stock_prices_company ON stock_prices(company_id, time DESC);

-- ============================================================
-- FUNDAMENTAL INDICATORS
-- Stores fundamental/valuation data per collection date
-- ============================================================
CREATE TABLE IF NOT EXISTS fundamentals (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id           UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

    -- Valuation
    p_l                  NUMERIC(10, 2),   -- Price / Earnings
    p_vp                 NUMERIC(10, 2),   -- Price / Book Value
    ev_ebitda            NUMERIC(10, 2),   -- EV / EBITDA

    -- Profitability
    roe                  NUMERIC(8, 2),    -- Return on Equity (%)
    roic                 NUMERIC(8, 2),    -- Return on Invested Capital (%)
    net_margin           NUMERIC(8, 2),    -- Net Profit Margin (%)

    -- Dividends
    dy                   NUMERIC(8, 2),    -- Dividend Yield (%)

    -- Debt
    liquid_debt_ebitda   NUMERIC(10, 2),   -- Net Debt / EBITDA

    -- Growth
    cagr_revenue_5y      NUMERIC(8, 2),    -- 5-year Revenue CAGR (%)
    cagr_profit_5y       NUMERIC(8, 2),    -- 5-year Profit CAGR (%)

    -- New Fields for AI Analysis (BACKEND_ENHANCEMENT_PLAN)
    debt_to_equity       NUMERIC(10, 2),
    market_cap           NUMERIC(20, 2),
    eps                  NUMERIC(10, 2),

    -- Calculated Valuations
    valuation_graham     NUMERIC(12, 4),   -- Graham Fair Value Price
    valuation_bazin      NUMERIC(12, 4),   -- Bazin Fair Value Price

    -- Custom composite score (0-100)
    quality_score        SMALLINT,

    -- When this data was collected
    collected_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fundamentals_company_date
    ON fundamentals(company_id, collected_at DESC);

-- ============================================================
-- ML FEATURES
-- ============================================================
CREATE TABLE IF NOT EXISTS ml_features (
    time                    TIMESTAMPTZ NOT NULL,
    company_id              UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    sma_20                  NUMERIC(12, 4),
    sma_50                  NUMERIC(12, 4),
    rsi_14                  NUMERIC(12, 4),
    volatility_20           NUMERIC(12, 4),
    p_l_ratio               NUMERIC(12, 4),
    target_next_day_change  NUMERIC(12, 4),
    PRIMARY KEY (time, company_id)
);

CREATE INDEX IF NOT EXISTS idx_ml_features_company ON ml_features(company_id, time DESC);

-- Continuous aggregate: latest fundamentals per company
CREATE OR REPLACE VIEW latest_fundamentals 
WITH (security_invoker = true)
AS
    SELECT DISTINCT ON (company_id)
        f.*,
        c.symbol,
        c.name,
        c.sector
    FROM fundamentals f
    JOIN companies c ON c.id = f.company_id
    ORDER BY company_id, collected_at DESC;
