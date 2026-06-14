"""XGBoost-first production inference helpers."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import joblib
import numpy as np
import pandas as pd

from app.services.backend_model_config import get_backend_model_config

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRIMARY_XGB_MODEL_PATH = PROJECT_ROOT / "models" / "xgboost" / "xgboost_model.pkl"
MODELS_ROOT_XGB_MODEL_PATH = PROJECT_ROOT / "models" / "xgboost_model.pkl"
LEGACY_XGB_MODEL_PATH = PROJECT_ROOT / "models" / "xgboost_classification_model.pkl"
PRIMARY_FEATURE_LIST_PATH = PROJECT_ROOT / "configs" / "xgb_feature_list.json"
MODELS_ROOT_FEATURE_LIST_PATH = PROJECT_ROOT / "models" / "xgb_feature_list.json"
LEGACY_FEATURE_LIST_PATH = PROJECT_ROOT / "models" / "feature_list.json"


class XGBoostInferenceError(RuntimeError):
    """Raised when XGBoost inference cannot proceed safely."""


@dataclass(frozen=True)
class XGBoostPrediction:
    """Clean XGBoost recommendation response."""

    action: str
    up_probability: float
    confidence: float
    main_model: str = "xgboost"
    model_source: str = "xgboost_only"
    reason: str = ""
    model_path: str = ""
    feature_list_path: str = ""
    feature_count: int = 0
    filled_missing_features: list[str] = field(default_factory=list)


def warmup_xgboost() -> dict[str, object]:
    """Load XGBoost artifacts once and return lightweight metadata."""

    _, model_path = load_xgboost_model()
    features, feature_path = load_xgb_feature_list()
    return {
        "model": str(model_path),
        "feature_list": str(feature_path),
        "feature_count": len(features),
    }


def predict_with_xgboost(input_features: Mapping[str, Any] | pd.Series | pd.DataFrame) -> XGBoostPrediction:
    """Predict UP probability from engineered features using XGBoost.

    The model receives exactly one row ordered according to the configured
    XGBoost feature list. Missing configured required features raise a clear
    error; other missing numeric features are filled with 0.0.
    """

    model, model_path = load_xgboost_model()
    feature_list, feature_list_path = load_xgb_feature_list()
    row = _coerce_feature_row(input_features)
    _validate_required_features(row, feature_list)
    frame, filled_missing = _ordered_model_frame(row, feature_list)
    up_probability = _predict_up_probability(model, frame)
    action = action_from_probability(up_probability)
    confidence = confidence_from_probability(up_probability)
    return XGBoostPrediction(
        action=action,
        up_probability=round(up_probability, 4),
        confidence=round(confidence, 4),
        reason=reason_for_prediction(action, up_probability),
        model_path=str(model_path),
        feature_list_path=str(feature_list_path),
        feature_count=len(feature_list),
        filled_missing_features=filled_missing,
    )


@lru_cache(maxsize=1)
def load_xgboost_model() -> tuple[Any, Path]:
    """Load the primary XGBoost model artifact."""

    searched = [PRIMARY_XGB_MODEL_PATH, MODELS_ROOT_XGB_MODEL_PATH, LEGACY_XGB_MODEL_PATH]
    for path in searched:
        if not path.exists():
            continue
        try:
            model = joblib.load(path)
            if not (hasattr(model, "predict_proba") or hasattr(model, "predict")):
                raise TypeError("artifact does not expose predict_proba or predict")
            logger.info("Loaded XGBoost model from %s", path)
            return model, path
        except Exception as exc:
            raise XGBoostInferenceError(f"Failed to load XGBoost model from {path}: {exc}") from exc
    raise XGBoostInferenceError(
        "Missing XGBoost model. Expected models/xgboost/xgboost_model.pkl, "
        "models/xgboost_model.pkl, or legacy models/xgboost_classification_model.pkl."
    )


@lru_cache(maxsize=1)
def load_xgb_feature_list() -> tuple[list[str], Path]:
    """Load XGBoost feature list from configs first, then legacy models path."""

    searched = [PRIMARY_FEATURE_LIST_PATH, MODELS_ROOT_FEATURE_LIST_PATH, LEGACY_FEATURE_LIST_PATH]
    for path in searched:
        if not path.exists():
            continue
        try:
            features = json.loads(path.read_text())
            if not isinstance(features, list) or not all(isinstance(item, str) for item in features):
                raise TypeError("feature list must be a JSON list of strings")
            if not features:
                raise ValueError("feature list is empty")
            logger.info("Loaded XGBoost feature list from %s", path)
            return features, path
        except Exception as exc:
            raise XGBoostInferenceError(f"Failed to load XGBoost feature list from {path}: {exc}") from exc
    raise XGBoostInferenceError(
        "Missing XGBoost feature list. Expected configs/xgb_feature_list.json, "
        "models/xgb_feature_list.json, or fallback models/feature_list.json."
    )


def action_from_probability(up_probability: float) -> str:
    """Map UP probability to BUY/HOLD/SELL."""

    if up_probability >= 0.60:
        return "BUY"
    if up_probability <= 0.40:
        return "SELL"
    return "HOLD"


def confidence_from_probability(up_probability: float) -> float:
    """Return confidence as distance from neutral probability."""

    return abs(float(up_probability) - 0.5) * 2


def reason_for_prediction(action: str, up_probability: float) -> str:
    """Return a short human-readable reason."""

    if action == "BUY":
        return "The XGBoost model sees enough upside probability for a BUY signal."
    if action == "SELL":
        return "The XGBoost model sees enough downside risk for a SELL signal."
    return "The model sees mild or uncertain upside probability, so confidence is not strong enough for BUY or SELL."


def _coerce_feature_row(input_features: Mapping[str, Any] | pd.Series | pd.DataFrame) -> dict[str, Any]:
    if isinstance(input_features, pd.DataFrame):
        if input_features.empty:
            raise XGBoostInferenceError("Input features dataframe is empty.")
        return input_features.iloc[0].to_dict()
    if isinstance(input_features, pd.Series):
        return input_features.to_dict()
    if isinstance(input_features, Mapping):
        return dict(input_features)
    raise XGBoostInferenceError("Input features must be a dictionary, pandas Series, or single-row DataFrame.")


def _validate_required_features(row: Mapping[str, Any], feature_list: list[str]) -> None:
    config = get_backend_model_config()
    configured_required = [str(item) for item in config.get("xgb_required_features", []) if str(item) in feature_list]
    required = configured_required
    missing = [feature for feature in required if feature not in row]
    if missing:
        raise XGBoostInferenceError("Input features missing required XGBoost columns: " + ", ".join(missing))


def _ordered_model_frame(row: Mapping[str, Any], feature_list: list[str]) -> tuple[pd.DataFrame, list[str]]:
    ordered: dict[str, float] = {}
    filled_missing: list[str] = []
    for feature in feature_list:
        if feature not in row or row[feature] is None:
            ordered[feature] = 0.0
            filled_missing.append(feature)
            continue
        ordered[feature] = _numeric_value(row[feature], feature)
    return pd.DataFrame([ordered], columns=feature_list), filled_missing


def _numeric_value(value: Any, feature: str) -> float:
    try:
        parsed = float(value)
        if np.isfinite(parsed):
            return parsed
    except (TypeError, ValueError):
        pass
    logger.warning("Invalid numeric value for feature %s=%r; using 0.0", feature, value)
    return 0.0


def _predict_up_probability(model: Any, frame: pd.DataFrame) -> float:
    try:
        if hasattr(model, "predict_proba"):
            probabilities = np.asarray(model.predict_proba(frame))
            if probabilities.ndim != 2 or probabilities.shape[0] != 1:
                raise ValueError(f"unexpected predict_proba shape: {probabilities.shape}")
            classes = list(getattr(model, "classes_", []))
            positive_index = classes.index(1) if 1 in classes else probabilities.shape[1] - 1
            probability = float(probabilities[0][positive_index])
        else:
            predictions = np.asarray(model.predict(frame))
            probability = float(predictions.reshape(-1)[0])
        if not np.isfinite(probability) or probability < 0 or probability > 1:
            raise ValueError(f"invalid probability: {probability}")
        return probability
    except Exception as exc:
        raise XGBoostInferenceError(f"Invalid XGBoost model output: {exc}") from exc
