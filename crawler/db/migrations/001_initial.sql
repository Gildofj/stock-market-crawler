-- ============================================================
-- 001_initial.sql
-- B3 Stock Market Crawler - Initial Database Schema
-- Requires: TimescaleDB extension
-- ============================================================

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================
-- COMPANIES
-- Master table of all B3-listed companies
-- ============================================================
CREATE TABLE IF NOT EXISTS companies (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(10) NOT NULL UNIQUE,
    name        VARCHAR(255),
    sector      VARCHAR(100),
    sub_sector  VARCHAR(100),
    segment     VARCHAR(100),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_companies_symbol ON companies(symbol);

-- ============================================================
-- STOCK PRICES (TimescaleDB Hypertable)
-- Stores OHLCV daily price data
-- Partitioned automatically by time (TimescaleDB)
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_prices (
    time        TIMESTAMPTZ NOT NULL,
    company_id  INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    open        NUMERIC(12, 4),
    high        NUMERIC(12, 4),
    low         NUMERIC(12, 4),
    close       NUMERIC(12, 4) NOT NULL,
    adj_close   NUMERIC(12, 4),
    volume      BIGINT,
    PRIMARY KEY (time, company_id)
);

-- Convert to TimescaleDB hypertable, partitioned by time (1 chunk per month)
SELECT create_hypertable(
    'stock_prices',
    'time',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- Enable compression for data older than 3 months
ALTER TABLE stock_prices SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'company_id'
);

SELECT add_compression_policy('stock_prices', INTERVAL '3 months', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_stock_prices_company ON stock_prices(company_id, time DESC);

-- ============================================================
-- FUNDAMENTAL INDICATORS
-- Stores fundamental/valuation data per collection date
-- Immutable append-only (never overwrite historical data)
-- ============================================================
CREATE TABLE IF NOT EXISTS fundamentals (
    id                   SERIAL PRIMARY KEY,
    company_id           INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

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

-- Continuous aggregate: latest fundamentals per company
-- This view gives you the most recent set of indicators for each company
CREATE MATERIALIZED VIEW IF NOT EXISTS latest_fundamentals AS
    SELECT DISTINCT ON (company_id)
        f.*,
        c.symbol,
        c.name,
        c.sector
    FROM fundamentals f
    JOIN companies c ON c.id = f.company_id
    ORDER BY company_id, collected_at DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_latest_fundamentals_company
    ON latest_fundamentals(company_id);
