"""NGX XGBoost Retraining — Google Colab / Kaggle
Upload to Colab via: File → Upload notebook  (use NGX_XGBoost_Retrain.ipynb)
Or paste each cell block directly into a new Colab notebook.

After training, upload the downloaded artifacts to the backend repo:
  xgboost_model.pkl       → models/xgboost_model.pkl
  xgb_feature_list.json   → configs/xgb_feature_list.json
  xgb_metrics.json        → reports/xgb_metrics.json
"""

# ── Cell A: Install dependencies ──────────────────────────────────────────────
# %%
# Run this cell first, then restart the runtime if prompted
get_ipython().system("pip install -q xgboost scikit-learn pandas numpy pyarrow joblib google-cloud-bigquery db-dtypes")

# ── Cell B: Imports + Config ──────────────────────────────────────────────────
# %%
import os
import json
import subprocess
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from datetime import datetime, timezone

from sklearn.metrics import (
    roc_auc_score, classification_report,
    matthews_corrcoef, balanced_accuracy_score,
)
from xgboost import XGBClassifier

# ── BigQuery ──────────────────────────────────────────────────────────────────
BQ_PROJECT = "stock-market-pipeline-496521"
BQ_DATASET = "ngx_market_data"
BQ_TABLE   = "price"

# ── Training ──────────────────────────────────────────────────────────────────
WINDOW_DAYS      = 730    # rolling 2-year training window
HOLDOUT_DAYS     = 60     # validation holdout (chronological, no shuffle)
MIN_TICKER_ROWS  = 60     # skip tickers with fewer rows
UP_THRESHOLD     = 0.005  # next-day return > 0.5% = class 1 (UP)

# ── Quality gate (must match configs/backend_model_config.json) ───────────────
MIN_AUC    = 0.55
MIN_MCC    = 0.05
MIN_BALACC = 0.55

# ── XGBoost hyper-parameters ─────────────────────────────────────────────────
XGB_PARAMS = dict(
    n_estimators          = 1000,
    max_depth             = 5,
    learning_rate         = 0.05,
    subsample             = 0.8,
    colsample_bytree      = 0.8,
    min_child_weight      = 3,
    objective             = "binary:logistic",
    eval_metric           = "auc",
    random_state          = 42,
    n_jobs                = -1,
    early_stopping_rounds = 50,
)

# Auto-detect GPU
try:
    subprocess.run(["nvidia-smi"], check=True, capture_output=True)
    XGB_PARAMS["device"] = "cuda"
    print("GPU detected — training on CUDA")
except Exception:
    print("No GPU — training on CPU")
    print("Tip: Runtime → Change runtime type → T4 GPU (Colab) or enable GPU (Kaggle)")

OUTPUT_DIR = Path("artifacts")
OUTPUT_DIR.mkdir(exist_ok=True)
print("Config ready.")

# ── Cell C: Authenticate + Load from BigQuery ─────────────────────────────────
# %%
# ─── Colab: uncomment the two lines below ────────────────────────────────────
from google.colab import auth
auth.authenticate_user()

# ─── Kaggle: comment out the two lines above and uncomment this line ──────────
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/kaggle/input/YOUR-KEY-FOLDER/key.json"
# ─────────────────────────────────────────────────────────────────────────────

from google.cloud import bigquery

client = bigquery.Client(project=BQ_PROJECT)

query = f"""
SELECT
    date, ticker,
    pclose, high, low, close, volume, change
FROM `{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}`
WHERE close  IS NOT NULL
  AND close  > 0
  AND high   > 0
  AND low    > 0
ORDER BY ticker, date
"""
print("Querying BigQuery…")
df_raw = client.query(query).to_dataframe()
df_raw["date"] = pd.to_datetime(df_raw["date"])

print(f"Loaded {len(df_raw):,} rows | {df_raw['ticker'].nunique()} tickers")
print(f"Date range: {df_raw['date'].min().date()} → {df_raw['date'].max().date()}")
df_raw.head()

