"""enable pg_trgm for fuzzy search

Revision ID: 0d4f0e29bab8
Revises: c9d48ed38fc7
Create Date: 2026-05-11 15:26:59.167861

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0d4f0e29bab8"
down_revision: str | Sequence[str] | None = "c9d48ed38fc7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
