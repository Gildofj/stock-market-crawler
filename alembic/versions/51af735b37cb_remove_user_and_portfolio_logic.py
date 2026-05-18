"""remove_user_and_portfolio_logic

Revision ID: 51af735b37cb
Revises: e5f6a7b8c9d0
Create Date: 2026-05-17 15:36:24.384106

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '51af735b37cb'
down_revision: str | Sequence[str] | None = 'e5f6a7b8c9d0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Drop portfolio-related tables
    op.execute("DROP TABLE IF EXISTS portfolio_assets")
    op.execute("DROP TABLE IF EXISTS portfolios")

    # 2. Drop users table
    op.execute("DROP TABLE IF EXISTS users")


def downgrade() -> None:
    # 1. Recreate users table
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

    # 2. Recreate portfolios table
    op.execute("""
        CREATE TABLE IF NOT EXISTS portfolios (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name        VARCHAR(100) NOT NULL,
            source_r2_key VARCHAR(500),
            source_filename VARCHAR(255),
            source_content_type VARCHAR(100),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_portfolios_user ON portfolios(user_id)")

    # 3. Recreate portfolio_assets table
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
