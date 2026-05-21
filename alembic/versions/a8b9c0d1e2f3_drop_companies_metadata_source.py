"""drop_companies_metadata_source

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-05-21 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a8b9c0d1e2f3"
down_revision: str | Sequence[str] | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE companies DROP COLUMN IF EXISTS metadata_source_id")


def downgrade() -> None:
    op.execute("""
        ALTER TABLE companies
            ADD COLUMN IF NOT EXISTS metadata_source_id UUID
                REFERENCES data_sources(id) ON DELETE SET NULL
    """)