# ── Cell D: Clean data ────────────────────────────────────────────────────────
# %%
def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates(subset=["date", "ticker"])
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    # OHLC sanity
    df = df[
        (df["close"] > 0) &
        (df["high"]  >= df["low"]) &
        (df["high"]  >= df["close"]) &
        (df["low"]   <= df["close"])
    ]
    # Volume: impute missing with per-ticker median
    df["volume"] = (
        df.groupby("ticker")["volume"]
        .transform(lambda x: x.fillna(x.median()).clip(lower=0))
        .fillna(0)
    )
    # pclose: forward-fill then backward-fill within ticker
    df["pclose"] = df.groupby("ticker")["pclose"].transform(
        lambda x: x.ffill().bfill()
    )
    return df

df = clean_data(df_raw)
print(f"After cleaning: {len(df):,} rows  ({len(df_raw) - len(df):,} removed)")

# ── Cell E: Feature engineering helpers ───────────────────────────────────────
# %%
# These functions replicate app/services/feature_engineer.py exactly so the
# trained model is compatible with backend inference.

def _rsi(close: pd.Series, w: int = 14) -> pd.Series:
    d    = close.diff()
    gain = d.clip(lower=0).rolling(w, min_periods=max(2, w // 2)).mean()
    loss = (-d.clip(upper=0)).rolling(w, min_periods=max(2, w // 2)).mean()
    rs   = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(close: pd.Series):
    ema12  = close.ewm(span=12, adjust=False, min_periods=6).mean()
    ema26  = close.ewm(span=26, adjust=False, min_periods=13).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False, min_periods=4).mean()
    return macd, signal, macd - signal


def _bollinger(close: pd.Series, w: int = 20):
    mid   = close.rolling(w, min_periods=5).mean()
    std   = close.rolling(w, min_periods=5).std()
    upper = mid + 2 * std
    lower = mid - 2 * std
    width = (upper - lower) / mid.replace(0, np.nan)
    return mid, upper, lower, width


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, w: int = 14) -> pd.Series:
    pc = close.shift(1)
    tr = pd.concat([high - low, (high - pc).abs(), (low - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(w, min_periods=max(2, w // 2)).mean()


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    return (np.sign(close.diff()).fillna(0) * volume.fillna(0)).cumsum()


def engineer_ticker(g: pd.DataFrame) -> pd.DataFrame:
    g = g.copy().sort_values("date")
    c = g["close"].astype(float)
    h = g["high"].astype(float)
    l = g["low"].astype(float)
    v = g["volume"].astype(float)

    # Returns
    g["daily_return"] = c.pct_change()
    g["log_return"]   = np.log(c.replace(0, np.nan) / c.shift(1).replace(0, np.nan))
    for w in (3, 5, 10, 20):
        g[f"return_{w}d"] = c.pct_change(w)

    # Volatility
    g["volatility_20"] = g["daily_return"].rolling(20, min_periods=5).std() * np.sqrt(252)

    # Moving averages
    for w in (5, 10, 20, 50):
        g[f"ma_{w}"] = c.rolling(w, min_periods=max(2, w // 4)).mean()
    g["ma_20_gap_pct"] = ((c - g["ma_20"]) / g["ma_20"].replace(0, np.nan)) * 100
    g["ma_50_gap_pct"] = ((c - g["ma_50"]) / g["ma_50"].replace(0, np.nan)) * 100

    # Oscillators
    g["rsi_14"] = _rsi(c, 14)
    g["macd"], g["macd_signal"], g["macd_hist"] = _macd(c)
    g["bb_mid"], g["bb_upper"], g["bb_lower"], g["bb_width"] = _bollinger(c)
    g["atr_14"] = _atr(h, l, c, 14)
    g["obv"]    = _obv(c, v)

    # Volume
    avg_v20 = v.rolling(20, min_periods=5).mean()
    g["volume_ratio_20"] = v / avg_v20.replace(0, np.nan)
    g["volume_change"]   = v.pct_change()

    # Risk / price position
    rh52 = c.rolling(252, min_periods=20).max()
    g["drawdown_52w"]   = ((c / rh52.replace(0, np.nan)) - 1.0) * 100
    g["high_low_pct"]   = ((h - l) / c.replace(0, np.nan)) * 100
    g["close_position"] = (c - l) / (h - l).replace(0, np.nan)

    # Lags
    for lag in (1, 2):
        g[f"lag_close_{lag}"]  = c.shift(lag)
        g[f"lag_return_{lag}"] = g["daily_return"].shift(lag)
    g["lag_volume_1"] = v.shift(1)

    return g

print("Engineering features — this may take 1-2 minutes…")
frames = []
skipped = 0
for ticker, group in df.groupby("ticker"):
    if len(group) >= MIN_TICKER_ROWS:
        frames.append(engineer_ticker(group))
    else:
        skipped += 1

df_feat = pd.concat(frames, ignore_index=True)
df_feat = df_feat.replace([np.inf, -np.inf], np.nan)
print(f"Done: {len(df_feat):,} rows, {df_feat['ticker'].nunique()} tickers  ({skipped} skipped)")

# ── Cell F: Labels + chronological split ─────────────────────────────────────
# %%
# These 33 features EXACTLY match backend FALLBACK_FEATURE_COLUMNS.
# Do NOT reorder — the saved xgb_feature_list.json is the source of truth.
FEATURE_COLS = [
    "daily_return", "log_return",
    "return_3d", "return_5d", "return_10d", "return_20d",
    "volatility_20",
    "ma_5", "ma_10", "ma_20", "ma_50",
    "ma_20_gap_pct", "ma_50_gap_pct",
    "rsi_14", "macd", "macd_signal", "macd_hist",
    "bb_mid", "bb_upper", "bb_lower", "bb_width",
    "atr_14", "obv",
    "volume_ratio_20", "volume_change",
    "drawdown_52w", "high_low_pct", "close_position",
    "lag_close_1", "lag_close_2",
    "lag_return_1", "lag_return_2",
    "lag_volume_1",
]

# Next-day close > current close by >0.5% = UP (class 1)
df_feat = df_feat.sort_values(["ticker", "date"])
df_feat["_next_close"] = df_feat.groupby("ticker")["close"].shift(-1)
df_feat["_fwd_return"] = (
    (df_feat["_next_close"] - df_feat["close"]) /
    df_feat["close"].replace(0, np.nan)
)
df_feat["label"] = (df_feat["_fwd_return"] > UP_THRESHOLD).astype(int)

# Drop rows where we can't compute a valid label or key features
df_feat = df_feat.dropna(subset=["label", "daily_return", "rsi_14"])

# Rolling 2-year window
latest = df_feat["date"].max()
df_win = df_feat[df_feat["date"] >= latest - pd.Timedelta(days=WINDOW_DAYS)].copy()

# Chronological split — NEVER shuffle before splitting financial time series
holdout_start = df_win["date"].max() - pd.Timedelta(days=HOLDOUT_DAYS)
train_df = df_win[df_win["date"] <  holdout_start]
val_df   = df_win[df_win["date"] >= holdout_start]

X_train = train_df[FEATURE_COLS].fillna(0.0)
y_train = train_df["label"].astype(int)
X_val   = val_df[FEATURE_COLS].fillna(0.0)
y_val   = val_df["label"].astype(int)

print(f"Train: {len(X_train):,} rows | Val: {len(X_val):,} rows")
print(f"Label balance — Train UP: {y_train.mean()*100:.1f}% | Val UP: {y_val.mean()*100:.1f}%")

# ── Cell G: Train XGBoost ─────────────────────────────────────────────────────
# %%
n_down = int((y_train == 0).sum())
n_up   = int(max((y_train == 1).sum(), 1))
scale_pos_weight = max(1.0, n_down / n_up)

print(f"Class balance — DOWN: {n_down:,}  UP: {n_up:,}  ({100*n_up/(n_down+n_up):.1f}% UP)")
print(f"scale_pos_weight: {scale_pos_weight:.2f}")
print("\nTraining XGBoost…")

params = {**XGB_PARAMS, "scale_pos_weight": scale_pos_weight}
model  = XGBClassifier(**params)
model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=100)

print(f"\nBest iteration: {model.best_iteration}")

# ── Cell H: Evaluate ──────────────────────────────────────────────────────────
# %%
y_prob  = model.predict_proba(X_val)[:, 1]
y_pred  = (y_prob >= 0.5).astype(int)

auc     = float(roc_auc_score(y_val, y_prob))
mcc     = float(matthews_corrcoef(y_val, y_pred))
bal_acc = float(balanced_accuracy_score(y_val, y_pred))
passed  = (auc >= MIN_AUC) and (mcc >= MIN_MCC) and (bal_acc >= MIN_BALACC)

print(f"\n{'='*58}")
print(f"  ROC-AUC            {auc:.4f}   gate ≥ {MIN_AUC}   {'✓' if auc >= MIN_AUC else '✗'}")
print(f"  MCC                {mcc:.4f}   gate ≥ {MIN_MCC}   {'✓' if mcc >= MIN_MCC else '✗'}")
print(f"  Balanced Accuracy  {bal_acc:.4f}   gate ≥ {MIN_BALACC}   {'✓' if bal_acc >= MIN_BALACC else '✗'}")
print(f"{'='*58}")
print(f"  Quality gate: {'PASSED ✓' if passed else 'FAILED ✗'}")
print(f"{'='*58}")
print(f"\nPredicted UP%: {y_pred.mean()*100:.1f}%  (actual: {y_val.mean()*100:.1f}%)")

print("\nClassification Report:")
print(classification_report(y_val, y_pred, target_names=["DOWN", "UP"]))

# Feature importances
fi = pd.Series(model.feature_importances_, index=FEATURE_COLS).sort_values(ascending=False)
print("\nTop 15 features by importance:")
print(fi.head(15).to_string())

if not passed:
    print("\nTroubleshooting:")
    up_pct = y_train.mean() * 100
    if up_pct < 10:
        print(f"  ⚠ UP labels are only {up_pct:.1f}% of training set — data may be biased.")
        print("    Try lowering UP_THRESHOLD from 0.005 to 0.001 or 0.0.")
    print("  → Increase n_estimators to 2000")
    print("  → Try max_depth=6, learning_rate=0.03")
    print("  → Check for data quality issues (many zero-volume rows?)")

# ── Cell I: Save artifacts ────────────────────────────────────────────────────
# %%
if passed:
    joblib.dump(model, OUTPUT_DIR / "xgboost_model.pkl")

    with open(OUTPUT_DIR / "xgb_feature_list.json", "w") as f:
        json.dump(FEATURE_COLS, f, indent=2)

    metrics_out = {
        "auc_roc":           round(auc, 4),
        "mcc":               round(mcc, 4),
        "balanced_accuracy": round(bal_acc, 4),
        "train_rows":        len(X_train),
        "val_rows":          len(X_val),
        "best_iteration":    int(model.best_iteration),
        "n_features":        len(FEATURE_COLS),
        "features":          FEATURE_COLS,
        "scale_pos_weight":  round(scale_pos_weight, 4),
        "up_threshold":      UP_THRESHOLD,
        "generated_at":      datetime.now(timezone.utc).isoformat(),
    }
    with open(OUTPUT_DIR / "xgb_metrics.json", "w") as f:
        json.dump(metrics_out, f, indent=2)

    print("✓ Artifacts saved to artifacts/")
    print("  xgboost_model.pkl      → upload to  models/xgboost_model.pkl")
    print("  xgb_feature_list.json  → upload to  configs/xgb_feature_list.json")
    print("  xgb_metrics.json       → upload to  reports/xgb_metrics.json")
else:
    print("✗ Model NOT saved — quality gate failed. Fix issues above and re-run Cell G.")

# ── Cell J: Zip + Download ────────────────────────────────────────────────────
# %%
if passed:
    import shutil
    shutil.make_archive("ngx_xgboost_artifacts", "zip", OUTPUT_DIR)

    # Colab download
    from google.colab import files
    files.download("ngx_xgboost_artifacts.zip")

    # Kaggle: find the zip in the working directory
    print("Downloaded ngx_xgboost_artifacts.zip")
    print("\nNext steps:")
    print("  1. Extract the zip")
    print("  2. Copy artifacts to your backend repo:")
    print("       xgboost_model.pkl      → models/xgboost_model.pkl")
    print("       xgb_feature_list.json  → configs/xgb_feature_list.json")
    print("       xgb_metrics.json       → reports/xgb_metrics.json")
    print("  3. git add + commit + push")
    print("  4. Redeploy the backend on Render")
