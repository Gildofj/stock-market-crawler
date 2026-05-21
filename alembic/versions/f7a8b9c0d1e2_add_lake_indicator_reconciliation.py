"""add_lake_indicator_reconciliation

Revision ID: f7a8b9c0d1e2
Revises: 51af735b37cb
Create Date: 2026-05-19 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str | Sequence[str] | None = "51af735b37cb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS lake_indicator_reconciliation (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id              UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            ticker                  VARCHAR(10) NOT NULL,
            indicator               VARCHAR(40) NOT NULL,
            source_slug             VARCHAR(40) NOT NULL DEFAULT 'yfinance_info',
            source_field            VARCHAR(60),
            source_value_raw        NUMERIC(20, 8),
            source_value_normalised NUMERIC(20, 8),
            cvm_value               NUMERIC(20, 8),
            delta_abs               NUMERIC(20, 8),
            delta_pct               NUMERIC(10, 4),
            is_outlier              BOOLEAN NOT NULL DEFAULT FALSE,
            collected_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_lake_recon_company "
        "ON lake_indicator_reconciliation(company_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_lake_recon_ticker ON lake_indicator_reconciliation(ticker)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_lake_recon_indicator "
        "ON lake_indicator_reconciliation(indicator)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_lake_recon_collected "
        "ON lake_indicator_reconciliation(collected_at)"
    )
    # Dominant ML query: history of one indicator for one ticker, in order.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_lake_recon_ticker_indicator_time "
        "ON lake_indicator_reconciliation(ticker, indicator, collected_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS lake_indicator_reconciliation")
