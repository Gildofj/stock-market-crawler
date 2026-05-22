"""compliance_and_stability

Revision ID: h9c0d1e2f3g4
Revises: g8b9c0d1e2f3
Create Date: 2026-05-21 21:26:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h9c0d1e2f3g4"
down_revision: str | Sequence[str] | None = "g8b9c0d1e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add provenance JSONB column to fundamentals
    op.add_column("fundamentals", sa.Column("provenance", sa.JSON(), nullable=True))

    # Create data_source_audit_log table
    op.create_table(
        "data_source_audit_log",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("data_source_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("operator", sa.String(length=255), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("affected_rowcount", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("data_source_audit_log")
    op.drop_column("fundamentals", "provenance")
