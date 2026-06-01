"""initial schema

Revision ID: 20260524_0001
Revises:
Create Date: 2026-05-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260524_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial API bridge tables."""

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("subscription_plan", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "stock_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(length=40), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open_price", sa.Float(), nullable=True),
        sa.Column("high_price", sa.Float(), nullable=True),
        sa.Column("low_price", sa.Float(), nullable=True),
        sa.Column("close_price", sa.Float(), nullable=False),
        sa.Column("previous_close", sa.Float(), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("daily_change", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "trade_date", name="uq_stock_prices_ticker_trade_date"),
    )
    op.create_index("ix_stock_prices_ticker", "stock_prices", ["ticker"], unique=False)
    op.create_index("ix_stock_prices_trade_date", "stock_prices", ["trade_date"], unique=False)
    op.create_index("ix_stock_prices_ticker_trade_date", "stock_prices", ["ticker", "trade_date"], unique=False)

    recommendation_enum = sa.Enum("BUY", "HOLD", "SELL", "AVOID", "WATCHLIST", name="recommendationaction")
    risk_enum = sa.Enum("LOW", "MEDIUM", "HIGH", name="risklevel")
    strength_enum = sa.Enum("WEAK", "MODERATE", "STRONG", name="signalstrength")

    op.create_table(
        "recommendation_signals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ticker", sa.String(length=40), nullable=False),
        sa.Column("signal_date", sa.Date(), nullable=False),
        sa.Column("recommendation", recommendation_enum, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("risk_level", risk_enum, nullable=False),
        sa.Column("signal_strength", strength_enum, nullable=False),
        sa.Column("ensemble_prob", sa.Float(), nullable=False),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("sentiment_label", sa.String(length=40), nullable=True),
        sa.Column("xgb_probability", sa.Float(), nullable=True),
        sa.Column("lstm_probability", sa.Float(), nullable=True),
        sa.Column("sector_adjustment", sa.Float(), nullable=True),
        sa.Column("explanation", sa.JSON(), nullable=False),
        sa.Column("feature_snapshot", sa.JSON(), nullable=True),
        sa.Column("model_versions", sa.JSON(), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recommendation_signals_ticker", "recommendation_signals", ["ticker"], unique=False)
    op.create_index("ix_recommendation_signals_signal_date", "recommendation_signals", ["signal_date"], unique=False)
    op.create_index("ix_recommendation_signals_ticker_signal_date", "recommendation_signals", ["ticker", "signal_date"], unique=False)
    op.create_index("ix_recommendation_signals_recommendation", "recommendation_signals", ["recommendation"], unique=False)

    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("ticker", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "ticker", name="uq_watchlist_items_user_ticker"),
    )
    op.create_index("ix_watchlist_items_user_id", "watchlist_items", ["user_id"], unique=False)
    op.create_index("ix_watchlist_items_ticker", "watchlist_items", ["ticker"], unique=False)

    op.create_table(
        "portfolio_positions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("ticker", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("average_cost", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "ticker", name="uq_portfolio_positions_user_ticker"),
    )
    op.create_index("ix_portfolio_positions_user_id", "portfolio_positions", ["user_id"], unique=False)
    op.create_index("ix_portfolio_positions_ticker", "portfolio_positions", ["ticker"], unique=False)


def downgrade() -> None:
    """Drop initial API bridge tables."""

    op.drop_index("ix_portfolio_positions_ticker", table_name="portfolio_positions")
    op.drop_index("ix_portfolio_positions_user_id", table_name="portfolio_positions")
    op.drop_table("portfolio_positions")
    op.drop_index("ix_watchlist_items_ticker", table_name="watchlist_items")
    op.drop_index("ix_watchlist_items_user_id", table_name="watchlist_items")
    op.drop_table("watchlist_items")
    op.drop_index("ix_recommendation_signals_recommendation", table_name="recommendation_signals")
    op.drop_index("ix_recommendation_signals_ticker_signal_date", table_name="recommendation_signals")
    op.drop_index("ix_recommendation_signals_signal_date", table_name="recommendation_signals")
    op.drop_index("ix_recommendation_signals_ticker", table_name="recommendation_signals")
    op.drop_table("recommendation_signals")
    op.drop_index("ix_stock_prices_ticker_trade_date", table_name="stock_prices")
    op.drop_index("ix_stock_prices_trade_date", table_name="stock_prices")
    op.drop_index("ix_stock_prices_ticker", table_name="stock_prices")
    op.drop_table("stock_prices")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
