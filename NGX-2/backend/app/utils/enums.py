"""Shared enum definitions for NGX AI Advisor layers.

This module keeps cross-layer vocabulary consistent without forcing service
modules to import ORM models or initialize database configuration.
"""

from __future__ import annotations

import enum


class RecommendationAction(str, enum.Enum):
    """Supported recommendation outcomes returned by the AI advisor."""

    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    AVOID = "AVOID"
    WATCHLIST = "WATCHLIST"


class SignalStrength(str, enum.Enum):
    """Human-readable strength labels for recommendation signals."""

    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"


class RiskLevel(str, enum.Enum):
    """Risk severity labels for stock and portfolio analysis."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
