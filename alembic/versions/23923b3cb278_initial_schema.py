"""initial_schema

Revision ID: 23923b3cb278
Revises: 
Create Date: 2026-05-09 11:23:04.019899

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '23923b3cb278'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Companies Table
    op.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id          SERIAL PRIMARY KEY,
            symbol      VARCHAR(10) NOT NULL UNIQUE,
            name        VARCHAR(255),
            sector      VARCHAR(100),
            sub_sector  VARCHAR(100),
            segment     VARCHAR(100),
            is_active   INTEGER NOT NULL DEFAULT 1,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_companies_symbol ON companies(symbol)")

    # 2. Stock Prices Table (Standard Postgres for Cloud compatibility)
    op.execute("""
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
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_stock_prices_company ON stock_prices(company_id, time DESC)")

    # 3. Fundamentals Table
    op.execute("""
        CREATE TABLE IF NOT EXISTS fundamentals (
            id                   SERIAL PRIMARY KEY,
            company_id           INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            p_l                  NUMERIC(10, 2),
            p_vp                 NUMERIC(10, 2),
            ev_ebitda            NUMERIC(10, 2),
            roe                  NUMERIC(8, 2),
            roic                 NUMERIC(8, 2),
            net_margin           NUMERIC(8, 2),
            dy                   NUMERIC(8, 2),
            liquid_debt_ebitda   NUMERIC(10, 2),
            cagr_revenue_5y      NUMERIC(8, 2),
            cagr_profit_5y       NUMERIC(8, 2),
            valuation_graham     NUMERIC(12, 4),
            valuation_bazin      NUMERIC(12, 4),
            quality_score        SMALLINT,
            collected_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_fundamentals_company_date ON fundamentals(company_id, collected_at DESC)")

    # 4. Latest Fundamentals View
    op.execute("""
        CREATE OR REPLACE VIEW latest_fundamentals AS
            SELECT DISTINCT ON (company_id)
                f.*,
                c.symbol,
                c.name,
                c.sector
            FROM fundamentals f
            JOIN companies c ON c.id = f.company_id
            ORDER BY company_id, collected_at DESC;
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS latest_fundamentals")
    op.execute("DROP TABLE IF EXISTS fundamentals")
    op.execute("DROP TABLE IF EXISTS stock_prices")
    op.execute("DROP TABLE IF EXISTS companies")
