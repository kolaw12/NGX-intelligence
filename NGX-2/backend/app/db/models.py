"""API bridge layer ORM models.

This module defines the database schema used by recommendation, stock, auth,
watchlist, and portfolio routers. It connects upstream intelligence outputs to
PostgreSQL/Supabase persistence and downstream React API responses.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.utils.enums import RecommendationAction, RiskLevel, SignalStrength


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for audit columns."""

    return datetime.now(timezone.utc)


def new_uuid() -> str:
    """Return a string UUID suitable for database primary keys."""

    return str(uuid4())


class User(Base):
    """Application user for auth, watchlists, portfolios, and saved recommendations."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    subscription_plan: Mapped[str] = mapped_column(String(50), nullable=False, default="basic")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    watchlist_items: Mapped[list["WatchlistItem"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    portfolio_positions: Mapped[list["PortfolioPosition"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    recommendation_signals: Mapped[list["RecommendationSignal"]] = relationship(back_populates="user")
    settings: Mapped[list["UserSetting"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    api_tokens: Mapped[list["ApiToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserSetting(Base):
    """Persisted per-user UI and notification settings."""

    __tablename__ = "user_settings"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_user_settings_user_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    user: Mapped[User] = relationship(back_populates="settings")


class ApiToken(Base):
    """Hashed personal access token metadata for account API access."""

    __tablename__ = "api_tokens"
    __table_args__ = (Index("ix_api_tokens_user_revoked", "user_id", "revoked_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="api_tokens")


class StockPrice(Base):
    """Normalized daily OHLCV record consumed by the processing and API layers."""

    __tablename__ = "stock_prices"
    __table_args__ = (
        UniqueConstraint("ticker", "trade_date", name="uq_stock_prices_ticker_trade_date"),
        Index("ix_stock_prices_ticker_trade_date", "ticker", "trade_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    open_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    high_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    low_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    close_price: Mapped[float] = mapped_column(Float, nullable=False)
    previous_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="data_layer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class RecommendationSignal(Base):
    """Persisted AI recommendation response served to the React dashboard."""

    __tablename__ = "recommendation_signals"
    __table_args__ = (
        Index("ix_recommendation_signals_ticker_signal_date", "ticker", "signal_date"),
        Index("ix_recommendation_signals_recommendation", "recommendation"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    ticker: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    signal_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    recommendation: Mapped[RecommendationAction] = mapped_column(Enum(RecommendationAction), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), nullable=False, default=RiskLevel.MEDIUM)
    signal_strength: Mapped[SignalStrength] = mapped_column(Enum(SignalStrength), nullable=False)
    ensemble_prob: Mapped[float] = mapped_column(Float, nullable=False)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    xgb_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    lstm_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    sector_adjustment: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    feature_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    model_versions: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    user: Mapped[User | None] = relationship(back_populates="recommendation_signals")


class WatchlistItem(Base):
    """Per-user stock watchlist entry for frontend monitoring workflows."""

    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("user_id", "ticker", name="uq_watchlist_items_user_ticker"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    user: Mapped[User] = relationship(back_populates="watchlist_items")


class PortfolioPosition(Base):
    """Per-user holding used by portfolio analytics and risk scoring."""

    __tablename__ = "portfolio_positions"
    __table_args__ = (UniqueConstraint("user_id", "ticker", name="uq_portfolio_positions_user_ticker"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    average_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    user: Mapped[User] = relationship(back_populates="portfolio_positions")


class Alert(Base):
    """Per-user price or AI signal alert used by frontend monitoring workflows."""

    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_user_status", "user_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    condition: Mapped[str] = mapped_column(String(40), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    user: Mapped[User] = relationship(back_populates="alerts")
