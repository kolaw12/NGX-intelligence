"""add account settings and api tokens

Revision ID: 20260602_0003
Revises: 20260528_0002
Create Date: 2026-06-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260602_0003"
down_revision = "20260528_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create persisted user settings and personal API token metadata."""

    op.create_table(
        "user_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "key", name="uq_user_settings_user_key"),
    )
    op.create_index("ix_user_settings_user_id", "user_settings", ["user_id"], unique=False)

    op.create_table(
        "api_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("token_prefix", sa.String(length=24), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_api_tokens_user_id", "api_tokens", ["user_id"], unique=False)
    op.create_index("ix_api_tokens_token_prefix", "api_tokens", ["token_prefix"], unique=False)
    op.create_index("ix_api_tokens_user_revoked", "api_tokens", ["user_id", "revoked_at"], unique=False)


def downgrade() -> None:
    """Drop persisted user settings and personal API token metadata."""

    op.drop_index("ix_api_tokens_user_revoked", table_name="api_tokens")
    op.drop_index("ix_api_tokens_token_prefix", table_name="api_tokens")
    op.drop_index("ix_api_tokens_user_id", table_name="api_tokens")
    op.drop_table("api_tokens")
    op.drop_index("ix_user_settings_user_id", table_name="user_settings")
    op.drop_table("user_settings")
