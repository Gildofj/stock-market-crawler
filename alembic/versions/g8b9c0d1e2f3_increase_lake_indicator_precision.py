"""increase_lake_indicator_precision

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-05-21 17:51:28.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "g8b9c0d1e2f3"
down_revision: str | Sequence[str] | None = "a8b9c0d1e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE lake_indicator_reconciliation
        ALTER COLUMN source_value_raw TYPE NUMERIC(30, 8),
        ALTER COLUMN source_value_normalised TYPE NUMERIC(30, 8),
        ALTER COLUMN cvm_value TYPE NUMERIC(30, 8),
        ALTER COLUMN delta_abs TYPE NUMERIC(30, 8);
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE lake_indicator_reconciliation
        ALTER COLUMN source_value_raw TYPE NUMERIC(20, 8),
        ALTER COLUMN source_value_normalised TYPE NUMERIC(20, 8),
        ALTER COLUMN cvm_value TYPE NUMERIC(20, 8),
        ALTER COLUMN delta_abs TYPE NUMERIC(20, 8);
    """)
