"""Processing layer feature engineering for model inference.

This module transforms cleaned NGX OHLCV data into technical-analysis features
for the AI/ML layer. It connects `DataProcessor` outputs to downstream model
serving, risk analysis, SHAP explanation, and recommendation APIs.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCALERS_DIR = PROJECT_ROOT / "scalers"
DEFAULT_MODELS_DIR = PROJECT_ROOT / "models"


@dataclass(frozen=True)
class FeatureEngineeringResult:
    """Container returned after feature engineering and optional scaling."""

    features: pd.DataFrame
    model_features: pd.DataFrame
    feature_columns: list[str]
    missing_feature_columns: list[str]
    scaler_loaded: bool
    feature_columns_loaded: bool
    warnings: list[str]


class FeatureEngineer:
    """Create training-compatible inference features from cleaned OHLCV data."""

    FALLBACK_FEATURE_COLUMNS = [
        "daily_return",
        "log_return",
        "return_3d",
        "return_5d",
        "return_10d",
        "return_20d",
        "volatility_20",
        "ma_5",
        "ma_10",
        "ma_20",
        "ma_50",
        "ma_20_gap_pct",
        "ma_50_gap_pct",
        "rsi_14",
        "macd",
        "macd_signal",
        "macd_hist",
        "bb_mid",
        "bb_upper",
        "bb_lower",
        "bb_width",
        "atr_14",
        "obv",
        "volume_ratio_20",
        "volume_change",
        "drawdown_52w",
        "high_low_pct",
        "close_position",
        "lag_close_1",
        "lag_close_2",
        "lag_return_1",
        "lag_return_2",
        "lag_volume_1",
    ]

    REQUIRED_INPUT_COLUMNS = ("date", "ticker", "pclose", "high", "low", "close", "volume", "change")

    def __init__(self, scalers_dir: str | Path | None = None) -> None:
        """Create a feature engineer and locate training artifacts.

        Args:
            scalers_dir: Optional path containing `feature_cols.pkl` and
                `standard_scaler.pkl`. Defaults to `SCALERS_DIR` or `app/scalers`.
        """

        configured_dir = os.getenv("SCALERS_DIR")
        configured_models_dir = os.getenv("MODELS_DIR")
        configured_configs_dir = os.getenv("CONFIGS_DIR")
        self.scalers_dir = Path(scalers_dir or configured_dir or DEFAULT_SCALERS_DIR)
        self.models_dir = Path(configured_models_dir or DEFAULT_MODELS_DIR)
        self.configs_dir = Path(configured_configs_dir or PROJECT_ROOT / "configs")
        standard_scaler_path = self.scalers_dir / "standard_scaler.pkl"
        models_standard_scaler_path = self.models_dir / "standard_scaler.pkl"
        feature_columns_path = self.scalers_dir / "feature_cols.pkl"
        xgb_feature_columns_path = self.configs_dir / "xgb_feature_list.json"
        models_xgb_feature_columns_path = self.models_dir / "xgb_feature_list.json"
        self.ticker_encoder_path = self.models_dir / "ticker_encoder.pkl"
        self._ticker_encoder = None
        self.scaler_candidates = [
            standard_scaler_path,
            models_standard_scaler_path,
            self.scalers_dir / "lstm_scaler.pkl",
            self.models_dir / "lstm_scaler.pkl",
        ]
        self.scaler_path = next((path for path in self.scaler_candidates if path.exists()), standard_scaler_path)
        self.feature_columns_path = (
            xgb_feature_columns_path
            if xgb_feature_columns_path.exists()
            else models_xgb_feature_columns_path
            if models_xgb_feature_columns_path.exists()
            else feature_columns_path
            if feature_columns_path.exists()
            else self.models_dir / "feature_list.json"
        )
        logger.info(
            "FeatureEngineer configured with feature columns %s and scaler %s",
            self.feature_columns_path,
            self.scaler_path,
        )

    def engineer(self, df: pd.DataFrame, scale: bool = True) -> FeatureEngineeringResult:
        """Compute indicators and return model-ready features.

        Args:
            df: Clean OHLCV data from `DataProcessor`.
            scale: Whether to apply the saved StandardScaler when available.
        """

        self._validate_input(df)
        logger.info("Engineering features for %s rows across %s tickers", len(df), df["ticker"].nunique())

        features = df.copy()
        features["date"] = pd.to_datetime(features["date"], errors="coerce")
        features = features.sort_values(["ticker", "date"]).reset_index(drop=True)

        engineered = pd.concat(
            [self._engineer_single_ticker(group) for _, group in features.groupby("ticker", sort=False)],
            ignore_index=True,
        )
        engineered = engineered.replace([np.inf, -np.inf], np.nan)
        engineered = self._fill_feature_gaps(engineered)

        feature_columns, feature_columns_loaded, feature_column_warning = self._load_feature_columns()
        model_frame, missing_feature_columns = self._build_model_frame(engineered, feature_columns)
        model_features, scaler_loaded, scaler_warning = self._scale_model_frame(model_frame, scale)

        warnings = [warning for warning in [feature_column_warning, scaler_warning] if warning]
        if missing_feature_columns:
            warning = "Missing engineered columns filled with 0.0: " + ", ".join(missing_feature_columns)
            logger.warning(warning)
            warnings.append(warning)

        logger.info(
            "Feature engineering complete: %s feature columns, scaler_loaded=%s",
            len(feature_columns),
            scaler_loaded,
        )
        return FeatureEngineeringResult(
            features=engineered,
            model_features=model_features,
            feature_columns=feature_columns,
            missing_feature_columns=missing_feature_columns,
            scaler_loaded=scaler_loaded,
            feature_columns_loaded=feature_columns_loaded,
            warnings=warnings,
        )

    def engineer_latest(self, df: pd.DataFrame, scale: bool = True) -> FeatureEngineeringResult:
        """Engineer features and return only the latest row per ticker."""

        result = self.engineer(df, scale=scale)
        latest_index = result.features.sort_values(["ticker", "date"]).groupby("ticker").tail(1).index
        return FeatureEngineeringResult(
            features=result.features.loc[latest_index].reset_index(drop=True),
            model_features=result.model_features.loc[latest_index].reset_index(drop=True),
            feature_columns=result.feature_columns,
            missing_feature_columns=result.missing_feature_columns,
            scaler_loaded=result.scaler_loaded,
            feature_columns_loaded=result.feature_columns_loaded,
            warnings=result.warnings,
        )

    def _validate_input(self, df: pd.DataFrame) -> None:
        """Validate that cleaned OHLCV columns are available."""

        missing = [column for column in self.REQUIRED_INPUT_COLUMNS if column not in df.columns]
        if missing:
            raise ValueError("FeatureEngineer requires cleaned OHLCV columns: " + ", ".join(missing))
        if df.empty:
            raise ValueError("FeatureEngineer received an empty DataFrame")

    def _engineer_single_ticker(self, group: pd.DataFrame) -> pd.DataFrame:
        """Compute all rolling and technical indicators for one ticker."""

        data = group.copy().sort_values("date")
        close = data["close"].astype(float)
        high = data["high"].astype(float)
        low = data["low"].astype(float)
        volume = data["volume"].astype(float)
        pclose = data["pclose"].astype(float)

        data["daily_return"] = close.pct_change()
        data["log_return"] = np.log(close.replace(0, np.nan) / close.shift(1).replace(0, np.nan))
        data["change_abs"] = close - pclose
        data["change_pct"] = data["change_abs"] / pclose.replace(0, np.nan)
        data["price_range"] = high - low
        data["gap_from_pclose"] = close - pclose
        data["daily_ret"] = data["daily_return"]
        data["log_ret"] = data["log_return"]
        for window in (3, 5, 10, 20):
            data[f"return_{window}d"] = close.pct_change(window)

        for window in (5, 10):
            data[f"volatility_{window}"] = data["daily_return"].rolling(window, min_periods=max(2, window // 2)).std() * np.sqrt(252)
        data["volatility_20"] = data["daily_return"].rolling(20, min_periods=5).std() * np.sqrt(252)
        for window in (5, 10, 20, 50):
            data[f"ma_{window}"] = close.rolling(window, min_periods=max(2, window // 4)).mean()
            data[f"MA_{window}"] = data[f"ma_{window}"]
            data[f"SMA_{window}"] = data[f"ma_{window}"]
        data["EMA_12"] = close.ewm(span=12, adjust=False, min_periods=6).mean()
        data["EMA_26"] = close.ewm(span=26, adjust=False, min_periods=13).mean()
        data["EMA_9"] = close.ewm(span=9, adjust=False, min_periods=4).mean()
        data["price_above_MA_20"] = (close > data["MA_20"]).astype(float)
        data["price_above_MA_50"] = (close > data["MA_50"]).astype(float)
        data["MA_20_above_MA_50"] = (data["MA_20"] > data["MA_50"]).astype(float)
        data["MA_20_slope"] = data["MA_20"].diff()
        data["MA_50_slope"] = data["MA_50"].diff()
        data["ma_20_gap_pct"] = ((close - data["ma_20"]) / data["ma_20"].replace(0, np.nan)) * 100
        data["ma_50_gap_pct"] = ((close - data["ma_50"]) / data["ma_50"].replace(0, np.nan)) * 100
        data["above_SMA20"] = data["price_above_MA_20"]
        data["above_SMA50"] = data["price_above_MA_50"]
        data["SMA20_vs_SMA50"] = data["MA_20_above_MA_50"]
        data["SMA20_slope"] = data["MA_20_slope"]
        data["SMA50_slope"] = data["MA_50_slope"]
        data["price_vs_SMA20"] = data["ma_20_gap_pct"]
        data["price_vs_SMA50"] = data["ma_50_gap_pct"]

        data["rsi_14"] = self._rsi(close, window=14)
        data["RSI_14"] = data["rsi_14"]
        data["RSI_7"] = self._rsi(close, window=7)
        data["macd"], data["macd_signal"], data["macd_hist"] = self._macd(close)
        data["bb_mid"], data["bb_upper"], data["bb_lower"], data["bb_width"] = self._bollinger(close)
        data["atr_14"] = self._atr(high, low, close, window=14)
        data["obv"] = self._obv(close, volume)
        data["RSI"] = data["rsi_14"]
        data["MACD"] = data["macd"]
        data["MACD_SIGNAL"] = data["macd_signal"]
        data["MACD_HISTOGRAM"] = data["macd_hist"]
        data["MACD_HIST"] = data["macd_hist"]
        data["MACD_cross"] = (data["macd"] > data["macd_signal"]).astype(float)
        data["ROC_5"] = close.pct_change(5)
        data["ROC"] = close.pct_change(10)
        data["ROC_10"] = data["ROC"]
        data["ROC_20"] = close.pct_change(20)
        data["momentum_5"] = close - close.shift(5)
        data["momentum_10"] = close - close.shift(10)
        data["momentum_accel"] = data["momentum_5"] - data["momentum_10"]
        data["BB_UPPER"] = data["bb_upper"]
        data["BB_LOWER"] = data["bb_lower"]
        data["BB_WIDTH"] = data["bb_width"]
        data["BB_PCT"] = (close - data["bb_lower"]) / (data["bb_upper"] - data["bb_lower"]).replace(0, np.nan)
        data["BB_squeeze"] = data["bb_width"].rolling(20, min_periods=5).rank(pct=True)
        data["ATR"] = data["atr_14"]
        data["ATR_14"] = data["atr_14"]
        data["ATR_pct"] = data["atr_14"] / close.replace(0, np.nan)
        data["OBV"] = data["obv"]
        data["OBV_MA20"] = data["OBV"].rolling(20, min_periods=5).mean()

        for window in (5, 20):
            data[f"volume_MA_{window}"] = volume.rolling(window, min_periods=max(2, window // 4)).mean()
        data["vol_MA5"] = data["volume_MA_5"]
        data["vol_MA20"] = data["volume_MA_20"]
        avg_volume_20 = volume.rolling(20, min_periods=5).mean()
        data["volume_ratio_20"] = volume / avg_volume_20.replace(0, np.nan)
        data["relative_volume"] = data["volume_ratio_20"]
        data["volume_change"] = volume.pct_change(fill_method=None)
        data["volume_log"] = np.log1p(volume.clip(lower=0))
        data["vol_5"] = data["daily_return"].rolling(5, min_periods=2).std() * np.sqrt(252)
        data["vol_10"] = data["daily_return"].rolling(10, min_periods=3).std() * np.sqrt(252)
        data["vol_20"] = data["volatility_20"]
        data["vol_ratio"] = data["volume_ratio_20"]
        data["rel_vol"] = data["relative_volume"]
        data["vol_surge"] = (data["volume_ratio_20"] >= 1.5).astype(float)
        typical_price = (high + low + close) / 3
        data["VWAP"] = (typical_price * volume).cumsum() / volume.replace(0, np.nan).cumsum()
        data["price_vs_VWAP"] = ((close - data["VWAP"]) / data["VWAP"].replace(0, np.nan)) * 100
        data = data.copy()

        rolling_52w_high = close.rolling(252, min_periods=20).max()
        data["rolling_max_close"] = close.cummax()
        data["drawdown_52w"] = ((close / rolling_52w_high.replace(0, np.nan)) - 1.0) * 100
        data["drawdown"] = (close / data["rolling_max_close"].replace(0, np.nan)) - 1.0
        data["max_drawdown_20"] = data["drawdown"].rolling(20, min_periods=5).min()
        data["max_dd_20"] = data["max_drawdown_20"]
        data["volatility_risk_score"] = data["volatility_20"].rank(pct=True)
        data["liquidity_risk_score"] = (-volume.replace(0, np.nan)).rank(pct=True)
        data["high_low_pct"] = ((high - low) / close.replace(0, np.nan)) * 100
        data["close_position"] = (close - low) / (high - low).replace(0, np.nan)
        data["close_pos"] = data["close_position"]
        dates = pd.to_datetime(data["date"], errors="coerce")
        data["day_of_week"] = dates.dt.dayofweek
        data["dow"] = data["day_of_week"]
        data["month"] = dates.dt.month
        data["quarter"] = dates.dt.quarter
        data["is_month_end"] = dates.dt.is_month_end.astype(float)
        data["ticker_encoded"] = self._encode_ticker(str(data["ticker"].iloc[-1]))
        data["ticker_enc"] = data["ticker_encoded"]
        data = data.copy()

        for lag in (1, 2, 3, 5):
            data[f"lag_close_{lag}"] = close.shift(lag)
            data[f"lag_return_{lag}"] = data["daily_return"].shift(lag)
            data[f"lag_volume_{lag}"] = volume.shift(lag)
            data[f"close_lag{lag}"] = data[f"lag_close_{lag}"]
            data[f"return_lag{lag}"] = data[f"lag_return_{lag}"]
        data["roll_mean_5"] = close.rolling(5, min_periods=2).mean()
        data["roll_std_5"] = close.rolling(5, min_periods=2).std()
        data["roll_skew_10"] = close.rolling(10, min_periods=3).skew()
        data["roll_max_5"] = close.rolling(5, min_periods=2).max()
        data["roll_min_5"] = close.rolling(5, min_periods=2).min()

        return data.copy()

    def _fill_feature_gaps(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fill warm-up NaNs conservatively after rolling indicators are computed."""

        features = df.copy()
        numeric_columns = features.select_dtypes(include=[np.number]).columns
        features[numeric_columns] = features.groupby("ticker", group_keys=False)[numeric_columns].ffill()
        neutral_defaults = {
            "daily_return": 0.0,
            "log_return": 0.0,
            "rsi_14": 50.0,
            "macd": 0.0,
            "macd_signal": 0.0,
            "macd_hist": 0.0,
            "bb_width": 0.0,
            "atr_14": 0.0,
            "volume_ratio_20": 1.0,
            "volume_change": 0.0,
            "drawdown_52w": 0.0,
            "high_low_pct": 0.0,
            "close_position": 0.5,
            "ticker_encoded": -1.0,
        }
        for column, value in neutral_defaults.items():
            if column in features.columns:
                features[column] = features[column].fillna(value)
        features[numeric_columns] = features[numeric_columns].fillna(0.0)
        return features

    def _load_feature_columns(self) -> tuple[list[str], bool, str | None]:
        """Load training feature columns, falling back when the artifact is absent."""

        if not self.feature_columns_path.exists():
            warning = (
                f"Training feature column artifact not found at {self.feature_columns_path}; "
                "using fallback feature order until scalers/feature_cols.pkl is provided."
            )
            logger.warning(warning)
            return list(self.FALLBACK_FEATURE_COLUMNS), False, warning

        try:
            if self.feature_columns_path.suffix.lower() == ".json":
                feature_columns = json.loads(self.feature_columns_path.read_text())
            else:
                feature_columns = joblib.load(self.feature_columns_path)
            if not isinstance(feature_columns, list) or not all(isinstance(col, str) for col in feature_columns):
                raise TypeError("feature_cols.pkl must contain a list[str]")
            logger.info("Loaded %s training feature columns", len(feature_columns))
            return feature_columns, True, None
        except Exception as exc:
            raise RuntimeError(f"Failed to load feature columns from {self.feature_columns_path}: {exc}") from exc

    def _encode_ticker(self, ticker: str) -> float:
        """Return the training LabelEncoder code for a ticker, or -1 for unknowns."""

        if not self.ticker_encoder_path.exists():
            return -1.0
        try:
            if self._ticker_encoder is None:
                self._ticker_encoder = joblib.load(self.ticker_encoder_path)
            encoder = self._ticker_encoder
            classes = list(getattr(encoder, "classes_", []))
            if ticker not in classes:
                return -1.0
            return float(encoder.transform([ticker])[0])
        except Exception as exc:
            logger.warning("Failed to encode ticker %s with %s: %s", ticker, self.ticker_encoder_path, exc)
            return -1.0

    def _build_model_frame(self, features: pd.DataFrame, feature_columns: list[str]) -> tuple[pd.DataFrame, list[str]]:
        """Align engineered features to the exact model feature column order."""

        missing_columns = [column for column in feature_columns if column not in features.columns]
        model_frame = pd.DataFrame(index=features.index)
        for column in feature_columns:
            model_frame[column] = features[column] if column in features.columns else 0.0
        model_frame = model_frame.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        return model_frame.astype(float), missing_columns

    def _scale_model_frame(self, model_frame: pd.DataFrame, scale: bool) -> tuple[pd.DataFrame, bool, str | None]:
        """Apply the saved StandardScaler without ever refitting at inference time."""

        if not scale:
            logger.info("Feature scaling disabled by caller")
            return model_frame, False, None

        scaler_path = self._find_compatible_scaler(len(model_frame.columns))
        if scaler_path is None:
            warning = (
                "Compatible StandardScaler artifact not found; returning unscaled model features until "
                "scalers/standard_scaler.pkl or models/standard_scaler.pkl is provided."
            )
            logger.warning(warning)
            return model_frame, False, warning

        try:
            scaler = joblib.load(scaler_path)
            scaled_values = scaler.transform(model_frame)
            scaled = pd.DataFrame(scaled_values, columns=model_frame.columns, index=model_frame.index)
            logger.info("Applied saved StandardScaler to model features from %s", scaler_path)
            return scaled, True, None
        except Exception as exc:
            raise RuntimeError(f"Failed to scale features with {scaler_path}: {exc}") from exc

    def _find_compatible_scaler(self, feature_count: int) -> Path | None:
        """Return the first scaler artifact whose feature count matches the model frame."""

        for path in self.scaler_candidates:
            if not path.exists():
                continue
            try:
                scaler = joblib.load(path)
                expected_features = getattr(scaler, "n_features_in_", None)
                if expected_features is None or int(expected_features) == feature_count:
                    self.scaler_path = path
                    return path
                logger.info(
                    "Skipping scaler artifact at %s: expects %s features, model frame has %s.",
                    path,
                    expected_features,
                    feature_count,
                )
            except Exception as exc:
                logger.warning("Skipping unreadable scaler artifact at %s: %s", path, exc)
        return None

    @staticmethod
    def _rsi(close: pd.Series, window: int) -> pd.Series:
        """Compute Relative Strength Index."""

        delta = close.diff()
        gain = delta.clip(lower=0).rolling(window, min_periods=max(2, window // 2)).mean()
        loss = (-delta.clip(upper=0)).rolling(window, min_periods=max(2, window // 2)).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Compute MACD, signal line, and histogram."""

        ema_12 = close.ewm(span=12, adjust=False, min_periods=6).mean()
        ema_26 = close.ewm(span=26, adjust=False, min_periods=13).mean()
        macd = ema_12 - ema_26
        signal = macd.ewm(span=9, adjust=False, min_periods=4).mean()
        hist = macd - signal
        return macd, signal, hist

    @staticmethod
    def _bollinger(close: pd.Series, window: int = 20) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
        """Compute Bollinger Band midpoint, upper band, lower band, and width."""

        mid = close.rolling(window, min_periods=5).mean()
        std = close.rolling(window, min_periods=5).std()
        upper = mid + (2 * std)
        lower = mid - (2 * std)
        width = (upper - lower) / mid.replace(0, np.nan)
        return mid, upper, lower, width

    @staticmethod
    def _atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int) -> pd.Series:
        """Compute Average True Range."""

        previous_close = close.shift(1)
        true_range = pd.concat(
            [
                high - low,
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return true_range.rolling(window, min_periods=max(2, window // 2)).mean()

    @staticmethod
    def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """Compute On-Balance Volume."""

        direction = np.sign(close.diff()).fillna(0)
        return (direction * volume.fillna(0)).cumsum()
