"""API bridge layer read helpers.

This module provides repository-style helpers for loading NGX market data from
the existing data layer until PostgreSQL persistence is fully enabled. It
connects Parquet/master data to FastAPI stock and recommendation routers.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import RecommendationSignal
from app.utils.enums import RecommendationAction, RiskLevel, SignalStrength

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def invalidate_all_caches() -> None:
    """Clear all in-memory data caches so the next request reloads from disk."""
    load_prices.cache_clear()
    load_tickers.cache_clear()
    load_macro_asi.cache_clear()
    get_ticker_prices.cache_clear()
    _latest_by_ticker_from_partitioned_files.cache_clear()
    logger.info("All data caches cleared; next request will reload from disk")

PRICE_DATA_PATH = PROJECT_ROOT / "data" / "output" / "processed" / "prices" / "historical_consolidated.parquet"
HISTORICAL_PRICE_DIR = PROJECT_ROOT / "data" / "output" / "processed" / "prices" / "historical"
TICKERS_PATH = PROJECT_ROOT / "data" / "master" / "tickers.csv"
MACRO_ASI_PATH = PROJECT_ROOT / "data" / "output" / "processed" / "macro" / "broadstreet_index.parquet"

TICKER_ALIASES = {
    "ZENITHBANK": "ZEN",
    "GTCO": "GTB",
    "ACCESSCORP": "ACC",
    "FBNH": "FBN",
    "MTNN": "MTN",
    "AIRTELAFRI": "AAF",
    "NESTLE": "NES",
    "GUINNESS": "GUI",
    "NB": "NBL",
}
CANONICAL_TO_PUBLIC = {value: key for key, value in TICKER_ALIASES.items()}


def canonical_ticker(ticker: object) -> str:
    """Map public frontend symbols to data-layer ticker codes."""

    if not ticker or (isinstance(ticker, float)):
        return ""
    normalized = str(ticker).upper().strip()
    return TICKER_ALIASES.get(normalized, normalized)


def public_ticker(ticker: object) -> str:
    """Map data-layer ticker codes to public symbols where known."""

    if not ticker or (isinstance(ticker, float)):
        return ""
    normalized = str(ticker).upper().strip()
    return CANONICAL_TO_PUBLIC.get(normalized, normalized)


@lru_cache(maxsize=1)
def load_prices() -> pd.DataFrame:
    """Load and normalize consolidated historical price data."""

    if not PRICE_DATA_PATH.exists():
        raise FileNotFoundError(f"Price data not found: {PRICE_DATA_PATH}")
    logger.info("Loading consolidated price data from %s", PRICE_DATA_PATH)
    prices = pd.read_parquet(PRICE_DATA_PATH)
    prices.columns = [str(column).strip().lower() for column in prices.columns]
    prices["ticker"] = prices["ticker"].astype(str).str.upper().str.strip()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    for column in ["pclose", "high", "low", "close", "volume", "change"]:
        prices[column] = pd.to_numeric(prices[column], errors="coerce")
    prices = prices.dropna(subset=["ticker", "date", "close"]).sort_values(["ticker", "date"])
    logger.info("Loaded %s price rows across %s tickers", len(prices), prices["ticker"].nunique())
    return prices


@lru_cache(maxsize=1)
def load_tickers() -> pd.DataFrame:
    """Load ticker metadata from the master data file."""

    if not TICKERS_PATH.exists():
        raise FileNotFoundError(f"Ticker master file not found: {TICKERS_PATH}")
    logger.info("Loading ticker metadata from %s", TICKERS_PATH)
    tickers = pd.read_csv(TICKERS_PATH)
    tickers["ticker"] = tickers["ticker"].astype(str).str.upper().str.strip()
    return tickers


@lru_cache(maxsize=1)
def load_macro_asi() -> pd.DataFrame:
    """Load optional NGX ASI macro data for risk adjustments."""

    if not MACRO_ASI_PATH.exists():
        logger.warning("ASI macro data not found: %s", MACRO_ASI_PATH)
        return pd.DataFrame()
    return pd.read_parquet(MACRO_ASI_PATH)


@lru_cache(maxsize=512)
def get_ticker_prices(ticker: str) -> pd.DataFrame:
    """Return historical prices for a ticker using public or canonical symbol."""

    canonical = canonical_ticker(ticker)
    per_ticker_path = HISTORICAL_PRICE_DIR / f"{canonical}.parquet"
    if per_ticker_path.exists() and per_ticker_path.stat().st_size > 0:
        frame = pd.read_parquet(per_ticker_path)
        frame.columns = [str(column).strip().lower() for column in frame.columns]
        frame["ticker"] = canonical
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        for column in ["pclose", "high", "low", "close", "volume", "change"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.dropna(subset=["date", "close"]).sort_values("date")
        if not frame.empty:
            return frame.reset_index(drop=True)
    prices = load_prices()
    frame = prices[prices["ticker"].astype(str).str.upper() == canonical].copy()
    if frame.empty:
        raise KeyError(f"Ticker not found: {ticker}")
    return frame.sort_values("date").reset_index(drop=True)


def get_latest_by_ticker() -> pd.DataFrame:
    """Return the latest price row for every ticker."""

    latest_from_files = _latest_by_ticker_from_partitioned_files()
    if not latest_from_files.empty:
        return latest_from_files
    prices = load_prices()
    return prices.sort_values(["ticker", "date"]).groupby("ticker", as_index=False).tail(1).reset_index(drop=True)


@lru_cache(maxsize=1)
def _latest_by_ticker_from_partitioned_files() -> pd.DataFrame:
    """Return latest rows without holding the consolidated parquet in memory."""

    if not HISTORICAL_PRICE_DIR.exists():
        return pd.DataFrame()
    rows: list[pd.DataFrame] = []
    for path in HISTORICAL_PRICE_DIR.glob("*.parquet"):
        if path.name.startswith("_") or path.stat().st_size <= 0:
            continue
        try:
            frame = pd.read_parquet(path)
            if frame.empty:
                continue
            frame.columns = [str(column).strip().lower() for column in frame.columns]
            if "date" not in frame.columns or "close" not in frame.columns:
                continue
            frame["ticker"] = path.stem.upper()
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            frame = frame.dropna(subset=["date", "close"]).sort_values("date").tail(1)
            if not frame.empty:
                rows.append(frame)
        except Exception as exc:
            logger.warning("Skipping latest-row load for %s: %s", path, exc)
    if not rows:
        return pd.DataFrame()
    latest = pd.concat(rows, ignore_index=True)
    for column in ["pclose", "high", "low", "close", "volume", "change"]:
        if column not in latest.columns:
            latest[column] = 0.0
        latest[column] = pd.to_numeric(latest[column], errors="coerce")
    latest["ticker"] = latest["ticker"].astype(str).str.upper().str.strip()
    logger.info("Loaded %s latest price rows from partitioned files", len(latest))
    return latest.sort_values("ticker").reset_index(drop=True)


def get_ticker_metadata(ticker: str) -> dict[str, object]:
    """Return metadata for a ticker, or a minimal fallback if metadata is missing."""

    canonical = canonical_ticker(ticker)
    tickers = load_tickers()
    match = tickers[tickers["ticker"] == canonical]
    if match.empty:
        logger.warning("Ticker metadata not found for %s", ticker)
        return {"ticker": canonical, "name": public_ticker(canonical), "sector": "Unknown"}
    return match.iloc[0].to_dict()


def sector_slug(sector: str) -> str:
    """Convert sector names into frontend-friendly slugs."""

    return (
        str(sector)
        .lower()
        .replace("&", "and")
        .replace("/", "-")
        .replace(" ", "-")
        .replace("--", "-")
    )


def save_recommendation_signal(
    db: Session,
    recommendation: dict[str, Any],
    feature_snapshot: dict[str, Any] | None = None,
    model_versions: dict[str, Any] | None = None,
) -> RecommendationSignal | None:
    """Persist a generated recommendation signal without blocking API responses."""

    try:
        record = RecommendationSignal(
            ticker=str(recommendation["ticker"]).upper(),
            signal_date=pd.to_datetime(recommendation["date"]).date(),
            recommendation=RecommendationAction(str(recommendation["recommendation"])),
            confidence=float(recommendation["confidence"]),
            risk_score=float(recommendation["risk_score"]),
            risk_level=_risk_level_from_score(float(recommendation["risk_score"])),
            signal_strength=SignalStrength(str(recommendation["signal_strength"])),
            ensemble_prob=float(recommendation["ensemble_prob"]),
            sentiment_score=_optional_float(recommendation.get("sentiment_score")),
            sentiment_label=_optional_str(recommendation.get("sentiment_label")),
            xgb_probability=_optional_float(recommendation.get("xgb_probability")),
            lstm_probability=_optional_float(recommendation.get("lstm_probability")),
            sector_adjustment=_optional_float(recommendation.get("sector_adjustment")),
            explanation=dict(recommendation["explanation"]),
            feature_snapshot=feature_snapshot,
            model_versions=model_versions,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        logger.info("Persisted recommendation signal %s for %s", record.id, record.ticker)
        return record
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("Recommendation persistence skipped: %s", exc)
        return None


def _risk_level_from_score(risk_score: float) -> RiskLevel:
    """Map a risk score to the persisted risk level enum."""

    if risk_score < 35:
        return RiskLevel.LOW
    if risk_score < 65:
        return RiskLevel.MEDIUM
    return RiskLevel.HIGH


def _optional_float(value: Any) -> float | None:
    """Convert optional JSON payload values to floats for persistence."""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    """Convert optional JSON payload values to strings for persistence."""

    if value is None:
        return None
    return str(value)
