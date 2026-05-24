"""add_bdr_ratio

Revision ID: m4h5i6j7k8l9
Revises: l3g4h5i6j7k8
Create Date: 2026-05-24 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "m4h5i6j7k8l9"
down_revision: str | Sequence[str] | None = "l3g4h5i6j7k8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("bdr_ratio", sa.Numeric(10, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("companies", "bdr_ratio")
