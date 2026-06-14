"""LSTM model serving for short-horizon ticker probability.

The checked-in LSTM artifact expects a 10-step sequence with three scaled
features in this order: high, low, close.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "lstm_model.keras"
DEFAULT_SCALER_PATH = PROJECT_ROOT / "scalers" / "lstm_scaler.pkl"
LSTM_FEATURES = ["high", "low", "close"]
SEQUENCE_LENGTH = 10


class LSTMPredictor:
    """Load the trained LSTM and return a bounded probability for one ticker."""

    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        scaler_path: str | Path = DEFAULT_SCALER_PATH,
    ) -> None:
        self.model_candidates = [
            Path(model_path),
            PROJECT_ROOT / "models" / "lstm_model.keras",
            PROJECT_ROOT / "models" / "lstm_model.h5",
        ]
        self.scaler_candidates = [
            Path(scaler_path),
            PROJECT_ROOT / "scalers" / "lstm_scaler.pkl",
            PROJECT_ROOT / "models" / "lstm_scaler.pkl",
        ]
        self.model_path = self._first_existing(self.model_candidates) or Path(model_path)
        self.scaler_path = self._find_compatible_scaler() or Path(scaler_path)

    def predict_probability(self, prices: pd.DataFrame) -> tuple[float | None, str]:
        """Return the LSTM probability and model version label.

        A ``None`` probability is intentional when artifacts/history are missing;
        the rule engine will then blend the remaining available models.
        """

        if not self.model_path.exists():
            logger.warning("LSTM model not found: %s", self.model_path)
            return None, "missing-lstm-model"
        if not self.scaler_path.exists():
            logger.warning("LSTM scaler not found: %s", self.scaler_path)
            return None, "missing-lstm-scaler"

        sequence = self._build_sequence(prices)
        if sequence is None:
            return None, "insufficient-history"

        try:
            model = _load_lstm_model(str(self.model_path))
            probability = float(model.predict(sequence, verbose=0)[0][0])
            if not np.isfinite(probability):
                raise ValueError(f"non-finite LSTM probability: {probability}")
            return max(0.05, min(0.95, probability)), self.model_path.name
        except Exception as exc:
            logger.warning("LSTM prediction failed; skipping LSTM probability: %s", exc)
            return None, "lstm-error"

    def _build_sequence(self, prices: pd.DataFrame) -> np.ndarray | None:
        """Prepare a scaled ``(1, 10, 3)`` tensor from latest OHLC rows."""

        missing = [column for column in LSTM_FEATURES if column not in prices.columns]
        if missing:
            logger.warning("LSTM input is missing columns: %s", ", ".join(missing))
            return None

        frame = prices.copy()
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.sort_values("date")
        values = frame[LSTM_FEATURES].apply(pd.to_numeric, errors="coerce")
        values = values.ffill().bfill().dropna()
        if len(values) < SEQUENCE_LENGTH:
            logger.info("Not enough rows for LSTM sequence: %s < %s", len(values), SEQUENCE_LENGTH)
            return None

        latest_window = values.tail(SEQUENCE_LENGTH)
        scaler = _load_lstm_scaler(str(self.scaler_path))
        scaled = scaler.transform(latest_window)
        return np.asarray(scaled, dtype=np.float32).reshape(1, SEQUENCE_LENGTH, len(LSTM_FEATURES))

    @staticmethod
    def _first_existing(paths: list[Path]) -> Path | None:
        """Return the first existing artifact path."""

        return next((path for path in paths if path.exists()), None)

    def _find_compatible_scaler(self) -> Path | None:
        """Find an LSTM scaler trained for the three sequence features."""

        for path in self.scaler_candidates:
            if not path.exists():
                continue
            try:
                scaler = _load_lstm_scaler(str(path))
                expected_features = getattr(scaler, "n_features_in_", None)
                if expected_features is None or int(expected_features) == len(LSTM_FEATURES):
                    return path
                logger.info(
                    "Skipping LSTM scaler at %s: expects %s features, LSTM uses %s.",
                    path,
                    expected_features,
                    len(LSTM_FEATURES),
                )
            except Exception as exc:
                logger.warning("Skipping unreadable LSTM scaler at %s: %s", path, exc)
        return None


@lru_cache(maxsize=1)
def _load_lstm_model(model_path: str):
    """Lazy-load Keras so regular API startup stays lightweight."""

    import keras

    return keras.models.load_model(model_path, compile=False)


@lru_cache(maxsize=1)
def _load_lstm_scaler(scaler_path: str):
    """Load the scaler trained with the LSTM model."""

    return joblib.load(scaler_path)
