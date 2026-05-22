"""drop_r2_mirror_columns

Revision ID: i0d1e2f3g4h5
Revises: h9c0d1e2f3g4
Create Date: 2026-05-22 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "i0d1e2f3g4h5"
down_revision: str | Sequence[str] | None = "h9c0d1e2f3g4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE lake_ri_documents
            DROP COLUMN IF EXISTS r2_public_url,
            DROP COLUMN IF EXISTS r2_key
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE lake_ri_documents
            ADD COLUMN IF NOT EXISTS r2_key VARCHAR(500),
            ADD COLUMN IF NOT EXISTS r2_public_url VARCHAR(1000)
    """)
