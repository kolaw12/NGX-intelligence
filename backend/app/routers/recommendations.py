"""API bridge layer recommendation endpoints.

This router assembles processing, feature engineering, risk analysis, sector
context, SHAP drivers, and NLG into the recommendation JSON contract consumed by
the React frontend.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.db.crud import get_latest_by_ticker, get_ticker_prices, load_macro_asi, public_ticker, save_recommendation_signal
from app.db.database import SessionLocal
from app.explain.nlg_generator import NLGGenerator
from app.explain.shap_explainer import ShapExplainer
from app.services.cache import ttl_cache
from app.services.rule_engine import SignalOutput
from app.utils.enums import RecommendationAction, SignalStrength
from app.services.backend_model_config import get_backend_model_config
from app.services.feature_engineer import FeatureEngineer
from app.services.lstm_predictor import DEFAULT_MODEL_PATH as LSTM_MODEL_PATH
from app.services.lstm_predictor import DEFAULT_SCALER_PATH as LSTM_SCALER_PATH
from app.services.lstm_predictor import LSTMPredictor
from app.services.news_sentiment import (
    SENTIMENT_SUMMARY_PATH,
    detect_high_severity_events_for_ticker,
    latest_market_package_sentiment,
    latest_package_breakdown_for_ticker,
    latest_package_momentum_for_ticker,
    latest_sentiment_for_ticker,
    load_daily_sentiment_summary,
    load_sentiment_history_for_ticker,
)
from app.services.risk_analyzer import RiskAnalyzer
from app.services.xgboost_predictor import (
    PRIMARY_XGB_MODEL_PATH,
    XGBoostInferenceError,
    action_from_probability,
    confidence_from_probability,
    predict_with_xgboost,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["recommendations"])
PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_INSIGHTS_SNAPSHOT_PATH = PROJECT_ROOT / "models" / "ai_insights_snapshot.json"
MODEL_PATH = PRIMARY_XGB_MODEL_PATH if PRIMARY_XGB_MODEL_PATH.exists() else PROJECT_ROOT / "models" / "xgboost_classification_model.pkl"
PRICE_DATA_PATH = PROJECT_ROOT / "data" / "output" / "processed" / "prices" / "historical_consolidated.parquet"


@router.get("/recommendations/{ticker}")
def get_recommendation(ticker: str, background_tasks: BackgroundTasks) -> dict[str, object]:
    """Return the exact recommendation response contract for one ticker."""

    try:
        recommendation, debug_payload = _cached_build_recommendation(ticker.upper().strip())
        background_tasks.add_task(
            _persist_recommendation_signal,
            recommendation,
            debug_payload["feature_snapshot"],
            debug_payload["model_versions"],
        )
        return recommendation
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/ai/insights/{ticker}")
@ttl_cache(ttl_seconds=600, name="ai_insight")
def get_ai_insight(ticker: str) -> dict[str, object]:
    """Return frontend-compatible AIInsight for one ticker."""

    try:
        recommendation, _ = _cached_build_recommendation(ticker.upper().strip())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _recommendation_to_ai_insight(recommendation)


@router.get("/ai/insights")
def list_ai_insights(limit: int = Query(default=8, ge=1, le=50)) -> list[dict[str, object]]:
    """Return ranked full model-backed AI insights for active tickers."""

    return _cached_ai_insights(limit)


@lru_cache(maxsize=8)
def _cached_ai_insights(limit: int) -> list[dict[str, object]]:
    """Build and cache full model-backed AI insight cards."""

    stored = _load_ai_insights_snapshot(limit)
    if stored:
        return stored

    latest = get_latest_by_ticker().copy()
    latest["close"] = latest["close"].astype(float)
    latest["pclose"] = latest["pclose"].astype(float)
    latest.loc[latest["pclose"] == 0, "pclose"] = latest.loc[latest["pclose"] == 0, "close"]
    latest["volume"] = latest["volume"].fillna(0).astype(float)
    latest["move_pct"] = ((latest["close"] - latest["pclose"]) / latest["pclose"]).fillna(0.0)
    latest["volume_rank"] = latest["volume"].rank(pct=True).fillna(0.0)
    active = latest[(latest["volume"] > 0) & (latest["move_pct"].abs() >= 0.002)].copy()
    if len(active) < limit:
        active = latest[latest["volume"] > 0].copy()
    ranked = active.assign(conviction=active["move_pct"].abs() + active["volume_rank"] * 0.15)
    insights: list[dict[str, object]] = []
    for ticker in ranked.sort_values("conviction", ascending=False)["ticker"].astype(str).head(limit * 2):
        try:
            recommendation, _ = _cached_build_recommendation(str(ticker).upper().strip())
            insights.append(_recommendation_to_ai_insight(recommendation))
        except Exception as exc:
            logger.warning("Skipping insight for %s: %s", ticker, exc)
        if len(insights) >= limit:
            break
    sorted_insights = sorted(insights, key=lambda row: row["confidence"], reverse=True)
    _save_ai_insights_snapshot(sorted_insights)
    return sorted_insights


def _load_ai_insights_snapshot(limit: int) -> list[dict[str, object]]:
    """Load persisted full AI insights when current for model/data artifacts."""

    if not AI_INSIGHTS_SNAPSHOT_PATH.exists() or _ai_insights_snapshot_is_stale():
        return []
    try:
        payload = json.loads(AI_INSIGHTS_SNAPSHOT_PATH.read_text())
        if payload.get("schema") != 2:
            return []
        insights = payload.get("insights", [])
        if isinstance(insights, list) and len(insights) >= limit:
            return insights[:limit]
    except Exception as exc:
        logger.warning("Failed to load AI insights snapshot: %s", exc)
    return []


def _save_ai_insights_snapshot(insights: list[dict[str, object]]) -> None:
    """Persist full AI insight cards for fast page loads."""

    try:
        AI_INSIGHTS_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        AI_INSIGHTS_SNAPSHOT_PATH.write_text(json.dumps({"schema": 2, "insights": insights}, indent=2))
    except Exception as exc:
        logger.warning("Failed to save AI insights snapshot: %s", exc)


def _ai_insights_snapshot_is_stale() -> bool:
    """Return true when source artifacts are newer than the AI insight snapshot."""

    snapshot_mtime = AI_INSIGHTS_SNAPSHOT_PATH.stat().st_mtime
    for source in (MODEL_PATH, PRICE_DATA_PATH, SENTIMENT_SUMMARY_PATH, LSTM_MODEL_PATH, LSTM_SCALER_PATH):
        if source.exists() and source.stat().st_mtime > snapshot_mtime:
            return True
    return False


@ttl_cache(ttl_seconds=60, name="recommendation")
def _cached_build_recommendation(ticker: str) -> tuple[dict[str, object], dict[str, object]]:
    """Cache assembled recommendation payloads across dashboard refreshes."""

    return _build_recommendation(ticker)


@lru_cache(maxsize=1)
def _get_shap_explainer() -> ShapExplainer:
    """Reuse the explainer/model object instead of loading it per request."""

    return ShapExplainer()


def _persist_recommendation_signal(
    recommendation: dict[str, object],
    feature_snapshot: dict[str, object],
    model_versions: dict[str, object],
) -> None:
    """Persist recommendation history outside the API response path."""

    db = SessionLocal()
    try:
        save_recommendation_signal(
            db,
            recommendation,
            feature_snapshot=feature_snapshot,
            model_versions=model_versions,
        )
    finally:
        db.close()


@router.get("/ai/sentiment")
@ttl_cache(ttl_seconds=60, name="market_sentiment")
def get_market_sentiment() -> dict[str, object]:
    """Return NLP market sentiment, falling back to breadth only if NLP data is absent."""

    nlp_sentiment = _nlp_market_sentiment()
    if nlp_sentiment:
        return nlp_sentiment
    return _market_breadth_sentiment()


def _nlp_market_sentiment() -> dict[str, object] | None:
    """Aggregate the merged NLP daily sentiment summary into the dashboard gauge."""

    package_sentiment = latest_market_package_sentiment()
    if package_sentiment:
        raw_score = float(package_sentiment["score"])
        gauge_score = int(round((raw_score + 1.0) * 50))
        label = _sentiment_gauge_label(gauge_score)
        article_count = int(package_sentiment["article_count"])
        as_of_date = package_sentiment["as_of_date"]
        return {
            "score": gauge_score,
            "label": label,
            "summary": (
                f"NLP sentiment pipeline is {label.replace('-', ' ')} with a market score of "
                f"{raw_score:.2f}, based on {article_count} market articles"
                f"{f' as of {as_of_date}' if as_of_date else ''}."
            ),
            "drivers": [
                {
                    "label": f"Pipeline market signal: {str(package_sentiment['signal']).upper()}",
                    "direction": "positive" if label in {"greed", "extreme-greed"} else "negative" if label in {"fear", "extreme-fear"} else "neutral",
                    "weight": 0.45,
                },
                {
                    "label": f"Pipeline articles analyzed: {article_count}",
                    "direction": "neutral",
                    "weight": 0.35,
                },
                {
                    "label": "Macro/news package export",
                    "direction": "neutral",
                    "weight": 0.2,
                },
            ],
            "source": "sentiment_pipeline_json",
            "articles": article_count,
            "tickersCovered": 0,
            "latestSummaryDate": as_of_date,
            "fallbackActive": False,
        }

    try:
        summary = load_daily_sentiment_summary()
    except Exception as exc:
        logger.warning("NLP market sentiment unavailable; falling back to breadth: %s", exc)
        return None

    required_columns = {
        "date",
        "ticker",
        "avg_sentiment",
        "positive_count",
        "negative_count",
        "neutral_count",
        "total_articles",
    }
    if summary.empty or not required_columns.issubset(set(summary.columns)):
        return None

    latest_rows = summary.copy()
    latest_rows["date"] = pd.to_datetime(latest_rows["date"], errors="coerce")
    latest_rows = latest_rows.dropna(subset=["date", "ticker"])
    if latest_rows.empty:
        return None

    latest_rows = latest_rows.sort_values("date").groupby("ticker", as_index=False).tail(1)
    sentiment_scores = pd.to_numeric(latest_rows["avg_sentiment"], errors="coerce").fillna(0.0).clip(-1.0, 1.0)
    article_weights = pd.to_numeric(latest_rows["total_articles"], errors="coerce").fillna(0.0).clip(lower=1.0)
    weighted_score = float((sentiment_scores * article_weights).sum() / article_weights.sum())
    weighted_score = max(-1.0, min(1.0, weighted_score))
    gauge_score = int(round((weighted_score + 1.0) * 50))

    positive_count = int(pd.to_numeric(latest_rows["positive_count"], errors="coerce").fillna(0).sum())
    negative_count = int(pd.to_numeric(latest_rows["negative_count"], errors="coerce").fillna(0).sum())
    neutral_count = int(pd.to_numeric(latest_rows["neutral_count"], errors="coerce").fillna(0).sum())
    article_count = int(pd.to_numeric(latest_rows["total_articles"], errors="coerce").fillna(0).sum())
    ticker_count = int(latest_rows["ticker"].nunique())
    latest_date = latest_rows["date"].max().date().isoformat()
    label = _sentiment_gauge_label(gauge_score)

    return {
        "score": gauge_score,
        "label": label,
        "summary": (
            f"NLP news sentiment is {label.replace('-', ' ')} with an average article score of "
            f"{weighted_score:.2f}, based on {article_count} processed articles across {ticker_count} tickers "
            f"as of {latest_date}."
        ),
        "drivers": [
            {
                "label": f"Positive NLP articles: {positive_count}",
                "direction": "positive" if positive_count >= negative_count else "neutral",
                "weight": 0.4,
            },
            {
                "label": f"Negative NLP articles: {negative_count}",
                "direction": "negative" if negative_count > positive_count else "neutral",
                "weight": 0.35,
            },
            {
                "label": f"Neutral/low-signal articles: {neutral_count}",
                "direction": "neutral",
                "weight": 0.25,
            },
        ],
        "source": "nlp_engine",
        "articles": article_count,
        "tickersCovered": ticker_count,
        "latestSummaryDate": latest_date,
        "fallbackActive": False,
    }


def _market_breadth_sentiment() -> dict[str, object]:
    """Fallback sentiment from market breadth when the NLP summary is unavailable."""

    latest = get_latest_by_ticker()
    up_count = int((latest["change"] > 0).sum())
    down_count = int((latest["change"] < 0).sum())
    total = max(len(latest), 1)
    score = round(((up_count - down_count) / total + 1) * 50)
    label = _sentiment_gauge_label(score)
    return {
        "score": score,
        "label": label,
        "summary": (
            f"NLP sentiment data is unavailable, so this fallback uses market breadth: "
            f"{up_count} advancers and {down_count} decliners across the latest NGX data."
        ),
        "drivers": [
            {"label": "Advancers vs decliners", "direction": "positive" if score >= 50 else "negative", "weight": 0.4},
            {"label": "Latest market breadth", "direction": "neutral", "weight": 0.3},
            {"label": "NLP summary unavailable", "direction": "neutral", "weight": 0.3},
        ],
        "source": "market_breadth_fallback",
        "articles": 0,
        "tickersCovered": 0,
        "latestSummaryDate": None,
        "fallbackActive": True,
    }


def _sentiment_gauge_label(score: int) -> str:
    """Map a 0-100 score to the frontend fear/greed gauge labels."""

    if score <= 20:
        return "extreme-fear"
    if score <= 40:
        return "fear"
    if score < 60:
        return "neutral"
    if score < 80:
        return "greed"
    return "extreme-greed"


def _lstm_passes_quality_gate(config: dict) -> tuple[bool, str]:
    """Return (passed, reason) based on lstm_quality_requirements vs lstm_metrics in config."""
    requirements = config.get("lstm_quality_requirements", {})
    metrics = config.get("lstm_metrics", {})
    roc_auc = float(metrics.get("roc_auc", 0.0))
    mcc = float(metrics.get("mcc", -1.0))
    bal_acc = float(metrics.get("balanced_accuracy", 0.0))
    predicted_up_pct = float(metrics.get("predicted_up_pct", 50.0))
    up_range = requirements.get("predicted_up_pct_range", [20, 80])
    min_roc = float(requirements.get("min_roc_auc", 0.55))
    min_mcc = float(requirements.get("min_mcc", 0.05))
    min_bal = float(requirements.get("min_balanced_accuracy", 0.55))
    if roc_auc < min_roc:
        return False, f"ROC-AUC {roc_auc:.3f} < threshold {min_roc:.2f}"
    if mcc < min_mcc:
        return False, f"MCC {mcc:.4f} < threshold {min_mcc:.4f}"
    if bal_acc < min_bal:
        return False, f"Balanced accuracy {bal_acc:.3f} < threshold {min_bal:.2f}"
    if not (up_range[0] <= predicted_up_pct <= up_range[1]):
        return False, f"Predicted UP% {predicted_up_pct:.1f}% outside range {up_range}"
    return True, "LSTM passed all quality thresholds"


def _build_recommendation(ticker: str) -> tuple[dict[str, object], dict[str, object]]:
    """Run the XGBoost-first public recommendation pipeline for one ticker."""

    prices = get_ticker_prices(ticker)
    feature_result = FeatureEngineer().engineer(prices, scale=False)
    latest_features = feature_result.features.tail(1)
    latest_model_features = feature_result.model_features.tail(1)
    latest = latest_features.iloc[-1]

    sentiment = latest_sentiment_for_ticker(str(latest["ticker"]))
    event_severity, event_alerts = detect_high_severity_events_for_ticker(str(latest["ticker"]))
    risk = RiskAnalyzer().analyze(
        feature_result.features,
        str(latest["ticker"]),
        macro_df=load_macro_asi(),
        sentiment_score=sentiment.score,
    )
    shap_explainer = _get_shap_explainer()
    try:
        xgb_prediction = predict_with_xgboost(latest_model_features)
    except XGBoostInferenceError as exc:
        raise RuntimeError(f"XGBoost recommendation failed for {ticker}: {exc}") from exc

    xgb_probability = xgb_prediction.up_probability
    final_probability = xgb_probability
    model_source = "xgboost_only"
    lstm_probability = None
    lstm_model_version = "disabled"
    lstm_available = False
    lstm_quality_passed = False
    lstm_used_in_final_decision = False
    lstm_reason = "LSTM model files not found — XGBoost-led mode active."
    config = get_backend_model_config()
    if config.get("use_lstm", False):
        try:
            lstm_probability, lstm_model_version = LSTMPredictor().predict_probability(prices)
        except Exception as exc:
            logger.warning("Optional LSTM prediction failed for %s: %s", ticker, exc)
            lstm_probability, lstm_model_version = None, "lstm-error"
        if lstm_probability is not None:
            lstm_available = True
            lstm_quality_passed, lstm_quality_reason = _lstm_passes_quality_gate(config)
            if lstm_quality_passed:
                xgb_weight = float(config.get("xgb_weight", 0.80))
                lstm_weight = float(config.get("lstm_weight", 0.20))
                total_weight = xgb_weight + lstm_weight
                if total_weight > 0:
                    final_probability = ((xgb_probability * xgb_weight) + (lstm_probability * lstm_weight)) / total_weight
                lstm_used_in_final_decision = True
                model_source = "xgboost_lstm_blend"
                lstm_reason = f"LSTM blended at {float(config.get('lstm_weight', 0.20)):.0%} weight. {lstm_quality_reason}"
            else:
                model_source = "xgboost_led_with_lstm_diagnostic"
                lstm_reason = f"LSTM loaded but did not pass quality gate: {lstm_quality_reason}. XGBoost-led mode active."
        else:
            lstm_reason = f"LSTM unavailable: {lstm_model_version}. XGBoost-led mode active."

    base_action = action_from_probability(final_probability)
    action = base_action
    confidence = confidence_from_probability(final_probability)
    risk_reasons = [flag.description for flag in risk.flags]
    filter_reasons: list[str] = []
    if action == "BUY" and risk.risk_score >= 70:
        action = "HOLD"
        filter_reasons.append(f"BUY downgraded to HOLD because risk score is {risk.risk_score:.1f}.")
    if action == "BUY" and sentiment.score < -0.5:
        action = "HOLD"
        filter_reasons.append(f"BUY downgraded to HOLD because sentiment is {sentiment.score:.2f}.")
    if action in {"BUY", "SELL"} and confidence < 0.16:
        action = "HOLD"
        filter_reasons.append("Directional confidence is too low for an active BUY or SELL signal.")

    # Event severity overrides — news-driven events the model has not seen
    if event_severity == "CRITICAL":
        action = "HOLD"
        confidence = min(confidence, 0.10)
        filter_reasons.append(
            "CRITICAL market event detected in news — model output overridden. "
            "Do not act on any directional signal until this resolves."
        )
    elif event_severity == "HIGH" and action == "BUY":
        action = "HOLD"
        filter_reasons.append("BUY downgraded to HOLD: high-severity news event detected.")

    # Volatility regime override — statistical distribution has shifted
    if risk.regime_alert:
        if action == "BUY":
            action = "HOLD"
            filter_reasons.append(f"BUY downgraded to HOLD: abnormal volatility regime. {risk.regime_reason}")
        else:
            filter_reasons.append(f"Model confidence reduced: abnormal volatility regime. {risk.regime_reason}")

    shap_explainer = _get_shap_explainer()
    shap_explanation = shap_explainer.explain_single(latest_model_features)
    try:
        _nlg_signal = SignalOutput(
            ticker=str(latest["ticker"]),
            date=risk.date,
            recommendation=RecommendationAction(action),
            confidence=confidence * 100,
            risk_score=risk.risk_score,
            signal_strength=SignalStrength(_signal_strength(confidence)),
            ensemble_prob=final_probability,
            reasons=filter_reasons,
        )
        explanation = NLGGenerator().generate(
            signal=_nlg_signal,
            shap_values=shap_explanation.drivers,
            sentiment_label=sentiment.label,
            risk_profile=risk,
        )
        explanation["risk_notes"] = filter_reasons
        explanation["model_notes"] = [
            "XGBoost is the primary model. LSTM is quality-gated and blended when it passes."
        ]
    except Exception as _nlg_exc:
        logger.warning("NLG generation failed for %s, using fallback: %s", ticker, _nlg_exc)
        explanation = _xgb_explanation(
            action, final_probability, shap_explanation.drivers,
            risk.risk_score, sentiment.score, filter_reasons,
        )

    momentum = latest_package_momentum_for_ticker(str(latest["ticker"]))
    article_breakdown = latest_package_breakdown_for_ticker(str(latest["ticker"])) or []
    sentiment_history = load_sentiment_history_for_ticker(str(latest["ticker"]), days=30)

    history_payload = []
    if not sentiment_history.empty:
        for _, row in sentiment_history.iterrows():
            history_payload.append(
                {
                    "date"           : row["date"].date().isoformat() if hasattr(row["date"], "date") else str(row["date"]),
                    "sentiment_score": float(row["sentiment_score"] or 0.0),
                    "signal"         : str(row.get("signal", "NEUTRAL") or "NEUTRAL"),
                    "article_count"  : int(row.get("article_count", 0) or 0),
                }
            )

    recommendation = {
        "ticker": public_ticker(str(latest["ticker"])),
        "date": risk.date.isoformat(),
        "recommendation": action,
        "action": action,
        "confidence": round(confidence, 4),
        "risk_score": round(risk.risk_score, 1),
        "risk_level": risk.risk_level.value,
        "risk_reasons": risk_reasons,
        "signal_strength": _signal_strength(confidence),
        "ensemble_prob": round(final_probability, 4),
        "up_probability": round(final_probability, 4),
        "main_model": "xgboost",
        "model_source": model_source,
        "reason": _recommendation_reason(action, base_action, final_probability, risk.risk_score, sentiment.score, filter_reasons),
        "xgboost_probability": round(xgb_probability, 3),
        "xgb_probability": round(xgb_probability, 3),
        "final_probability": round(final_probability, 4),
        "lstm_probability": round(lstm_probability, 3) if lstm_probability is not None else None,
        "lstm_available": lstm_available,
        "lstm_quality_passed": lstm_quality_passed,
        "lstm_used_in_final_decision": lstm_used_in_final_decision,
        "lstm_reason": lstm_reason,
        "sentiment_score": round(sentiment.score, 3),
        "sentiment_label": sentiment.label,
        "sector_adjustment": None,
        "explanation": explanation,
        "regime_alert": risk.regime_alert,
        "regime_reason": risk.regime_reason if risk.regime_alert else None,
        "event_severity": event_severity,
        "event_alerts": event_alerts,
        "news": {
            "momentum"      : momentum,
            "articles"      : article_breakdown,
            "history"       : history_payload,
        },
    }
    debug_payload = {
        "feature_snapshot": latest_model_features.tail(1).to_dict(orient="records")[0],
        "model_versions": {
            "advisor": "ngx-advisor-v0.1",
            "xgboost": xgb_prediction.model_path,
            "xgb_feature_list": xgb_prediction.feature_list_path,
            "lstm": lstm_model_version,
            "sentiment": sentiment.label,
            "sentiment_articles": sentiment.total_articles,
            "sentiment_as_of": sentiment.as_of_date,
            "sentiment_source": sentiment.source,
            "shap_available": shap_explanation.shap_available,
            "model_loaded": shap_explanation.model_loaded,
        },
    }
    return recommendation, debug_payload


def _xgb_explanation(
    action: str,
    up_probability: float,
    drivers: list[object],
    risk_score: float,
    sentiment_score: float,
    filter_reasons: list[str],
) -> dict[str, object]:
    """Build the explanation object without requiring non-XGBoost signals."""

    return {
        "headline": f"{action} signal from XGBoost",
        "summary": _recommendation_reason(action, action, up_probability, risk_score, sentiment_score, filter_reasons),
        "drivers": [
            {
                "factor": getattr(driver, "factor", "XGBoost feature"),
                "effect": getattr(driver, "effect", "neutral"),
                "impact": getattr(driver, "impact", "LOW"),
                "shap": getattr(driver, "shap", 0.0),
                "alignment": getattr(driver, "alignment", "model"),
            }
            for driver in drivers
        ],
        "risk_notes": filter_reasons,
        "model_notes": ["XGBoost is the primary model. LSTM is optional and disabled unless backend config enables it."],
    }


def _recommendation_reason(
    action: str,
    base_action: str,
    up_probability: float,
    risk_score: float,
    sentiment_score: float,
    filter_reasons: list[str],
) -> str:
    """Explain the final action using real model/risk/sentiment values."""

    if filter_reasons:
        return (
            f"XGBoost produced a {base_action} base signal with {up_probability:.1%} upside probability, "
            f"but the final action is {action}. " + " ".join(filter_reasons)
        )
    if action == "BUY":
        return (
            f"XGBoost gives {up_probability:.1%} probability of upward movement; "
            f"risk score is {risk_score:.1f} and sentiment is {sentiment_score:.2f}, so BUY is allowed."
        )
    if action == "SELL":
        return (
            f"XGBoost gives only {up_probability:.1%} probability of upward movement; "
            f"risk score is {risk_score:.1f} and sentiment is {sentiment_score:.2f}."
        )
    return (
        f"XGBoost gives {up_probability:.1%} probability of upward movement, "
        f"with risk score {risk_score:.1f} and sentiment {sentiment_score:.2f}; confidence is not strong enough for BUY or SELL."
    )


def _signal_strength(confidence: float) -> str:
    """Map 0..1 probability confidence to existing strength labels."""

    if confidence >= 0.36:
        return "STRONG"
    if confidence >= 0.16:
        return "MODERATE"
    return "WEAK"


def _recommendation_to_ai_insight(recommendation: dict[str, object]) -> dict[str, object]:
    """Map recommendation contract to existing frontend AIInsight type."""

    rec = str(recommendation["recommendation"])
    outlook = "bullish" if rec == "BUY" else "bearish" if rec in {"SELL", "AVOID"} else "neutral"
    explanation = recommendation["explanation"]
    drivers = [
        {
            "label": driver["factor"],
            "direction": "positive" if driver["effect"] == "bullish" else "negative" if driver["effect"] == "bearish" else "neutral",
            "weight": min(1.0, abs(float(driver["shap"]))),
        }
        for driver in explanation["drivers"]
    ]
    risk_score = float(recommendation["risk_score"])
    raw_confidence = float(recommendation["confidence"])
    display_confidence = round(raw_confidence * 100, 1) if raw_confidence <= 1 else raw_confidence
    return {
        "symbol": recommendation["ticker"],
        "outlook": outlook,
        "confidence": display_confidence,
        "summary": explanation["summary"],
        "drivers": drivers,
        "risks": {
            "marketRisk": round(risk_score * 0.35),
            "sectorRisk": round(risk_score * 0.30),
            "companyRisk": round(risk_score * 0.35),
        },
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "horizonDays": 90,
        "modelVersion": "ngx-advisor-v0.1",
        "xgboostProbability": recommendation.get("xgboost_probability"),
        "lstmProbability": recommendation.get("lstm_probability"),
        "lstmAvailable": recommendation.get("lstm_available", False),
        "lstmQualityPassed": recommendation.get("lstm_quality_passed", False),
        "lstmUsedInFinalDecision": recommendation.get("lstm_used_in_final_decision", False),
        "lstmReason": recommendation.get("lstm_reason"),
        "modelSource": recommendation.get("model_source", "xgboost_only"),
        "finalProbability": recommendation.get("final_probability"),
        "regimeAlert": bool(recommendation.get("regime_alert", False)),
        "regimeReason": recommendation.get("regime_reason"),
        "eventSeverity": recommendation.get("event_severity", "NORMAL"),
        "eventAlerts": recommendation.get("event_alerts", []),
    }
