"""Cached model signal snapshot for list views.

This module runs the trained XGBoost model across the latest row for each
ticker, giving stock lists and overview pages real model-derived signals
without recomputing full SHAP explanations per card.
"""

from __future__ import annotations

import logging
import json
import os
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.db.crud import load_macro_asi, load_prices, public_ticker
from app.services.backend_model_config import get_backend_model_config
from app.services.feature_engineer import FeatureEngineer
from app.services.lstm_predictor import DEFAULT_MODEL_PATH as LSTM_MODEL_PATH
from app.services.lstm_predictor import DEFAULT_SCALER_PATH as LSTM_SCALER_PATH
from app.services.lstm_predictor import LSTMPredictor
from app.services.news_sentiment import SENTIMENT_SUMMARY_PATH, latest_sentiment_for_ticker
from app.services.risk_analyzer import RiskAnalyzer
from app.services.xgboost_predictor import (
    MODELS_ROOT_FEATURE_LIST_PATH,
    MODELS_ROOT_XGB_MODEL_PATH,
    PRIMARY_FEATURE_LIST_PATH,
    PRIMARY_XGB_MODEL_PATH,
    action_from_probability,
    confidence_from_probability,
    load_xgb_feature_list,
    predict_with_xgboost,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = PROJECT_ROOT / "models" / "model_signal_snapshot.json"
MODEL_PATH = (
    PRIMARY_XGB_MODEL_PATH
    if PRIMARY_XGB_MODEL_PATH.exists()
    else MODELS_ROOT_XGB_MODEL_PATH
    if MODELS_ROOT_XGB_MODEL_PATH.exists()
    else PROJECT_ROOT / "models" / "xgboost_classification_model.pkl"
)
FEATURES_PATH = (
    PRIMARY_FEATURE_LIST_PATH
    if PRIMARY_FEATURE_LIST_PATH.exists()
    else MODELS_ROOT_FEATURE_LIST_PATH
    if MODELS_ROOT_FEATURE_LIST_PATH.exists()
    else PROJECT_ROOT / "models" / "feature_list.json"
)
PRICE_DATA_PATH = PROJECT_ROOT / "data" / "output" / "processed" / "prices" / "historical_consolidated.parquet"


@dataclass(frozen=True)
class ModelSignal:
    """Model-derived signal for one latest ticker row."""

    ticker: str
    public_symbol: str
    probability: float
    recommendation: str
    outlook: str
    confidence: float
    risk_score: float
    model_version: str
    lstm_probability: float | None = None
    lstm_model_version: str | None = None
    sentiment_score: float = 0.0
    sentiment_label: str = "neutral"


@lru_cache(maxsize=1)
def get_model_signal_snapshot() -> dict[str, ModelSignal]:
    """Return cached latest XGBoost signals keyed by canonical ticker.

    Dashboard list endpoints must stay fast, but they should still display real
    model-derived signals. If no valid persisted snapshot exists, build one
    once and cache it in memory/disk instead of falling back to fake neutral
    values.
    """

    stored_snapshot = _load_stored_snapshot()
    if stored_snapshot and _is_production():
        logger.info("Using packaged model signal snapshot in production")
        return stored_snapshot
    if stored_snapshot and not _snapshot_is_stale():
        return stored_snapshot
    if stored_snapshot:
        logger.info("Stored model signal snapshot is stale; rebuilding stock-list signals")
    else:
        logger.info("No model signal snapshot available; building stock-list signals from XGBoost")
    return rebuild_model_signal_snapshot()


def rebuild_model_signal_snapshot() -> dict[str, ModelSignal]:
    """Rebuild latest XGBoost signals and persist them for fast page loads."""

    prices = load_prices()
    feature_result = FeatureEngineer().engineer(prices, scale=False)
    latest_indices = feature_result.features.groupby("ticker", group_keys=False).tail(1).index
    latest_features = feature_result.features.loc[latest_indices].reset_index(drop=True)
    model_features = feature_result.model_features.loc[latest_indices].reset_index(drop=True)

    try:
        _, feature_list_path = load_xgb_feature_list()
    except Exception as exc:
        logger.warning("No XGBoost feature list available for model signal snapshot: %s", exc)
        return {}

    config = get_backend_model_config()
    use_lstm = bool(config.get("use_lstm", False))
    lstm_predictor = LSTMPredictor() if use_lstm else None
    prices_by_ticker = {str(ticker).upper(): group.copy() for ticker, group in prices.groupby("ticker", sort=False)}
    features_by_ticker = {str(ticker).upper(): group.copy() for ticker, group in latest_features.groupby("ticker", sort=False)}
    risk_analyzer = RiskAnalyzer()
    macro_df = load_macro_asi()
    snapshot: dict[str, ModelSignal] = {}
    for index, row in latest_features.iterrows():
        ticker = str(row["ticker"]).upper()
        try:
            xgb_prediction = predict_with_xgboost(model_features.iloc[[index]])
        except Exception as exc:
            logger.warning("Skipping snapshot signal for %s: %s", ticker, exc)
            continue
        probability = xgb_prediction.up_probability
        lstm_probability = None
        lstm_model_version = "disabled"
        model_source = "xgboost_only"
        if lstm_predictor is not None:
            lstm_probability, lstm_model_version = lstm_predictor.predict_probability(prices_by_ticker.get(ticker, pd.DataFrame()))
            if lstm_probability is not None:
                xgb_weight = float(config.get("xgb_weight", 0.80))
                lstm_weight = float(config.get("lstm_weight", 0.20))
                total_weight = xgb_weight + lstm_weight
                if total_weight > 0:
                    probability = ((probability * xgb_weight) + (lstm_probability * lstm_weight)) / total_weight
                    model_source = "xgboost_lstm_weighted"
        sentiment = latest_sentiment_for_ticker(ticker)
        risk_score = _snapshot_risk_score(risk_analyzer, features_by_ticker.get(ticker, pd.DataFrame()), ticker, row, macro_df)
        confidence = confidence_from_probability(probability)
        recommendation = _final_recommendation(probability, confidence, risk_score, sentiment.score)
        snapshot[ticker] = ModelSignal(
            ticker=ticker,
            public_symbol=public_ticker(ticker),
            probability=round(probability, 3),
            recommendation=recommendation,
            outlook=_recommendation_to_outlook(recommendation),
            confidence=round(confidence * 100, 1),
            risk_score=risk_score,
            model_version=model_source,
            lstm_probability=round(lstm_probability, 3) if lstm_probability is not None else None,
            lstm_model_version=lstm_model_version,
            sentiment_score=round(sentiment.score, 3),
            sentiment_label=sentiment.label,
        )
    logger.info("Built model signal snapshot for %s tickers", len(snapshot))
    _save_stored_snapshot(snapshot)
    return snapshot


def _load_stored_snapshot() -> dict[str, ModelSignal]:
    """Load persisted model signals if they match current model/data artifacts."""

    if not SNAPSHOT_PATH.exists():
        return {}
    try:
        payload = json.loads(SNAPSHOT_PATH.read_text())
        if payload.get("schema") != 4:
            return {}
        signals = payload.get("signals", {})
        snapshot = {ticker: ModelSignal(**values) for ticker, values in signals.items()}
        logger.info("Loaded stored model signal snapshot for %s tickers", len(snapshot))
        return snapshot
    except Exception as exc:
        logger.warning("Failed to load stored model signal snapshot: %s", exc)
        return {}


def _save_stored_snapshot(snapshot: dict[str, ModelSignal]) -> None:
    """Persist model signals for reuse across backend restarts."""

    try:
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": 4,
            "signals": {ticker: asdict(signal) for ticker, signal in snapshot.items()},
        }
        SNAPSHOT_PATH.write_text(json.dumps(payload, indent=2))
        logger.info("Saved model signal snapshot to %s", SNAPSHOT_PATH)
    except Exception as exc:
        logger.warning("Failed to save model signal snapshot: %s", exc)


