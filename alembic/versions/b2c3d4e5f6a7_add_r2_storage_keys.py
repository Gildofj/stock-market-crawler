"""add_r2_storage_keys

Adds object-storage references for RI PDFs (public bucket) and portfolio
spreadsheet uploads (private bucket). All columns are nullable so the
migration is safe on existing rows and the system keeps working when R2 is
not configured.

Revision ID: b2c3d4e5f6a7
Revises: a1f2e3d4c5b6
Create Date: 2026-05-16 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1f2e3d4c5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE lake_ri_documents
            ADD COLUMN IF NOT EXISTS r2_key VARCHAR(500),
            ADD COLUMN IF NOT EXISTS r2_public_url VARCHAR(1000)
    """)
    op.execute("""
        ALTER TABLE portfolios
            ADD COLUMN IF NOT EXISTS source_r2_key VARCHAR(500),
            ADD COLUMN IF NOT EXISTS source_filename VARCHAR(255),
            ADD COLUMN IF NOT EXISTS source_content_type VARCHAR(100)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE portfolios
            DROP COLUMN IF EXISTS source_content_type,
            DROP COLUMN IF EXISTS source_filename,
            DROP COLUMN IF EXISTS source_r2_key
    """)
    op.execute("""
        ALTER TABLE lake_ri_documents
            DROP COLUMN IF EXISTS r2_public_url,
            DROP COLUMN IF EXISTS r2_key
    """)
