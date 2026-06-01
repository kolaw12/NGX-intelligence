"""Backend model-serving configuration.

The backend defaults to XGBoost-only inference. Optional model signals, such as
LSTM, must be enabled explicitly by configs/backend_model_config.json.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "configs" / "backend_model_config.json"
LEGACY_MODELS_CONFIG_PATH = PROJECT_ROOT / "models" / "backend_model_config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "use_lstm": False,
    "xgb_weight": 0.80,
    "lstm_weight": 0.20,
    "xgb_required_features": [],
}


@lru_cache(maxsize=1)
def get_backend_model_config() -> dict[str, Any]:
    """Return backend model config, defaulting to XGBoost-only."""

    config_path = CONFIG_PATH if CONFIG_PATH.exists() else LEGACY_MODELS_CONFIG_PATH
    if not config_path.exists():
        return dict(DEFAULT_CONFIG)

    try:
        loaded = json.loads(config_path.read_text())
        if not isinstance(loaded, dict):
            raise TypeError("backend_model_config.json must contain an object")
        config = {**DEFAULT_CONFIG, **loaded}
        config["use_lstm"] = bool(config.get("use_lstm", False))
        config["xgb_weight"] = _safe_weight(config.get("xgb_weight"), DEFAULT_CONFIG["xgb_weight"])
        config["lstm_weight"] = _safe_weight(config.get("lstm_weight"), DEFAULT_CONFIG["lstm_weight"])
        if not isinstance(config.get("xgb_required_features"), list):
            config["xgb_required_features"] = []
        return config
    except Exception as exc:
        logger.warning("Failed to read %s; using XGBoost-only defaults: %s", config_path, exc)
        return dict(DEFAULT_CONFIG)


def _safe_weight(value: Any, default: float) -> float:
    try:
        parsed = float(value)
        return max(0.0, parsed)
    except (TypeError, ValueError):
        return float(default)
