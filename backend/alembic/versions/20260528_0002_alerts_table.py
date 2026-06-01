"""add alerts table

Revision ID: 20260528_0002
Revises: 20260524_0001
Create Date: 2026-05-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260528_0002"
down_revision = "20260524_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create persisted alert rows."""

    op.create_table(
        "alerts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("ticker", sa.String(length=40), nullable=False),
        sa.Column("condition", sa.String(length=40), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_ticker", "alerts", ["ticker"], unique=False)
    op.create_index("ix_alerts_user_id", "alerts", ["user_id"], unique=False)
    op.create_index("ix_alerts_user_status", "alerts", ["user_id", "status"], unique=False)


def downgrade() -> None:
    """Drop persisted alert rows."""

    op.drop_index("ix_alerts_user_status", table_name="alerts")
    op.drop_index("ix_alerts_user_id", table_name="alerts")
    op.drop_index("ix_alerts_ticker", table_name="alerts")
    op.drop_table("alerts")
