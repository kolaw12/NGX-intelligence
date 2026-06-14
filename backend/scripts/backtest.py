"""NGX AI Advisor — Backtesting Module.

Replays XGBoost (and optionally LSTM) recommendations over historical price
data and measures signal quality, trading P&L, and risk-adjusted returns.

Usage:
    # Backtest all tickers, last 252 trading days
    python scripts/backtest.py

    # Specific tickers and date range
    python scripts/backtest.py --tickers DANGCEM GTCO MTNN --start 2024-01-01 --end 2024-12-31

    # Save detailed trade log to CSV
    python scripts/backtest.py --output reports/backtest_results.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR  = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.crud import get_ticker_prices, load_tickers
from app.services.backend_model_config import get_backend_model_config
from app.services.feature_engineer import FeatureEngineer
from app.services.xgboost_predictor import predict_with_xgboost, XGBoostInferenceError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── constants ─────────────────────────────────────────────────────────────────

BUY_THRESHOLD  = 0.60   # probability above which we signal BUY
SELL_THRESHOLD = 0.40   # probability below which we signal SELL
HOLDING_DAYS   = 5      # hold a position for this many trading days
TRANSACTION_COST = 0.005  # 0.5% round-trip cost (NGX brokerage estimate)
DEFAULT_LOOKBACK = 252   # trading days to backtest by default


# ── signal generation ─────────────────────────────────────────────────────────

def _action_from_prob(prob: float) -> str:
    if prob >= BUY_THRESHOLD:
        return "BUY"
    if prob <= SELL_THRESHOLD:
        return "SELL"
    return "HOLD"


def generate_signals(
    ticker: str,
    prices: pd.DataFrame,
    start: date,
    end: date,
) -> pd.DataFrame:
    """Generate daily BUY/HOLD/SELL signals for one ticker over [start, end].

    Signals are generated on each day using only data up to that day
    (no future leakage). The model sees the same rolling window it would
    see in production.
    """
    prices = prices.copy()
    prices["date"] = pd.to_datetime(prices["date"])
    prices = prices.sort_values("date").reset_index(drop=True)

    fe = FeatureEngineer()
    rows: list[dict] = []

    date_range = prices[(prices["date"].dt.date >= start) & (prices["date"].dt.date <= end)]

    for idx, row in date_range.iterrows():
        signal_date = row["date"].date()

        # Use all history up to and including this date
        history = prices[prices["date"] <= row["date"]].copy()
        if len(history) < 20:   # need at least 20 rows for indicators
            continue

        try:
            feature_result = fe.engineer(history, scale=False)
            latest_features = feature_result.model_features.tail(1)
            prediction = predict_with_xgboost(latest_features)
            prob   = float(prediction.up_probability)
            action = _action_from_prob(prob)
        except (XGBoostInferenceError, Exception) as exc:
            logger.debug("Signal failed for %s on %s: %s", ticker, signal_date, exc)
            prob   = 0.5
            action = "HOLD"

        rows.append({
            "date":        signal_date,
            "ticker":      ticker,
            "close":       float(row["close"]),
            "signal":      action,
            "probability": round(prob, 4),
        })

    return pd.DataFrame(rows)


# ── trade simulation ──────────────────────────────────────────────────────────

def simulate_trades(signals: pd.DataFrame) -> pd.DataFrame:
    """Convert daily signals into fixed-holding-period trades.

    Entry: signal=BUY or signal=SELL on day T
    Exit : HOLDING_DAYS later (or last available price)
    Return: (exit_price - entry_price) / entry_price − transaction_cost
    """
    trades: list[dict] = []
    prices = signals.set_index("date")["close"].to_dict()
    dates  = sorted(prices.keys())

    for i, row in signals.iterrows():
        if row["signal"] not in ("BUY", "SELL"):
            continue

        entry_date  = row["date"]
        entry_price = row["close"]
        direction   = 1 if row["signal"] == "BUY" else -1

        # find exit date (HOLDING_DAYS later)
        future_dates = [d for d in dates if d > entry_date]
        if len(future_dates) < HOLDING_DAYS:
            if not future_dates:
                continue
            exit_date = future_dates[-1]
        else:
            exit_date = future_dates[HOLDING_DAYS - 1]

        exit_price = prices.get(exit_date, entry_price)

        raw_return   = (exit_price - entry_price) / max(entry_price, 1e-6)
        trade_return = direction * raw_return - TRANSACTION_COST

        trades.append({
            "entry_date":   entry_date,
            "exit_date":    exit_date,
            "ticker":       row["ticker"],
            "signal":       row["signal"],
            "entry_price":  round(entry_price, 4),
            "exit_price":   round(exit_price,  4),
            "raw_return":   round(raw_return,   4),
            "trade_return": round(trade_return, 4),
            "probability":  row["probability"],
        })

    return pd.DataFrame(trades)


# ── performance metrics ───────────────────────────────────────────────────────

def compute_metrics(trades: pd.DataFrame, signals: pd.DataFrame) -> dict:
    """Compute standard backtest performance metrics."""
    if trades.empty:
        return {"error": "No trades generated — check signal thresholds or data range."}

    returns = trades["trade_return"].values
    n       = len(returns)
    wins    = int((returns > 0).sum())
    losses  = int((returns < 0).sum())

    win_rate   = wins / max(n, 1)
    avg_return = float(returns.mean())
    std_return = float(returns.std()) if n > 1 else 0.0
    sharpe     = (avg_return / max(std_return, 1e-9)) * np.sqrt(252 / HOLDING_DAYS)

    # Cumulative return (each trade is independent, equal-weight)
    cumulative = float((1 + pd.Series(returns)).prod() - 1)

    # Max drawdown from equity curve
    equity = (1 + pd.Series(returns)).cumprod()
    rolling_max = equity.cummax()
    drawdowns   = (equity - rolling_max) / rolling_max
    max_drawdown = float(drawdowns.min())

    # Profit factor
    gross_profit = float(returns[returns > 0].sum()) if wins > 0 else 0.0
    gross_loss   = float(abs(returns[returns < 0].sum())) if losses > 0 else 1e-9
    profit_factor = gross_profit / gross_loss

    # Signal distribution
    sig_counts = signals["signal"].value_counts().to_dict()

    # BUY vs SELL breakdown
    buy_trades  = trades[trades["signal"] == "BUY"]
    sell_trades = trades[trades["signal"] == "SELL"]

    return {
        "total_trades":    n,
        "buy_trades":      len(buy_trades),
        "sell_trades":     len(sell_trades),
        "win_rate":        round(win_rate,    4),
        "avg_return_pct":  round(avg_return * 100, 3),
        "std_return_pct":  round(std_return * 100, 3),
        "cumulative_return_pct": round(cumulative * 100, 3),
        "annualised_sharpe":     round(sharpe,      3),
        "max_drawdown_pct":      round(max_drawdown * 100, 3),
        "profit_factor":         round(profit_factor, 3),
        "gross_profit_pct":      round(gross_profit * 100, 3),
        "gross_loss_pct":        round(gross_loss * 100, 3),
        "holding_days":          HOLDING_DAYS,
        "transaction_cost_pct":  TRANSACTION_COST * 100,
        "buy_threshold":         BUY_THRESHOLD,
        "sell_threshold":        SELL_THRESHOLD,
        "signal_distribution":   sig_counts,
        "buy_win_rate":  round((buy_trades["trade_return"] > 0).mean(), 4) if len(buy_trades) else None,
        "sell_win_rate": round((sell_trades["trade_return"] > 0).mean(), 4) if len(sell_trades) else None,
        "avg_buy_return_pct":  round(buy_trades["trade_return"].mean() * 100, 3) if len(buy_trades) else None,
        "avg_sell_return_pct": round(sell_trades["trade_return"].mean() * 100, 3) if len(sell_trades) else None,
    }


# ── per-ticker runner ─────────────────────────────────────────────────────────

def backtest_ticker(ticker: str, start: date, end: date) -> dict:
    """Run full backtest for one ticker. Returns metrics dict."""
    logger.info("Backtesting %s  (%s → %s)", ticker, start, end)
    try:
        prices = get_ticker_prices(ticker)
    except Exception as exc:
        logger.warning("  Could not load prices for %s: %s", ticker, exc)
        return {"ticker": ticker, "error": str(exc)}

    if prices.empty:
        return {"ticker": ticker, "error": "No price data found."}

    signals = generate_signals(ticker, prices, start, end)
    if signals.empty:
        return {"ticker": ticker, "error": "No signals generated — insufficient history."}

    trades  = simulate_trades(signals)
    metrics = compute_metrics(trades, signals)

    return {
        "ticker":       ticker,
        "start":        start.isoformat(),
        "end":          end.isoformat(),
        "signal_days":  len(signals),
        **metrics,
    }


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="NGX AI Advisor Backtester")
    parser.add_argument("--tickers",  nargs="+", help="Tickers to backtest (default: all)")
    parser.add_argument("--start",    help="Start date YYYY-MM-DD (default: 252 days ago)")
    parser.add_argument("--end",      help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--output",   default="reports/backtest_results.json", help="Output JSON path")
    parser.add_argument("--trades-csv", help="Optional path to save full trade log CSV")
    args = parser.parse_args()

    end_date   = date.fromisoformat(args.end)   if args.end   else date.today()
    start_date = date.fromisoformat(args.start) if args.start else end_date - timedelta(days=DEFAULT_LOOKBACK)

    # Resolve tickers
    if args.tickers:
        tickers = [t.upper().strip() for t in args.tickers]
    else:
        try:
            tickers_df = load_tickers()
            tickers = tickers_df["ticker"].astype(str).str.upper().str.strip().tolist()
        except Exception as exc:
            logger.error("Could not load ticker list: %s", exc)
            sys.exit(1)

    logger.info("Backtesting %d tickers  |  %s → %s", len(tickers), start_date, end_date)
    logger.info("Holding period: %d days  |  Transaction cost: %.1f%%", HOLDING_DAYS, TRANSACTION_COST * 100)

    results: list[dict] = []
    all_trades: list[pd.DataFrame] = []

    for ticker in tickers:
        result = backtest_ticker(ticker, start_date, end_date)
        results.append(result)
        if "error" not in result:
            logger.info(
                "  %s — trades: %d  win_rate: %.1f%%  cum_return: %.1f%%  sharpe: %.2f",
                ticker,
                result.get("total_trades", 0),
                result.get("win_rate", 0) * 100,
                result.get("cumulative_return_pct", 0),
                result.get("annualised_sharpe", 0),
            )

    # Aggregate portfolio metrics
    valid = [r for r in results if "error" not in r and r.get("total_trades", 0) > 0]
    if valid:
        portfolio = {
            "tickers_backtested":   len(results),
            "tickers_with_trades":  len(valid),
            "avg_win_rate":         round(np.mean([r["win_rate"] for r in valid]), 4),
            "avg_cum_return_pct":   round(np.mean([r["cumulative_return_pct"] for r in valid]), 3),
            "avg_sharpe":           round(np.mean([r["annualised_sharpe"] for r in valid]), 3),
            "avg_max_drawdown_pct": round(np.mean([r["max_drawdown_pct"] for r in valid]), 3),
            "total_trades":         sum(r["total_trades"] for r in valid),
        }
    else:
        portfolio = {"error": "No valid backtest results — check data pipeline."}

    output = {
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "start":          start_date.isoformat(),
        "end":            end_date.isoformat(),
        "holding_days":   HOLDING_DAYS,
        "portfolio_summary": portfolio,
        "ticker_results": results,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2))
    logger.info("Results saved → %s", output_path)

    # Print summary table
    print("\n" + "=" * 72)
    print(f"  BACKTEST SUMMARY  |  {start_date} → {end_date}  |  {len(tickers)} tickers")
    print("=" * 72)
    if valid:
        print(f"  Avg win rate      : {portfolio['avg_win_rate']*100:.1f}%")
        print(f"  Avg cum return    : {portfolio['avg_cum_return_pct']:.1f}%")
        print(f"  Avg Sharpe        : {portfolio['avg_sharpe']:.2f}")
        print(f"  Avg max drawdown  : {portfolio['avg_max_drawdown_pct']:.1f}%")
        print(f"  Total trades      : {portfolio['total_trades']:,}")
    else:
        print("  No valid results.")
    print("=" * 72)


if __name__ == "__main__":
    main()
