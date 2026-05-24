"""widen_delta_pct

Revision ID: j1e2f3g4h5i6
Revises: i0d1e2f3g4h5
Create Date: 2026-05-23 22:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "j1e2f3g4h5i6"
down_revision: str | Sequence[str] | None = "i0d1e2f3g4h5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE lake_indicator_reconciliation
        ALTER COLUMN delta_pct TYPE NUMERIC(20, 8);
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE lake_indicator_reconciliation
        ALTER COLUMN delta_pct TYPE NUMERIC(10, 4);
    """)
