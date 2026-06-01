"""Direct model prediction API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.cache import ttl_cache
from app.services.xgboost_predictor import XGBoostInferenceError, predict_with_xgboost

router = APIRouter(tags=["prediction"])


class PredictRequest(BaseModel):
    ticker: str = Field(min_length=1)
    features: dict[str, Any] = Field(default_factory=dict)
    risk_score: float | None = None
    sentiment_score: float | None = None
    sector_signal: float | None = None
    news_signal: float | None = None


@router.post("/predict")
def predict(input: PredictRequest) -> dict[str, object]:
    """Return a clean XGBoost-first BUY/HOLD/SELL prediction."""

    try:
        prediction = _cached_prediction(input.ticker.upper().strip(), input.features)
    except XGBoostInferenceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return {
        "ticker": input.ticker.upper().strip(),
        "action": prediction.action,
        "up_probability": prediction.up_probability,
        "confidence": prediction.confidence,
        "main_model": prediction.main_model,
        "model": prediction.main_model,
        "model_source": prediction.model_source,
        "feature_count": prediction.feature_count,
        "filled_missing_features": prediction.filled_missing_features,
        "reason": prediction.reason,
    }


@ttl_cache(ttl_seconds=60, name="direct_prediction")
def _cached_prediction(ticker: str, features: dict[str, Any]):
    """Short-cache direct predictions for repeated refreshes."""

    return predict_with_xgboost(features)
