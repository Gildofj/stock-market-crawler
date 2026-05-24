"""add_asset_taxonomy

Revision ID: l3g4h5i6j7k8
Revises: k2f3g4h5i6j7
Create Date: 2026-05-24 00:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "l3g4h5i6j7k8"
down_revision: str | Sequence[str] | None = "k2f3g4h5i6j7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("cnpj", sa.String(length=14), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("cd_cvm", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("asset_type", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("underlying_ticker", sa.String(length=20), nullable=True),
    )
    op.create_index("ix_companies_cnpj", "companies", ["cnpj"])
    op.create_index("ix_companies_asset_type", "companies", ["asset_type"])

    op.add_column(
        "fundamentals",
        sa.Column(
            "asset_type",
            sa.String(length=20),
            nullable=False,
            server_default="EQUITY",
        ),
    )
    op.create_index("ix_fundamentals_asset_type", "fundamentals", ["asset_type"])


def downgrade() -> None:
    op.drop_index("ix_fundamentals_asset_type", table_name="fundamentals")
    op.drop_column("fundamentals", "asset_type")
    op.drop_index("ix_companies_asset_type", table_name="companies")
    op.drop_index("ix_companies_cnpj", table_name="companies")
    op.drop_column("companies", "underlying_ticker")
    op.drop_column("companies", "asset_type")
    op.drop_column("companies", "cd_cvm")
    op.drop_column("companies", "cnpj")
