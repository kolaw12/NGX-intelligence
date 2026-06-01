"""Runtime model and engine status endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from app.db.crud import MACRO_ASI_PATH, PRICE_DATA_PATH, TICKERS_PATH, load_prices, load_tickers
from app.services.backend_model_config import get_backend_model_config
from app.services.fundamentals_service import fundamentals_status
from app.services.news_sentiment import load_daily_sentiment_summary
from app.services.xgboost_predictor import load_xgb_feature_list, load_xgboost_model

router = APIRouter(tags=["engine"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = PROJECT_ROOT / "reports"
MODELS_DIR = PROJECT_ROOT / "models"
CONFIGS_DIR = PROJECT_ROOT / "configs"


@router.get("/model/status")
def model_status() -> dict[str, Any]:
    """Return real model artifact status; never report success by assumption."""

    config_loaded = _config_path().exists()
    config = get_backend_model_config()
    xgb_loaded = False
    xgb_model_path = None
    xgb_feature_count = 0
    xgb_feature_list_path = None
    xgb_error = None
    try:
        _, model_path = load_xgboost_model()
        features, feature_path = load_xgb_feature_list()
        xgb_loaded = True
        xgb_model_path = _relative(model_path)
        xgb_feature_list_path = _relative(feature_path)
        xgb_feature_count = len(features)
    except Exception as exc:
        xgb_error = str(exc)

    lstm_model_path = _first_existing(
        MODELS_DIR / "lstm" / "lstm_model.keras",
        MODELS_DIR / "lstm_model.keras",
        MODELS_DIR / "lstm_model.h5",
    )
    lstm_scaler_path = _first_existing(PROJECT_ROOT / "scalers" / "lstm_scaler.pkl", MODELS_DIR / "lstm_scaler.pkl")
    use_lstm = bool(config.get("use_lstm", False))
    lstm_loaded = bool(use_lstm and lstm_model_path and lstm_scaler_path)

    return {
        "xgboost_loaded": xgb_loaded,
        "xgboost_model_path": xgb_model_path,
        "xgb_feature_list_path": xgb_feature_list_path,
        "xgb_feature_count": xgb_feature_count,
        "xgb_error": xgb_error,
        "lstm_loaded": lstm_loaded,
        "lstm_model_path": _relative(lstm_model_path) if lstm_model_path else None,
        "lstm_scaler_path": _relative(lstm_scaler_path) if lstm_scaler_path else None,
        "use_lstm": use_lstm,
        "main_model": "xgboost",
        "backend_config_loaded": config_loaded,
        "backend_config_path": _relative(_config_path()) if config_loaded else None,
        "xgb_metrics": _load_json(REPORTS_DIR / "xgb_metrics.json", MODELS_DIR / "xgb_metrics.json"),
        "lstm_metrics": _load_json(REPORTS_DIR / "lstm_metrics.json", MODELS_DIR / "lstm_metrics.json"),
    }


@router.get("/engine/health")
def engine_health(deep: bool = Query(default=False)) -> dict[str, Any]:
    """Check real data/model engines and report degraded components explicitly."""

    checks: dict[str, dict[str, Any]] = {}

    try:
        if deep:
            prices = load_prices()
            checks["data_service"] = {
                "ok": not prices.empty,
                "rows": int(len(prices)),
                "tickers": int(prices["ticker"].nunique()),
                "mode": "deep",
            }
        else:
            checks["data_service"] = _file_check(PRICE_DATA_PATH, "prices")
    except Exception as exc:
        checks["data_service"] = {"ok": False, "error": str(exc)}

    try:
        if deep:
            tickers = load_tickers()
            checks["ticker_metadata"] = {"ok": not tickers.empty, "rows": int(len(tickers)), "mode": "deep"}
        else:
            checks["ticker_metadata"] = _file_check(TICKERS_PATH, "ticker_metadata")
    except Exception as exc:
        checks["ticker_metadata"] = {"ok": False, "error": str(exc)}

    checks["macro_data"] = _file_check(MACRO_ASI_PATH, "macro_asi")

    status = model_status()
    checks["xgboost_model"] = {
        "ok": bool(status["xgboost_loaded"]),
        "model_path": status["xgboost_model_path"],
        "feature_count": status["xgb_feature_count"],
        "error": status["xgb_error"],
    }
    checks["lstm_optional"] = {
        "ok": True,
        "enabled": bool(status["use_lstm"]),
        "loaded": bool(status["lstm_loaded"]),
        "note": "LSTM is optional and not required for production XGBoost inference.",
    }

    try:
        sentiment = load_daily_sentiment_summary()
        checks["sentiment_engine"] = {"ok": True, "rows": int(len(sentiment)), "source": "nlp_engine" if not sentiment.empty else "neutral_fallback"}
    except Exception as exc:
        checks["sentiment_engine"] = {"ok": False, "error": str(exc), "source": "neutral_fallback"}

    checks["feature_engine"] = {"ok": bool(status["xgboost_loaded"] and status["xgb_feature_count"])}
    checks["fundamentals_service"] = fundamentals_status()
    checks["risk_engine"] = {"ok": True}
    checks["recommendation_engine"] = {"ok": bool(status["xgboost_loaded"])}

    overall = "ok" if all(check.get("ok") for key, check in checks.items() if key != "lstm_optional") else "degraded"
    return {"status": overall, "main_model": "xgboost", "checks": checks}


def _config_path() -> Path:
    return CONFIGS_DIR / "backend_model_config.json" if (CONFIGS_DIR / "backend_model_config.json").exists() else MODELS_DIR / "backend_model_config.json"


def _load_json(*paths: Path) -> dict[str, Any]:
    for path in paths:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception as exc:
                return {"error": f"failed to read {_relative(path)}: {exc}"}
    return {}


def _first_existing(*paths: Path) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def _file_check(path: Path, name: str) -> dict[str, Any]:
    exists = path.exists() and path.stat().st_size > 0
    payload: dict[str, Any] = {"ok": exists, "name": name, "path": _relative(path), "mode": "file"}
    if exists:
        stat = path.stat()
        payload["bytes"] = stat.st_size
        payload["modifiedAt"] = stat.st_mtime
    else:
        payload["error"] = "file missing or empty"
    return payload


def _relative(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)
