"""add_data_lake

Revision ID: a1f2e3d4c5b6
Revises: 0d4f0e29bab8
Create Date: 2026-05-16 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a1f2e3d4c5b6"
down_revision: str | Sequence[str] | None = "0d4f0e29bab8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email       VARCHAR(255) NOT NULL UNIQUE,
            is_premium  BOOLEAN NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS lake_news (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source        VARCHAR(50) NOT NULL,
            title         VARCHAR(500) NOT NULL,
            summary       TEXT,
            url           VARCHAR(1000) NOT NULL UNIQUE,
            url_hash      VARCHAR(64) NOT NULL UNIQUE,
            sentiment     VARCHAR(20),
            published_at  TIMESTAMPTZ,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_lake_news_published ON lake_news(published_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lake_news_hash ON lake_news(url_hash)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS lake_news_tickers (
            news_id  UUID NOT NULL REFERENCES lake_news(id) ON DELETE CASCADE,
            ticker   VARCHAR(10) NOT NULL,
            PRIMARY KEY (news_id, ticker)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_lake_news_tickers_ticker ON lake_news_tickers(ticker)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS lake_ri_documents (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            doc_id          VARCHAR(100) NOT NULL UNIQUE,
            company_id      UUID REFERENCES companies(id) ON DELETE SET NULL,
            ticker          VARCHAR(10) NOT NULL,
            category        VARCHAR(20) NOT NULL,
            title           VARCHAR(500) NOT NULL,
            pdf_url         VARCHAR(1000),
            text_excerpt    TEXT,
            reference_date  DATE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_lake_ri_ticker ON lake_ri_documents(ticker)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_lake_ri_company_date "
        "ON lake_ri_documents(company_id, reference_date DESC)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS lake_insight_cache (
            ticker        VARCHAR(10) PRIMARY KEY,
            insight       JSONB,
            score         NUMERIC(5, 2),
            dy_adjusted   NUMERIC(8, 2),
            pl_adjusted   NUMERIC(10, 2),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at    TIMESTAMPTZ
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS portfolios (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name        VARCHAR(100) NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_portfolios_user ON portfolios(user_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_assets (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            portfolio_id  UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
            ticker        VARCHAR(10) NOT NULL,
            quantity      NUMERIC(18, 6) NOT NULL,
            avg_price     NUMERIC(12, 4) NOT NULL,
            asset_type    VARCHAR(20),
            notes         VARCHAR(500),
            added_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_portfolio_assets_portfolio "
        "ON portfolio_assets(portfolio_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS portfolio_assets")
    op.execute("DROP TABLE IF EXISTS portfolios")
    op.execute("DROP TABLE IF EXISTS lake_insight_cache")
    op.execute("DROP TABLE IF EXISTS lake_ri_documents")
    op.execute("DROP TABLE IF EXISTS lake_news_tickers")
    op.execute("DROP TABLE IF EXISTS lake_news")
    op.execute("DROP TABLE IF EXISTS users")
