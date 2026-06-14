"""Explanation layer SHAP driver extraction.

This module explains single-row model predictions using SHAP when the XGBoost
model and SHAP dependency are available. It connects upstream model-ready
features from `FeatureEngineer` to downstream NLG generation and recommendation
API responses.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv

try:
    import shap
except ImportError:  # pragma: no cover - expected before ML dependencies arrive.
    shap = None

logger = logging.getLogger(__name__)

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODELS_DIR = PROJECT_ROOT / "models"


@dataclass(frozen=True)
class ShapDriver:
    """One model driver formatted for the API explanation contract."""

    factor: str
    effect: str
    impact: str
    shap: float
    alignment: str


@dataclass(frozen=True)
class ShapExplanation:
    """Explanation result for a single model input row."""

    drivers: list[ShapDriver]
    model_loaded: bool
    shap_available: bool
    warning: str | None = None


class ShapExplainer:
    """Explain model predictions with SHAP or a safe feature-signal fallback."""

    MODEL_FILENAMES = (
        "xgboost/xgboost_model.pkl",
        "xgboost_model.pkl",
        "xgboost_classification_model.pkl",
        "xgboost_model.joblib",
        "stock_model.pkl",
        "stock_model.joblib",
    )
    BULLISH_FEATURE_HINTS = {
        "rsi",
        "macd",
        "return",
        "volume_ratio",
        "obv",
        "ma_20_gap",
        "ma_50_gap",
        "close_position",
    }
    BEARISH_FEATURE_HINTS = {"drawdown", "volatility", "atr", "bb_width", "high_low"}
    FALLBACK_DRIVER_COLUMNS = [
        "rsi_14",
        "macd_hist",
        "return_20d",
        "return_10d",
        "volume_ratio_20",
        "volatility_20",
        "drawdown_52w",
        "atr_14",
        "ma_20_gap_pct",
        "ma_50_gap_pct",
        "bb_width",
    ]

    def __init__(self, models_dir: str | Path | None = None, model_path: str | Path | None = None) -> None:
        """Create a SHAP explainer and lazily load the XGBoost model."""

        configured_models_dir = os.getenv("MODELS_DIR")
        self.models_dir = Path(models_dir or configured_models_dir or DEFAULT_MODELS_DIR)
        self.model_path = Path(model_path) if model_path else self._find_model_path()
        self._model: Any | None = None
        self._explainer: Any | None = None
        logger.info("ShapExplainer configured with model path: %s", self.model_path)

    def explain_single(self, x_scaled: pd.DataFrame, top_n: int = 5) -> ShapExplanation:
        """Return top feature contributions for one model-ready feature row."""

        if x_scaled.empty:
            raise ValueError("x_scaled cannot be empty")
        if top_n <= 0:
            raise ValueError("top_n must be positive")

        row = x_scaled.iloc[[0]].copy()
        model = self._load_model()
        if model is None:
            warning = f"XGBoost model artifact not found at {self.models_dir}; using fallback feature drivers."
            logger.warning(warning)
            return ShapExplanation(
                drivers=self._fallback_drivers(row, top_n),
                model_loaded=False,
                shap_available=False,
                warning=warning,
            )

        xgboost_values = self._xgboost_contrib_values(model, row)
        if xgboost_values is not None:
            drivers = self._drivers_from_values(row.columns.tolist(), xgboost_values, top_n)
            logger.info("Generated %s XGBoost Tree SHAP drivers", len(drivers))
            return ShapExplanation(drivers=drivers, model_loaded=True, shap_available=True)

        if shap is None:
            warning = "SHAP package is not installed; using fallback feature drivers."
            logger.warning(warning)
            return ShapExplanation(
                drivers=self._fallback_drivers(row, top_n),
                model_loaded=True,
                shap_available=False,
                warning=warning,
            )

        try:
            explainer = self._load_explainer(model)
            shap_values = explainer.shap_values(row)
            values = self._normalize_shap_values(shap_values)
            drivers = self._drivers_from_values(row.columns.tolist(), values, top_n)
            logger.info("Generated %s SHAP drivers", len(drivers))
            return ShapExplanation(drivers=drivers, model_loaded=True, shap_available=True)
        except Exception as exc:
            warning = f"SHAP explanation failed: {exc}; using fallback feature drivers."
            logger.exception(warning)
            return ShapExplanation(
                drivers=self._fallback_drivers(row, top_n),
                model_loaded=True,
                shap_available=False,
                warning=warning,
            )

    def _find_model_path(self) -> Path:
        """Return the first available XGBoost model path or the preferred default."""

        for filename in self.MODEL_FILENAMES:
            candidate = self.models_dir / filename
            if candidate.exists():
                return candidate
        return self.models_dir / self.MODEL_FILENAMES[0]

    def _load_model(self) -> Any | None:
        """Load the trained model if present."""

        if self._model is not None:
            return self._model
        if not self.model_path.exists():
            return None
        try:
            self._model = joblib.load(self.model_path)
            logger.info("Loaded XGBoost model from %s", self.model_path)
            return self._model
        except Exception as exc:
            logger.exception("Failed to load model from %s", self.model_path)
            raise RuntimeError(f"Failed to load model from {self.model_path}: {exc}") from exc

    def _load_explainer(self, model: Any) -> Any:
        """Create and cache a SHAP TreeExplainer."""

        if self._explainer is None:
            self._explainer = shap.TreeExplainer(model)
            logger.info("Initialized SHAP TreeExplainer")
        return self._explainer

    def _xgboost_contrib_values(self, model: Any, row: pd.DataFrame) -> np.ndarray | None:
        """Use XGBoost's built-in Tree SHAP contributions when available."""

        if not hasattr(model, "get_booster"):
            return None
        try:
            import xgboost as xgb

            booster = model.get_booster()
            matrix = xgb.DMatrix(row, feature_names=row.columns.tolist())
            contributions = np.asarray(booster.predict(matrix, pred_contribs=True))
            if contributions.ndim == 3:
                contributions = contributions[:, :, -1]
            if contributions.ndim != 2 or contributions.shape[1] < 2:
                return None
            return contributions[0, :-1]
        except Exception as exc:
            logger.warning("XGBoost Tree SHAP contribution path failed: %s", exc)
            return None

    def _normalize_shap_values(self, shap_values: Any) -> np.ndarray:
        """Normalize SHAP outputs from binary or multiclass explainers."""

        if isinstance(shap_values, list):
            values = np.asarray(shap_values[-1])
        else:
            values = np.asarray(shap_values)

        if values.ndim == 3:
            values = values[:, :, -1]
        if values.ndim == 2:
            return values[0]
        if values.ndim == 1:
            return values
        raise ValueError(f"Unexpected SHAP value shape: {values.shape}")

    def _drivers_from_values(self, feature_names: list[str], values: np.ndarray, top_n: int) -> list[ShapDriver]:
        """Convert raw SHAP values into sorted API drivers."""

        ranked = sorted(zip(feature_names, values, strict=False), key=lambda item: abs(float(item[1])), reverse=True)
        drivers = [
            ShapDriver(
                factor=self._display_name(name),
                effect="bullish" if float(value) >= 0 else "bearish",
                impact=self._impact_label(float(value), values),
                shap=round(float(value), 6),
                alignment="aligned" if float(value) >= 0 else "opposing",
            )
            for name, value in ranked[:top_n]
        ]
        return drivers

    def _fallback_drivers(self, row: pd.DataFrame, top_n: int) -> list[ShapDriver]:
        """Create deterministic feature drivers before model artifacts are available."""

        values = row.iloc[0].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        candidate_columns = [column for column in self.FALLBACK_DRIVER_COLUMNS if column in values.index]
        candidate_values = values[candidate_columns] if candidate_columns else values
        ranked = candidate_values.abs().sort_values(ascending=False).head(top_n)
        drivers: list[ShapDriver] = []
        max_abs = float(ranked.max()) if len(ranked) else 0.0
        for feature_name, magnitude in ranked.items():
            raw_value = float(values[feature_name])
            pseudo_shap = 0.0 if max_abs == 0 else raw_value / max_abs
            drivers.append(
                ShapDriver(
                    factor=self._display_name(str(feature_name)),
                    effect=self._fallback_effect(str(feature_name), raw_value),
                    impact=self._fallback_impact(float(magnitude), max_abs),
                    shap=round(float(pseudo_shap), 6),
                    alignment="proxy",
                )
            )
        return drivers

    def _fallback_effect(self, feature_name: str, value: float) -> str:
        """Infer effect direction for fallback drivers using finance feature names."""

        lowered = feature_name.lower()
        if "drawdown" in lowered:
            return "bearish" if value < 0 else "bullish"
        if any(hint in lowered for hint in self.BEARISH_FEATURE_HINTS):
            return "bearish" if value > 0 else "bullish"
        if any(hint in lowered for hint in self.BULLISH_FEATURE_HINTS):
            return "bullish" if value > 0 else "bearish"
        return "bullish" if value >= 0 else "bearish"

    def _display_name(self, feature_name: str) -> str:
        """Format feature names for API explanations."""

        replacements = {
            "rsi_14": "momentum (RSI)",
            "macd": "MACD momentum",
            "atr_14": "ATR volatility",
            "drawdown_52w": "52-week drawdown",
            "volume_ratio_20": "volume strength",
            "volatility_20": "20-day volatility",
        }
        return replacements.get(feature_name, feature_name.replace("_", " "))

    def _impact_label(self, value: float, all_values: np.ndarray) -> str:
        """Label SHAP impact by relative contribution size."""

        max_abs = float(np.max(np.abs(all_values))) if len(all_values) else 0.0
        return self._fallback_impact(abs(value), max_abs)

    @staticmethod
    def _fallback_impact(value: float, max_abs: float) -> str:
        """Label fallback impact by relative magnitude."""

        if max_abs <= 0:
            return "LOW"
        ratio = value / max_abs
        if ratio >= 0.70:
            return "HIGH"
        if ratio >= 0.35:
            return "MEDIUM"
        return "LOW"
