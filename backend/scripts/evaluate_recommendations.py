"""Evaluate historical recommendation accuracy against actual price movements.

Loads persisted recommendation signals from the database and compares each
BUY/SELL signal against the actual price change N days after the signal date.
Prints a summary broken down by action, confidence band, and ticker.

Usage:
    python scripts/evaluate_recommendations.py [--horizon 10] [--min-signals 5]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MIN_SIGNALS_FOR_REPORT = 5
DEFAULT_HORIZON_DAYS = 10


def _load_signals() -> list[dict[str, Any]]:
    from app.db.database import SessionLocal
    from app.db.models import RecommendationSignal

    db = SessionLocal()
    try:
        rows = db.query(RecommendationSignal).order_by(RecommendationSignal.signal_date.asc()).all()
        return [
            {
                "id": r.id,
                "ticker": r.ticker,
                "signal_date": r.signal_date,
                "recommendation": r.recommendation.value if hasattr(r.recommendation, "value") else str(r.recommendation),
                "confidence": float(r.confidence),
                "risk_level": r.risk_level.value if hasattr(r.risk_level, "value") else str(r.risk_level),
                "ensemble_prob": float(r.ensemble_prob),
                "xgb_probability": float(r.xgb_probability) if r.xgb_probability is not None else None,
                "lstm_probability": float(r.lstm_probability) if r.lstm_probability is not None else None,
            }
            for r in rows
        ]
    finally:
        db.close()


def _load_prices_for_ticker(ticker: str):
    try:
        from app.db.crud import get_ticker_prices
        return get_ticker_prices(ticker)
    except Exception:
        return None


def _price_on_or_after(prices, target_date: date) -> float | None:
    """Return the closing price on target_date or the next available trading day."""
    import pandas as pd
    if prices is None or prices.empty:
        return None
    prices["date"] = pd.to_datetime(prices["date"]).dt.date
    future = prices[prices["date"] >= target_date].sort_values("date")
    if future.empty:
        return None
    return float(future.iloc[0]["close"])


def _confidence_band(confidence: float) -> str:
    if confidence >= 0.36:
        return "strong (≥0.36)"
    if confidence >= 0.16:
        return "moderate (0.16–0.35)"
    return "weak (<0.16)"


def evaluate(horizon_days: int = DEFAULT_HORIZON_DAYS, min_signals: int = MIN_SIGNALS_FOR_REPORT) -> None:
    print(f"NGX Recommendation Evaluator — {horizon_days}-day outcome horizon\n{'─' * 55}")

    signals = _load_signals()
    total = len(signals)
    print(f"Signals in database: {total}")

    if total < min_signals:
        print(
            f"\nNot enough recommendation history yet.\n"
            f"Need at least {min_signals} signals; have {total}.\n"
            f"This report will be meaningful once the daily pipeline has been running for several weeks."
        )
        return

    cutoff = date.today() - timedelta(days=horizon_days)
    evaluable = [s for s in signals if s["signal_date"] <= cutoff and s["recommendation"] in {"BUY", "SELL"}]
    print(f"Evaluable BUY/SELL signals (signal_date ≤ {cutoff}): {len(evaluable)}")

    if len(evaluable) < min_signals:
        print(
            f"\nNot enough evaluable signals yet.\n"
            f"Most signals are too recent to have a {horizon_days}-day outcome.\n"
            f"Run this script again once more signals have matured past {cutoff}."
        )
        return

    print("\nLoading price data for outcome comparison (this may take a moment)...")

    # Group by ticker to avoid re-loading prices per signal
    tickers = list({s["ticker"] for s in evaluable})
    prices_by_ticker = {t: _load_prices_for_ticker(t) for t in tickers}

    results = []
    for sig in evaluable:
        ticker = sig["ticker"]
        prices = prices_by_ticker.get(ticker)
        entry_price = _price_on_or_after(prices, sig["signal_date"])
        outcome_price = _price_on_or_after(prices, sig["signal_date"] + timedelta(days=horizon_days))
        if entry_price is None or outcome_price is None or entry_price == 0:
            continue
        actual_return = (outcome_price - entry_price) / entry_price
        if sig["recommendation"] == "BUY":
            correct = actual_return > 0
        else:  # SELL
            correct = actual_return < 0
        results.append({
            **sig,
            "entry_price": entry_price,
            "outcome_price": outcome_price,
            "actual_return_pct": round(actual_return * 100, 2),
            "correct": correct,
        })

    if not results:
        print("\nCould not compute outcomes — price data may be unavailable for evaluated tickers.")
        return

    total_eval = len(results)
    correct_count = sum(1 for r in results if r["correct"])
    overall_accuracy = correct_count / total_eval * 100

    print(f"\n{'─' * 55}")
    print(f"OVERALL ACCURACY: {overall_accuracy:.1f}%  ({correct_count}/{total_eval} signals correct)")
    print(f"{'─' * 55}")

    # By action
    print("\nBy action:")
    for action in ("BUY", "SELL"):
        subset = [r for r in results if r["recommendation"] == action]
        if not subset:
            continue
        acc = sum(1 for r in subset if r["correct"]) / len(subset) * 100
        print(f"  {action:<6} {acc:5.1f}%  ({len(subset)} signals)")

    # By confidence band
    print("\nBy confidence band:")
    for band in ["strong (≥0.36)", "moderate (0.16–0.35)", "weak (<0.16)"]:
        subset = [r for r in results if _confidence_band(r["confidence"]) == band]
        if not subset:
            continue
        acc = sum(1 for r in subset if r["correct"]) / len(subset) * 100
        print(f"  {band:<28} {acc:5.1f}%  ({len(subset)} signals)")

    # By ticker (top 10 by signal count)
    print("\nBy ticker (≥3 evaluable signals):")
    ticker_groups: dict[str, list] = {}
    for r in results:
        ticker_groups.setdefault(r["ticker"], []).append(r)
    sorted_tickers = sorted(ticker_groups.items(), key=lambda kv: len(kv[1]), reverse=True)
    for ticker, group in sorted_tickers:
        if len(group) < 3:
            continue
        acc = sum(1 for r in group if r["correct"]) / len(group) * 100
        avg_return = sum(r["actual_return_pct"] for r in group) / len(group)
        print(f"  {ticker:<12} {acc:5.1f}%  ({len(group)} signals, avg return {avg_return:+.1f}%)")

    print(f"\n{'─' * 55}")
    print("Note: Past accuracy is not a guarantee of future performance.")
    print("HOLD signals are excluded from this accuracy report.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate NGX recommendation accuracy.")
    parser.add_argument("--horizon", type=int, default=DEFAULT_HORIZON_DAYS, help="Days after signal date to measure outcome (default: 10)")
    parser.add_argument("--min-signals", type=int, default=MIN_SIGNALS_FOR_REPORT, help="Minimum signals required before reporting (default: 5)")
    args = parser.parse_args()
    evaluate(horizon_days=args.horizon, min_signals=args.min_signals)
