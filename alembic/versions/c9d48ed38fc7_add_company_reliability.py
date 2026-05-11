"""add_company_reliability

Revision ID: c9d48ed38fc7
Revises: 23923b3cb278
Create Date: 2026-05-11 13:26:50.372344

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d48ed38fc7"
down_revision: str | Sequence[str] | None = "23923b3cb278"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_reliability",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("profit_consistency_score", sa.SmallInteger(), nullable=True),
        sa.Column("debt_control_score", sa.SmallInteger(), nullable=True),
        sa.Column("tag_along_score", sa.SmallInteger(), nullable=True),
        sa.Column("perennial_sector_score", sa.SmallInteger(), nullable=True),
        sa.Column("profitable_years_verified", sa.SmallInteger(), nullable=True),
        sa.Column("max_years_available", sa.SmallInteger(), nullable=True),
        sa.Column("debt_snapshots_compliant", sa.SmallInteger(), nullable=True),
        sa.Column("debt_snapshots_total", sa.SmallInteger(), nullable=True),
        sa.Column("tag_along_pct", sa.SmallInteger(), nullable=True),
        sa.Column("is_perennial_sector", sa.Boolean(), nullable=True),
        sa.Column("reliability_score", sa.SmallInteger(), nullable=True),
        sa.Column("reliability_grade", sa.String(length=3), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id"),
    )
    op.create_index(
        "idx_reliability_score",
        "company_reliability",
        [sa.text("reliability_score DESC NULLS LAST")],
        unique=False,
    )
    op.create_index(
        "idx_reliability_grade",
        "company_reliability",
        ["reliability_grade"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_reliability_grade", table_name="company_reliability")
    op.drop_index("idx_reliability_score", table_name="company_reliability")
    op.drop_table("company_reliability")
