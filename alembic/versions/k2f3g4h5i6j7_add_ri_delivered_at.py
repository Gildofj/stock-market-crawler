"""add_ri_delivered_at

Revision ID: k2f3g4h5i6j7
Revises: j1e2f3g4h5i6
Create Date: 2026-05-23 23:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "k2f3g4h5i6j7"
down_revision: str | Sequence[str] | None = "j1e2f3g4h5i6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lake_ri_documents",
        sa.Column("delivered_at", sa.Date(), nullable=True),
    )
    op.create_index(
        "ix_lake_ri_documents_delivered_at",
        "lake_ri_documents",
        ["delivered_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_lake_ri_documents_delivered_at", table_name="lake_ri_documents")
    op.drop_column("lake_ri_documents", "delivered_at")
