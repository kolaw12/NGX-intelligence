"""Weekly XGBoost retraining script.

Loads the latest engineered features from local price parquet files, builds a
binary UP/DOWN label from the next-day forward return, trains XGBoost on a
rolling 2-year window, validates AUC-ROC on a 60-day hold-out, and writes a
new model only when quality passes the minimum threshold.

Usage:
    python scripts/train_xgboost.py                  # normal run
    python scripts/train_xgboost.py --min-auc 0.52   # relax threshold
    python scripts/train_xgboost.py --dry-run         # train but do not save
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from xgboost import XGBClassifier

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.crud import get_latest_by_ticker, load_tickers          # noqa: E402
from app.services.feature_engineer import FeatureEngineer            # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

MODELS_DIR = BACKEND_ROOT / "models"
OUTPUT_MODEL_PATH = MODELS_DIR / "xgboost_model.pkl"
OUTPUT_FEATURE_LIST_PATH = MODELS_DIR / "xgb_feature_list.json"
METRICS_PATH = MODELS_DIR / "last_retrain_metrics.json"

ROLLING_WINDOW_DAYS = 730        # 2-year training window
HOLDOUT_DAYS = 60                # 60-day validation hold-out
MIN_TRAINING_ROWS = 2_000        # abort if fewer rows than this
UP_RETURN_THRESHOLD = 0.005      # >0.5% next-day return = class 1 (UP)

XGB_PARAMS = {
    "n_estimators": 1_000,
    "max_depth": 5,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "use_label_encoder": False,
    "random_state": 42,
    "n_jobs": -1,
    "early_stopping_rounds": 50,
}


def build_training_frame() -> pd.DataFrame:
    """Load all tickers, engineer features, add forward-return label."""

    logger.info("Loading ticker price data …")
    tickers_df = load_tickers()
    all_tickers = tickers_df["ticker"].astype(str).str.upper().str.strip().tolist()
    logger.info("  %d tickers in master list", len(all_tickers))

    fe = FeatureEngineer()
    frames: list[pd.DataFrame] = []

    from app.db.crud import get_ticker_prices  # imported here to avoid circular at module level
    skipped = 0
    for ticker in all_tickers:
        try:
            prices = get_ticker_prices(ticker)
            if len(prices) < 60:
                skipped += 1
                continue
            result = fe.engineer(prices, scale=False)
            feat = result.features.copy()
            # Forward 1-day return label
            feat["_next_close"] = feat["close"].shift(-1)
            feat["_fwd_return"] = (feat["_next_close"] - feat["close"]) / feat["close"].replace(0, np.nan)
            feat["label"] = (feat["_fwd_return"] > UP_RETURN_THRESHOLD).astype(int)
            feat = feat.dropna(subset=["label", "close"])
            if not feat.empty:
                frames.append(feat)
        except Exception as exc:
            logger.debug("Skipping %s: %s", ticker, exc)
            skipped += 1

    logger.info("  Loaded %d tickers, skipped %d", len(frames), skipped)
    if not frames:
        raise RuntimeError("No ticker data could be loaded — check price parquet files.")

    combined = pd.concat(frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    combined = combined.dropna(subset=["date"]).sort_values("date")
    logger.info("  Combined frame: %d rows, date range %s → %s",
                len(combined),
                combined["date"].min().date(),
                combined["date"].max().date())
    return combined


def select_window(df: pd.DataFrame) -> pd.DataFrame:
    """Trim to rolling 2-year window ending at the latest available date."""

    latest = df["date"].max()
    cutoff = latest - pd.Timedelta(days=ROLLING_WINDOW_DAYS)
    windowed = df[df["date"] >= cutoff].copy()
    logger.info("  Rolling window (%d days): %d → %d rows", ROLLING_WINDOW_DAYS, len(df), len(windowed))
    return windowed


def train_validate(df: pd.DataFrame, feature_list: list[str], min_auc: float, dry_run: bool) -> dict:
    """Split train/holdout, train XGBoost, return metrics dict."""

    df = df.copy().sort_values("date")
    holdout_cutoff = df["date"].max() - pd.Timedelta(days=HOLDOUT_DAYS)
    train_df = df[df["date"] < holdout_cutoff]
    val_df = df[df["date"] >= holdout_cutoff]

    logger.info("  Train rows: %d  |  Validation rows: %d", len(train_df), len(val_df))

    if len(train_df) < MIN_TRAINING_ROWS:
        raise RuntimeError(
            f"Only {len(train_df)} training rows — need at least {MIN_TRAINING_ROWS}. "
            "Run the daily price pipeline first to accumulate more history."
        )

    # Fill missing features with 0 (consistent with inference path)
    X_train = train_df[feature_list].fillna(0.0).astype(float)
    y_train = train_df["label"].astype(int)
    X_val = val_df[feature_list].fillna(0.0).astype(float)
    y_val = val_df["label"].astype(int)

    class_counts = y_train.value_counts()
    n_down = int(class_counts.get(0, 1))
    n_up   = int(max(class_counts.get(1, 1), 1))
    # True imbalance ratio — gives XGBoost the correct prior for rare UP moves.
    # NGX data typically has ~15% UP labels so scale_pos_weight ≈ 5.75.
    # A floor of 1.0 prevents division issues on balanced datasets.
    scale_pos_weight = max(1.0, float(n_down) / float(n_up))
    up_pct = 100.0 * n_up / (n_down + n_up)
    logger.info(
        "  Class balance — DOWN: %d  UP: %d  (%.1f%% UP)  scale_pos_weight: %.2f",
        n_down, n_up, up_pct, scale_pos_weight,
    )
    if up_pct < 20.0:
        logger.warning(
            "  UP class is only %.1f%% of training data. scale_pos_weight=%.2f will correct"
            " for imbalance. Verify labels are not systematically biased.",
            up_pct, scale_pos_weight,
        )

    params = {**XGB_PARAMS, "scale_pos_weight": scale_pos_weight}
    model = XGBClassifier(**params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    y_prob = model.predict_proba(X_val)[:, 1]
    auc = float(roc_auc_score(y_val, y_prob))
    best_iteration = getattr(model, "best_iteration", params["n_estimators"])
    logger.info("  Validation AUC-ROC: %.4f  (threshold: %.2f)  best_iteration: %d",
                auc, min_auc, best_iteration)

    metrics = {
        "auc_roc": round(auc, 4),
        "min_auc_threshold": min_auc,
        "passed": auc >= min_auc,
        "train_rows": int(len(train_df)),
        "val_rows": int(len(val_df)),
        "best_iteration": int(best_iteration),
        "features": len(feature_list),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if auc < min_auc:
        logger.warning(
            "  AUC-ROC %.4f is below threshold %.2f — model NOT saved. "
            "Keeping previous model artifact.",
            auc, min_auc,
        )
        return metrics

    if dry_run:
        logger.info("  --dry-run: model trained but NOT saved.")
        return metrics

    # Back up the existing model before overwriting
    if OUTPUT_MODEL_PATH.exists():
        backup = OUTPUT_MODEL_PATH.with_suffix(f".{datetime.now(timezone.utc).strftime('%Y%m%d')}.bak.pkl")
        shutil.copy2(OUTPUT_MODEL_PATH, backup)
        logger.info("  Backed up existing model to %s", backup.name)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, OUTPUT_MODEL_PATH)
    json.dump(feature_list, OUTPUT_FEATURE_LIST_PATH.open("w"), indent=2)
    logger.info("  Saved new model → %s", OUTPUT_MODEL_PATH)
    logger.info("  Saved feature list (%d features) → %s", len(feature_list), OUTPUT_FEATURE_LIST_PATH)

    return metrics


def resolve_feature_list(df: pd.DataFrame) -> list[str]:
    """Use existing feature list if present; otherwise derive from the frame."""

    if OUTPUT_FEATURE_LIST_PATH.exists():
        existing = json.loads(OUTPUT_FEATURE_LIST_PATH.read_text())
        available = [f for f in existing if f in df.columns]
        missing = [f for f in existing if f not in df.columns]
        if missing:
            logger.warning("  %d features from existing list missing in frame: %s", len(missing), missing[:5])
        logger.info("  Using existing feature list: %d/%d features available", len(available), len(existing))
        return available

    # Derive from engineered columns (exclude metadata + label columns)
    exclude = {
        "ticker", "date", "label", "_next_close", "_fwd_return",
        "sector", "exchange", "name",
    }
    numeric_cols = [
        col for col in df.select_dtypes(include=[np.number]).columns
        if col not in exclude and not col.startswith("_")
    ]
    logger.info("  Derived feature list from frame: %d numeric columns", len(numeric_cols))
    return sorted(numeric_cols)


def main() -> int:
    parser = argparse.ArgumentParser(description="Retrain XGBoost model on latest NGX price data.")
    parser.add_argument("--min-auc", type=float, default=0.55,
                        help="Minimum AUC-ROC required to save the new model (default: 0.55)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Train and validate but do not overwrite model artifacts")
    args = parser.parse_args()

    logger.info("=== NGX XGBoost Retraining  min-auc=%.2f  dry-run=%s ===", args.min_auc, args.dry_run)

    df = build_training_frame()
    df = select_window(df)
    feature_list = resolve_feature_list(df)

    metrics = train_validate(df, feature_list, min_auc=args.min_auc, dry_run=args.dry_run)

    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    logger.info("Metrics written to %s", METRICS_PATH)

    if not metrics["passed"]:
        logger.error("Retraining FAILED quality gate (AUC %.4f < %.2f). Previous model retained.",
                     metrics["auc_roc"], args.min_auc)
        return 1

    logger.info("=== Retraining complete. AUC-ROC: %.4f ===", metrics["auc_roc"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
