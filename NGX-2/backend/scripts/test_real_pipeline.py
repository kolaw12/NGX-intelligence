"""Run a real end-to-end NGX AI pipeline smoke test.

This script does not retrain models and does not use mock data. It loads local
processed market data, builds trained-model features, runs XGBoost inference,
checks risk and sentiment engines, and prints the final recommendation payload.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.crud import get_ticker_prices, public_ticker  # noqa: E402
from app.routers.recommendations import _build_recommendation  # noqa: E402
from app.services.feature_engineer import FeatureEngineer  # noqa: E402
from app.services.news_sentiment import latest_sentiment_for_ticker  # noqa: E402
from app.services.risk_analyzer import RiskAnalyzer  # noqa: E402
from app.services.xgboost_predictor import load_xgb_feature_list, load_xgboost_model, predict_with_xgboost  # noqa: E402


def run(ticker: str = "GTCO") -> dict[str, object]:
    model, model_path = load_xgboost_model()
    features, feature_path = load_xgb_feature_list()
    prices = get_ticker_prices(ticker)
    engineered = FeatureEngineer().engineer(prices, scale=False)
    latest_model_features = engineered.model_features.tail(1)
    xgb = predict_with_xgboost(latest_model_features)
    risk = RiskAnalyzer().analyze(engineered.features, str(engineered.features.iloc[-1]["ticker"]))
    sentiment = latest_sentiment_for_ticker(str(engineered.features.iloc[-1]["ticker"]))
    recommendation, _ = _build_recommendation(ticker)
    return {
        "ticker": public_ticker(str(engineered.features.iloc[-1]["ticker"])),
        "model_loaded": model is not None,
        "model_path": str(model_path.relative_to(PROJECT_ROOT)),
        "feature_list_path": str(feature_path.relative_to(PROJECT_ROOT)),
        "feature_count": len(features),
        "latest_feature_columns": len(latest_model_features.columns),
        "xgboost": {
            "up_probability": xgb.up_probability,
            "action": xgb.action,
            "confidence": xgb.confidence,
            "filled_missing_features": xgb.filled_missing_features,
        },
        "risk": {
            "risk_score": risk.risk_score,
            "risk_level": risk.risk_level.value,
            "risk_reasons": [flag.description for flag in risk.flags],
        },
        "sentiment": {
            "sentiment_score": sentiment.score,
            "sentiment_label": sentiment.label,
            "source": "nlp_engine" if sentiment.total_articles else "neutral_fallback",
            "total_articles": sentiment.total_articles,
            "as_of_date": sentiment.as_of_date,
        },
        "recommendation": recommendation,
    }


if __name__ == "__main__":
    requested_ticker = sys.argv[1] if len(sys.argv) > 1 else "GTCO"
    print(json.dumps(run(requested_ticker), indent=2, default=str))