def _snapshot_is_stale() -> bool:
    """Return true when source artifacts are newer than the persisted snapshot."""

    if not SNAPSHOT_PATH.exists():
        return True
    snapshot_mtime = SNAPSHOT_PATH.stat().st_mtime
    for source in (MODEL_PATH, FEATURES_PATH, PRICE_DATA_PATH, LSTM_MODEL_PATH, LSTM_SCALER_PATH, SENTIMENT_SUMMARY_PATH):
        if source.exists() and source.stat().st_mtime > snapshot_mtime:
            return True
    return False


def _is_production() -> bool:
    env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
    return env not in {"development", "dev", "test", "testing", "local"}


def _snapshot_risk_score(
    risk_analyzer: RiskAnalyzer,
    ticker_features: pd.DataFrame,
    ticker: str,
    latest_row: pd.Series,
    macro_df: pd.DataFrame | None,
) -> float:
    """Use the production risk engine for list signals, with a quick fallback."""

    try:
        return risk_analyzer.analyze(ticker_features, ticker, macro_df=macro_df).risk_score
    except Exception as exc:
        logger.warning("Risk analyzer failed for snapshot signal %s; using quick risk fallback: %s", ticker, exc)
        return _quick_risk_score(latest_row)


def _final_recommendation(probability: float, confidence: float, risk_score: float, sentiment_score: float) -> str:
    """Mirror the detailed recommendation filters so list cards and detail pages agree."""

    recommendation = action_from_probability(probability)
    if recommendation == "BUY" and risk_score >= 70:
        return "HOLD"
    if recommendation == "BUY" and sentiment_score < -0.5:
        return "HOLD"
    if recommendation in {"BUY", "SELL"} and confidence < 0.16:
        return "HOLD"
    return recommendation


def _predict_probabilities(model: Any, model_features: pd.DataFrame) -> np.ndarray:
    """Predict class-1 probabilities with a trained sklearn-style model."""

    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(model_features)
        classes = list(getattr(model, "classes_", []))
        positive_index = classes.index(1) if 1 in classes else probabilities.shape[1] - 1
        return np.asarray(probabilities[:, positive_index], dtype=float).clip(0.05, 0.95)
    predictions = model.predict(model_features)
    return np.asarray(predictions, dtype=float).clip(0.05, 0.95)


def _quick_risk_score(row: pd.Series) -> float:
    """Estimate latest-row risk for fast list views."""

    close = _float(row.get("close"), 0.0)
    high = _float(row.get("high"), close)
    low = _float(row.get("low"), close)
    pclose = _float(row.get("pclose"), close) or close
    change_pct = 0.0 if pclose == 0 else abs((close - pclose) / pclose) * 100
    intraday_range = 0.0 if close == 0 else max((high - low) / close * 100, 0.0)
    volatility = _float(row.get("volatility_20"), 0.0) * 25
    score = 25 + min(intraday_range * 3.0, 25) + min(change_pct * 2.0, 20) + min(volatility, 30)
    return round(max(0.0, min(100.0, score)), 1)


def _recommendation_to_outlook(recommendation: str) -> str:
    """Map rule-engine recommendation to frontend outlook."""

    if recommendation == "BUY":
        return "bullish"
    if recommendation in {"SELL", "AVOID"}:
        return "bearish"
    return "neutral"


def _float(value: object, default: float = 0.0) -> float:
    """Safely convert values to finite floats."""

    try:
        if pd.isna(value):
            return default
        parsed = float(value)
        if np.isfinite(parsed):
            return parsed
        return default
    except (TypeError, ValueError):
        return default
