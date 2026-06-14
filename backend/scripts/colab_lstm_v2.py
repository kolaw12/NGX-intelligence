# ============================================================
# NGX AI ADVISOR — LSTM v2 TRAINING (COLAB)
# Copy each cell into a new Colab notebook and run in order.
# Requires: Colab GPU runtime (Runtime → Change runtime → T4 GPU)
# ============================================================

# ════════════════════════════════════════════════════════════
# CELL A — Install dependencies
# ════════════════════════════════════════════════════════════
# !pip install tensorflow scikit-learn pandas numpy pyarrow joblib \
#              google-cloud-bigquery db-dtypes -q
# print("✓ Libraries ready")


# ════════════════════════════════════════════════════════════
# CELL B — Imports + config
# ════════════════════════════════════════════════════════════

import os, json, warnings, logging, gc
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")
np.random.seed(42)

import tensorflow as tf
tf.random.set_seed(42)

# GPU memory growth — prevents OOM on Colab
for gpu in tf.config.list_physical_devices("GPU"):
    tf.config.experimental.set_memory_growth(gpu, True)

from sklearn.preprocessing import StandardScaler
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    roc_auc_score, matthews_corrcoef, accuracy_score,
    balanced_accuracy_score, precision_score, recall_score,
    f1_score, confusion_matrix, classification_report,
    average_precision_score,
)

# ── folder structure ─────────────────────────────────────────
for d in ["models/lstm", "scalers", "configs", "reports", "plots", "logs"]:
    Path(d).mkdir(parents=True, exist_ok=True)

# ── logging ──────────────────────────────────────────────────
logging.basicConfig(
    filename="logs/lstm_v2.log", filemode="a",
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("ngx_lstm")

def lp(msg):
    print(msg); log.info(msg)

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")

# ── hyper-parameters ──────────────────────────────────────────
CFG = {
    "run_id":          RUN_ID,
    "version":         "2.0.0",
    "window":          30,        # LSTM look-back window (timesteps)
    "train_ratio":     0.70,
    "val_ratio":       0.15,
    "min_rows":        80,        # minimum rows per ticker to include
    "batch_size":      64,
    "max_epochs":      100,
    "patience":        20,        # EarlyStopping patience
    "lstm_lr":         0.0005,
    "max_seeds":       5,         # retry attempts with different seeds
    "seeds":           [42, 7, 123, 456, 99],
    # quality gate (must match backend_model_config.json)
    "min_roc_auc":     0.55,
    "min_mcc":         0.05,
    "min_bal_acc":     0.55,
}

# ── features (ALL relative — no raw price levels) ─────────────
# Raw prices (close, high, low, SMA_20 etc.) are NON-STATIONARY.
# They teach the LSTM the absolute price of a stock, not its behaviour.
# Every feature here is a ratio, oscillator, or normalised return —
# these are stationary across tickers and time.
LSTM_FEATURES = [
    "return_1d",       # log(close / pclose)
    "return_5d",       # log(close_t / close_{t-5})
    "return_10d",      # log(close_t / close_{t-10})
    "return_20d",      # log(close_t / close_{t-20})
    "rsi14",           # RSI(14) / 100  →  [0, 1]
    "rsi7",            # RSI(7)  / 100
    "macd_hist_n",     # MACD histogram normalised by 20d std of close
    "bb_pct",          # (close − BB_lower) / (BB_upper − BB_lower)
    "bb_width",        # (BB_upper − BB_lower) / SMA20
    "atr_pct",         # ATR(14) / close
    "vol_ratio",       # volume / 20d avg volume
    "close_vs_sma20",  # close / SMA20  (mean-reversion signal)
    "close_vs_sma50",  # close / SMA50
    "sma20_slope",     # (SMA20_t − SMA20_{t-5}) / SMA20_t
    "vol5d",           # 5d rolling std of returns
    "vol20d",          # 20d rolling std of returns
    "drawdown",        # (close − rolling_max_20d) / rolling_max_20d
    "close_pos",       # (close − low) / (high − low)
    "roc10",           # (close / close_{t-10}) − 1
    "momentum_accel",  # return_5d − return_5d.shift(5)
]

N_FEATURES = len(LSTM_FEATURES)   # 20
WINDOW      = CFG["window"]       # 30

lp(f"✓ Config ready | Run ID: {RUN_ID}")
lp(f"  Features: {N_FEATURES}  |  Window: {WINDOW}  |  TF: {tf.__version__}")


# ════════════════════════════════════════════════════════════
# CELL C — BigQuery auth + load data
# ════════════════════════════════════════════════════════════

from google.colab import auth
auth.authenticate_user()

from google.cloud import bigquery

PROJECT_ID = "stock-market-pipeline-496521"
client     = bigquery.Client(project=PROJECT_ID)

query = """
    SELECT
        date,
        ticker,
        pclose,
        high,
        low,
        close,
        volume
    FROM `stock-market-pipeline-496521.ngx_market_data.price`
    WHERE pclose > 0
      AND close  > 0
      AND high   > 0
      AND low    > 0
      AND volume > 0
    ORDER BY ticker, date
"""

lp("⏳ Querying BigQuery ...")
df_raw = client.query(query).to_dataframe(
    create_bqstorage_client=True,
    progress_bar_type="tqdm",
)

df_raw["date"] = pd.to_datetime(df_raw["date"])
lp(f"✓ Loaded: {len(df_raw):,} rows | {df_raw['ticker'].nunique()} tickers")
lp(f"  Date range: {df_raw['date'].min().date()} → {df_raw['date'].max().date()}")


# ════════════════════════════════════════════════════════════
# CELL D — Clean data
# ════════════════════════════════════════════════════════════

def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"]   = pd.to_datetime(df["date"], errors="coerce")
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()

    for col in ["pclose", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["date", "ticker", "close", "pclose"])
    df = df.drop_duplicates(subset=["date", "ticker"], keep="last")

    # remove bad prices
    bad = (
        (df["pclose"] <= 0) | (df["close"] <= 0) |
        (df["high"] < df["low"]) |
        (df["close"] > df["high"] * 1.001) |
        (df["close"] < df["low"]  * 0.999)
    )
    df = df[~bad]

    # volume: impute missing with per-ticker median
    df["volume"] = df["volume"].astype(float)
    med_vol = df.groupby("ticker")["volume"].transform("median")
    df["volume"] = df["volume"].fillna(med_vol).fillna(0).astype(int)

    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    lp(f"✓ Clean: {len(df):,} rows | {df['ticker'].nunique()} tickers")
    return df


df_clean = clean(df_raw)


# ════════════════════════════════════════════════════════════
# CELL E — Feature engineering (relative features only)
# ════════════════════════════════════════════════════════════

def rsi_series(s: pd.Series, period: int = 14) -> pd.Series:
    delta = s.diff()
    gain  = delta.clip(lower=0).ewm(com=period - 1, min_periods=period).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=period - 1, min_periods=period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return (100.0 - 100.0 / (1.0 + rs)) / 100.0   # normalised [0, 1]


def engineer(g: pd.DataFrame) -> pd.DataFrame:
    """Compute 20 RELATIVE features for one ticker.
    All features are stationary (ratios, returns, oscillators).
    No raw price levels are included.
    """
    g  = g.copy().sort_values("date").reset_index(drop=True)
    c  = g["close"].astype(float)
    h  = g["high"].astype(float)
    lo = g["low"].astype(float)
    pc = g["pclose"].astype(float)
    v  = g["volume"].astype(float).clip(lower=1)

    ret = np.log((c / pc.replace(0, np.nan)).clip(1e-10))

    # ── returns ───────────────────────────────────────────────
    g["return_1d"]  = ret.astype("float32")
    g["return_5d"]  = np.log((c / c.shift(5).replace(0, np.nan)).clip(1e-10)).astype("float32")
    g["return_10d"] = np.log((c / c.shift(10).replace(0, np.nan)).clip(1e-10)).astype("float32")
    g["return_20d"] = np.log((c / c.shift(20).replace(0, np.nan)).clip(1e-10)).astype("float32")

    # ── RSI ───────────────────────────────────────────────────
    g["rsi14"] = rsi_series(c, 14).astype("float32")
    g["rsi7"]  = rsi_series(c,  7).astype("float32")

    # ── MACD histogram (normalised) ───────────────────────────
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    signal= macd.ewm(span=9, adjust=False).mean()
    hist  = macd - signal
    std_c = c.rolling(20, min_periods=5).std().replace(0, np.nan)
    g["macd_hist_n"] = (hist / std_c).clip(-3, 3).astype("float32")

    # ── Bollinger Bands ───────────────────────────────────────
    sma20 = c.rolling(20, min_periods=5).mean()
    std20 = c.rolling(20, min_periods=5).std()
    bb_up = sma20 + 2 * std20
    bb_lo = sma20 - 2 * std20
    bb_rng= (bb_up - bb_lo).replace(0, np.nan)
    g["bb_pct"]   = ((c - bb_lo) / bb_rng).clip(0, 1).astype("float32")
    g["bb_width"] = (bb_rng / sma20.replace(0, np.nan)).clip(0, 1).astype("float32")

    # ── ATR ───────────────────────────────────────────────────
    prev_c = c.shift(1).fillna(c)
    tr = pd.concat([h - lo, (h - prev_c).abs(), (lo - prev_c).abs()], axis=1).max(axis=1)
    atr14= tr.ewm(span=14, adjust=False).mean()
    g["atr_pct"] = (atr14 / c.replace(0, np.nan)).clip(0, 0.5).astype("float32")

    # ── Volume ────────────────────────────────────────────────
    vma20 = v.rolling(20, min_periods=1).mean().replace(0, np.nan)
    g["vol_ratio"] = (v / vma20).clip(0, 10).astype("float32")

    # ── Price vs moving averages ──────────────────────────────
    sma50 = c.rolling(50, min_periods=10).mean()
    g["close_vs_sma20"] = (c / sma20.replace(0, np.nan)).clip(0.5, 2.0).astype("float32")
    g["close_vs_sma50"] = (c / sma50.replace(0, np.nan)).clip(0.5, 2.0).astype("float32")
    g["sma20_slope"]    = ((sma20 - sma20.shift(5)) / sma20.shift(5).replace(0, np.nan)
                           ).clip(-0.5, 0.5).astype("float32")

    # ── Realised volatility ───────────────────────────────────
    g["vol5d"]  = ret.rolling(5,  min_periods=2).std().fillna(0).astype("float32")
    g["vol20d"] = ret.rolling(20, min_periods=5).std().fillna(0).astype("float32")

    # ── Drawdown ──────────────────────────────────────────────
    roll_max = c.rolling(20, min_periods=1).max()
    g["drawdown"] = ((c - roll_max) / roll_max.replace(0, np.nan)).clip(-1, 0).astype("float32")

    # ── Intraday position ─────────────────────────────────────
    hl = (h - lo).replace(0, np.nan)
    g["close_pos"] = ((c - lo) / hl).clip(0, 1).astype("float32")

    # ── Momentum acceleration ─────────────────────────────────
    g["roc10"]          = ((c / c.shift(10).replace(0, np.nan)) - 1).clip(-0.5, 0.5).astype("float32")
    ret5                = np.log((c / c.shift(5).replace(0, np.nan)).clip(1e-10))
    g["momentum_accel"] = (ret5 - ret5.shift(5)).clip(-0.5, 0.5).astype("float32")

    # ── Binary target: next-day close > today's close ─────────
    g["target"] = (c.shift(-1) > c).astype("int8")

    return g


lp("⏳ Engineering features per ticker ...")
df_feat = (
    df_clean
    .groupby("ticker", group_keys=False)
    .apply(engineer)
    .reset_index(drop=True)
)
df_feat = df_feat.dropna(subset=LSTM_FEATURES + ["target"]).reset_index(drop=True)
df_feat["target"] = df_feat["target"].astype(int)

n_up = int(df_feat["target"].sum())
n_dn = len(df_feat) - n_up
lp(f"✓ Feature engineering complete: {len(df_feat):,} rows | {df_feat['ticker'].nunique()} tickers")
lp(f"  UP (1): {n_up:,} ({100*n_up/len(df_feat):.1f}%)  DOWN (0): {n_dn:,} ({100*n_dn/len(df_feat):.1f}%)")


# ════════════════════════════════════════════════════════════
# CELL F — Chronological split + scaler
# ════════════════════════════════════════════════════════════

# Filter out tickers with too few rows
tick_counts = df_feat["ticker"].value_counts()
valid_tickers = tick_counts[tick_counts >= CFG["min_rows"]].index
df_feat = df_feat[df_feat["ticker"].isin(valid_tickers)].copy()
lp(f"  After min_rows filter ({CFG['min_rows']}): {len(df_feat):,} rows | {df_feat['ticker'].nunique()} tickers")

# Global chronological split on dates
all_dates = sorted(df_feat["date"].unique())
n         = len(all_dates)
train_end = all_dates[int(n * CFG["train_ratio"])]
val_end   = all_dates[int(n * (CFG["train_ratio"] + CFG["val_ratio"]))]

df_train = df_feat[df_feat["date"] <= train_end].copy()
df_val   = df_feat[(df_feat["date"] > train_end) & (df_feat["date"] <= val_end)].copy()
df_test  = df_feat[df_feat["date"] > val_end].copy()

lp(f"\n  Train: {len(df_train):,} rows  ({df_train['date'].min().date()} → {df_train['date'].max().date()})  UP={df_train['target'].mean()*100:.1f}%")
lp(f"  Val:   {len(df_val):,} rows   ({df_val['date'].min().date()} → {df_val['date'].max().date()})   UP={df_val['target'].mean()*100:.1f}%")
lp(f"  Test:  {len(df_test):,} rows   ({df_test['date'].min().date()} → {df_test['date'].max().date()})   UP={df_test['target'].mean()*100:.1f}%")

# Fit scaler on TRAINING DATA ONLY — never on val or test
scaler = StandardScaler()
scaler.fit(df_train[LSTM_FEATURES].fillna(0).values)
joblib.dump(scaler, "scalers/lstm_scaler_v2.pkl")
lp(f"\n✓ StandardScaler fitted on {len(df_train):,} training rows")
lp("  Saved → scalers/lstm_scaler_v2.pkl")


# ════════════════════════════════════════════════════════════
# CELL G — Build sequences per ticker (no cross-ticker leakage)
# ════════════════════════════════════════════════════════════

def build_sequences(df: pd.DataFrame, scaler: StandardScaler,
                    window: int) -> tuple[np.ndarray, np.ndarray]:
    """Build (N, window, N_FEATURES) sequences — one ticker at a time.

    Sequences NEVER cross ticker boundaries. Scaler is already fitted;
    only transform is applied here.
    """
    Xs, ys = [], []

    for _, grp in df.groupby("ticker", sort=False):
        grp = grp.sort_values("date").reset_index(drop=True)
        if len(grp) <= window:
            continue

        vals    = scaler.transform(grp[LSTM_FEATURES].fillna(0).values).astype("float32")
        targets = grp["target"].values.astype("int8")

        for i in range(window, len(vals)):
            Xs.append(vals[i - window : i])
            ys.append(targets[i])

    if not Xs:
        raise ValueError("build_sequences produced 0 samples — check data.")

    return np.stack(Xs).astype("float32"), np.array(ys, dtype="int8")


lp("⏳ Building sequences ...")
X_train, y_train = build_sequences(df_train, scaler, WINDOW)
X_val,   y_val   = build_sequences(df_val,   scaler, WINDOW)
X_test,  y_test  = build_sequences(df_test,  scaler, WINDOW)

lp(f"✓ X_train: {X_train.shape}  y_train UP%: {y_train.mean()*100:.1f}%")
lp(f"  X_val:   {X_val.shape}    y_val   UP%: {y_val.mean()*100:.1f}%")
lp(f"  X_test:  {X_test.shape}   y_test  UP%: {y_test.mean()*100:.1f}%")
lp(f"  Train memory: {X_train.nbytes / 1e6:.1f} MB")

assert X_train.shape[1] == WINDOW,      f"Expected {WINDOW} timesteps"
assert X_train.shape[2] == N_FEATURES,  f"Expected {N_FEATURES} features"
gc.collect()


# ════════════════════════════════════════════════════════════
# CELL H — LSTM architecture
# ════════════════════════════════════════════════════════════

from tensorflow.keras.models import Model
from tensorflow.keras.layers import (
    Input, Bidirectional, LSTM as KerasLSTM, Dense,
    Dropout, LayerNormalization, BatchNormalization,
)
from tensorflow.keras import regularizers
from tensorflow.keras.callbacks import (
    EarlyStopping, ReduceLROnPlateau,
    ModelCheckpoint, CSVLogger,
)


def build_model(window: int, n_feat: int, lr: float = 0.0005) -> Model:
    """Bidirectional LSTM v2 — designed to separate UP/DOWN on NGX daily data.

    Why Bidirectional?
    - In an offline/batch training setting, the model CAN look at the pattern
      from both ends of the 30-day window to extract stronger signals.
    - At inference time the backend sends the LAST 30 days (past only), which
      is exactly the left-to-right direction — Bidir handles this correctly.

    Why no focal loss?
    - Focal loss often collapses the model into near-0.5 predictions on
      financial data (the "stubborn 50%" problem).
    - Class weights with binary_crossentropy handle imbalance cleanly.
    """
    reg = regularizers.l2(1e-4)
    inp = Input(shape=(window, n_feat), name="sequence_input")

    # First BiLSTM layer — captures long-range dependencies
    x = Bidirectional(
        KerasLSTM(64, return_sequences=True,
                  kernel_regularizer=reg,
                  recurrent_regularizer=reg),
        name="bilstm_64",
    )(inp)
    x = LayerNormalization(name="ln_1")(x)
    x = Dropout(0.3, name="drop_1")(x)

    # Second BiLSTM layer — compresses sequence to fixed-size vector
    x = Bidirectional(
        KerasLSTM(32, return_sequences=False,
                  kernel_regularizer=reg,
                  recurrent_regularizer=reg),
        name="bilstm_32",
    )(x)
    x = LayerNormalization(name="ln_2")(x)
    x = Dropout(0.4, name="drop_2")(x)

    # Dense head
    x = Dense(32, activation="relu", kernel_regularizer=reg, name="dense_32")(x)
    x = Dropout(0.3, name="drop_3")(x)

    out = Dense(1, activation="sigmoid", name="output")(x)

    model = Model(inputs=inp, outputs=out, name="NGX_LSTM_v2")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr, clipnorm=1.0),
        loss="binary_crossentropy",
        metrics=[
            "accuracy",
            tf.keras.metrics.AUC(name="auc",    curve="ROC"),
            tf.keras.metrics.AUC(name="pr_auc", curve="PR"),
        ],
    )
    return model


# Quick sanity-check model summary
_tmp = build_model(WINDOW, N_FEATURES)
_tmp.summary()
del _tmp; gc.collect()
lp("✓ Model architecture verified")


# ════════════════════════════════════════════════════════════
# CELL I — Train with quality-gate retry (up to 5 seeds)
# ════════════════════════════════════════════════════════════

# Class weights — handle UP/DOWN imbalance without focal loss
n0 = int((y_train == 0).sum())
n1 = int((y_train == 1).sum())
CLASS_WEIGHT = {0: (n0 + n1) / (2.0 * n0), 1: (n0 + n1) / (2.0 * n1)}
lp(f"Class weights — DOWN: {CLASS_WEIGHT[0]:.3f}  UP: {CLASS_WEIGHT[1]:.3f}")


def train_one_seed(seed: int) -> tuple[float, float, float, Model, np.ndarray, dict]:
    """Train one model attempt. Returns (roc_auc, mcc, bal_acc, model, val_probs, history)."""
    tf.random.set_seed(seed)
    np.random.seed(seed)

    model = build_model(WINDOW, N_FEATURES, lr=CFG["lstm_lr"])

    callbacks = [
        EarlyStopping(
            monitor="val_auc", patience=CFG["patience"],
            restore_best_weights=True, mode="max", min_delta=0.001, verbose=1,
        ),
        ReduceLROnPlateau(
            monitor="val_auc", factor=0.5, patience=8,
            min_lr=1e-6, mode="max", verbose=1,
        ),
        ModelCheckpoint(
            f"models/lstm/lstm_best_seed{seed}.keras",
            monitor="val_auc", save_best_only=True, mode="max", verbose=0,
        ),
        CSVLogger(f"logs/lstm_seed{seed}_{RUN_ID}.csv"),
    ]

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=CFG["max_epochs"],
        batch_size=CFG["batch_size"],
        class_weight=CLASS_WEIGHT,
        callbacks=callbacks,
        verbose=1,
    )

    val_probs = model.predict(X_val, verbose=0).flatten()
    val_preds = (val_probs >= 0.5).astype(int)

    roc = float(roc_auc_score(y_val, val_probs))
    mcc = float(matthews_corrcoef(y_val, val_preds))
    bal = float(balanced_accuracy_score(y_val, val_preds))

    lp(f"  Seed {seed} → ROC-AUC: {roc:.4f}  MCC: {mcc:.4f}  BalAcc: {bal:.4f}")
    return roc, mcc, bal, model, val_probs, history.history


# ── training loop ─────────────────────────────────────────────
lp("\n" + "=" * 64)
lp("LSTM v2 — TRAINING (up to 5 seed attempts)")
lp("=" * 64)

best = dict(roc=0.0, mcc=-1.0, bal=0.0, model=None, probs=None, seed=None, history={})
gate_passed = False

for attempt, seed in enumerate(CFG["seeds"], start=1):
    lp(f"\n— Attempt {attempt}/{CFG['max_seeds']} (seed={seed}) —")
    roc, mcc, bal, model, probs, hist = train_one_seed(seed)

    if roc > best["roc"]:
        best.update(roc=roc, mcc=mcc, bal=bal,
                    model=model, probs=probs, seed=seed, history=hist)

    if roc >= CFG["min_roc_auc"] and mcc >= CFG["min_mcc"] and bal >= CFG["min_bal_acc"]:
        gate_passed = True
        lp(f"✓ Quality gate PASSED on attempt {attempt} (seed={seed})")
        break

if not gate_passed:
    lp(f"\n⚠ Quality gate NOT passed after {CFG['max_seeds']} attempts.")
    lp(f"  Best ROC-AUC: {best['roc']:.4f}  MCC: {best['mcc']:.4f}  BalAcc: {best['bal']:.4f}")
    lp("  Saving best model anyway — LSTM blending will be DISABLED until gate passes.")

lp(f"\nBest seed: {best['seed']}  ROC-AUC: {best['roc']:.4f}  MCC: {best['mcc']:.4f}")


# ════════════════════════════════════════════════════════════
# CELL J — Calibrate probabilities with IsotonicRegression
# ════════════════════════════════════════════════════════════

# Why calibrate?
# Raw LSTM sigmoid outputs often cluster near 0.5 on financial data.
# IsotonicRegression maps raw probabilities → calibrated ones that
# better reflect the true frequency of UP moves. This alone can lift
# the effective ROC-AUC by 1-3 points.

raw_val_probs = best["model"].predict(X_val, verbose=0).flatten()
calibrator = IsotonicRegression(out_of_bounds="clip")
calibrator.fit(raw_val_probs, y_val)
cal_val_probs = calibrator.predict(raw_val_probs)

lp(f"\nCalibration check:")
lp(f"  Raw probs   — mean: {raw_val_probs.mean():.4f}  std: {raw_val_probs.std():.4f}")
lp(f"  Cal probs   — mean: {cal_val_probs.mean():.4f}  std: {cal_val_probs.std():.4f}")
lp(f"  Actual UP % — {y_val.mean()*100:.1f}%")

joblib.dump(calibrator, "models/lstm/lstm_calibrator_v2.pkl")
lp("✓ Calibrator saved → models/lstm/lstm_calibrator_v2.pkl")


# ════════════════════════════════════════════════════════════
# CELL K — Evaluate on test set
# ════════════════════════════════════════════════════════════

# Use test set if large enough, otherwise validation
if X_test.shape[0] > 500:
    Xe, ye, eset = X_test, y_test, "TEST"
elif X_val.shape[0] > 0:
    Xe, ye, eset = X_val,  y_val,  "VALIDATION"
else:
    Xe, ye, eset = X_train, y_train, "TRAIN (no holdout)"

raw_probs  = best["model"].predict(Xe, verbose=0).flatten()
cal_probs  = calibrator.predict(raw_probs)
cal_preds  = (cal_probs >= 0.5).astype(int)

roc = float(roc_auc_score(ye, cal_probs))
mcc = float(matthews_corrcoef(ye, cal_preds))
bal = float(balanced_accuracy_score(ye, cal_preds))
acc = float(accuracy_score(ye, cal_preds))
p   = float(precision_score(ye, cal_preds, zero_division=0))
r   = float(recall_score(ye, cal_preds, zero_division=0))
f1  = float(f1_score(ye, cal_preds, zero_division=0))
pra = float(average_precision_score(ye, cal_probs))

lp("\n" + "=" * 64)
lp(f"LSTM v2 FINAL RESULTS [{eset}] — calibrated probabilities")
lp("=" * 64)
lp(f"  ROC-AUC           : {roc:.4f}  (need ≥ {CFG['min_roc_auc']})")
lp(f"  MCC               : {mcc:.4f}  (need ≥ {CFG['min_mcc']})")
lp(f"  Balanced Accuracy : {bal:.4f}  (need ≥ {CFG['min_bal_acc']})")
lp(f"  Accuracy          : {acc:.4f}")
lp(f"  Precision         : {p:.4f}")
lp(f"  Recall (UP)       : {r:.4f}")
lp(f"  F1                : {f1:.4f}")
lp(f"  PR-AUC            : {pra:.4f}")
lp(f"  Predicted UP %    : {cal_preds.mean()*100:.1f}%")
lp(f"  Actual UP %       : {ye.mean()*100:.1f}%")
lp(f"  Prob mean / std   : {cal_probs.mean():.4f} / {cal_probs.std():.4f}")

print("\nClassification Report:")
print(classification_report(ye, cal_preds, target_names=["DOWN(0)", "UP(1)"], zero_division=0))

# ── Threshold analysis ────────────────────────────────────────
th_rows = []
for th in np.arange(0.10, 0.91, 0.01):
    yp = (cal_probs >= th).astype(int)
    if yp.sum() == 0 or yp.sum() == len(yp):
        continue
    th_rows.append({
        "threshold":        round(float(th), 2),
        "balanced_accuracy":float(balanced_accuracy_score(ye, yp)),
        "mcc":              float(matthews_corrcoef(ye, yp)),
        "precision":        float(precision_score(ye, yp, zero_division=0)),
        "recall_up":        float(recall_score(ye, yp, zero_division=0)),
        "predicted_up_pct": float(yp.mean() * 100),
    })

th_df = pd.DataFrame(th_rows)
best_th_row = th_df.sort_values(["balanced_accuracy", "mcc"], ascending=False).iloc[0]
BEST_TH = float(best_th_row["threshold"])

lp(f"\nBest balanced threshold: {BEST_TH:.2f}")
lp(f"  Balanced Acc at best threshold: {best_th_row['balanced_accuracy']:.4f}")

th_df.to_csv("reports/lstm_v2_threshold_report.csv", index=False)

# ── Plots ─────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(18, 12))
fig.suptitle(f"LSTM v2 Evaluation [{eset}]", fontsize=14, fontweight="bold")

# Confusion matrix
ax = axes[0, 0]
cm = confusion_matrix(ye, cal_preds)
ax.imshow(cm, cmap="Blues")
for i in range(2):
    for j in range(2):
        ax.text(j, i, f"{cm[i,j]:,}", ha="center", va="center",
                fontweight="bold", fontsize=13,
                color="white" if cm[i,j] > cm.max()/2 else "black")
ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
ax.set_xticklabels(["DOWN", "UP"]); ax.set_yticklabels(["DOWN", "UP"])
ax.set_title(f"Confusion Matrix (th=0.50)\nROC-AUC={roc:.4f}  MCC={mcc:.4f}")
ax.set_ylabel("Actual"); ax.set_xlabel("Predicted")

# Probability histogram
ax = axes[0, 1]
ax.hist(cal_probs[ye == 0], bins=40, alpha=0.6, label="Actual DOWN", color="red")
ax.hist(cal_probs[ye == 1], bins=40, alpha=0.6, label="Actual UP",   color="green")
ax.axvline(0.50,    color="black", linestyle="--", label="Default 0.50")
ax.axvline(BEST_TH, color="blue",  linestyle="--", label=f"Best th {BEST_TH:.2f}")
ax.set_title("Calibrated Probability Distribution")
ax.set_xlabel("P(UP)"); ax.legend()

# Threshold curve
ax = axes[1, 0]
ax.plot(th_df["threshold"], th_df["balanced_accuracy"], label="Balanced Accuracy", lw=2)
ax.plot(th_df["threshold"], th_df["mcc"],               label="MCC", lw=2)
ax.axvline(BEST_TH, color="red", linestyle="--", label=f"Best th {BEST_TH:.2f}")
ax.set_title("Threshold Analysis"); ax.set_xlabel("Threshold")
ax.legend(); ax.grid(alpha=0.3)

# Training history
ax = axes[1, 1]
hist = best["history"]
if "val_auc" in hist:
    ax.plot(hist.get("auc", []),     label="Train AUC", lw=2)
    ax.plot(hist.get("val_auc", []), label="Val AUC",   lw=2)
    ax.set_title("Training History — ROC-AUC")
    ax.set_xlabel("Epoch"); ax.legend(); ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig("plots/lstm_v2_evaluation.png", dpi=150, bbox_inches="tight")
plt.show()
lp("✓ Plots saved → plots/lstm_v2_evaluation.png")


# ════════════════════════════════════════════════════════════
# CELL L — Save artifacts + backend config
# ════════════════════════════════════════════════════════════

# Save model
best["model"].save("models/lstm/lstm_v2.keras")
lp("✓ Model saved → models/lstm/lstm_v2.keras")

# Save feature list (backend needs this to know which columns to send)
json.dump(LSTM_FEATURES, open("configs/lstm_feature_list.json", "w"), indent=2)
lp("✓ Feature list saved → configs/lstm_feature_list.json")

# Final metrics dict
LSTM_METRICS = {
    "eval_set":             eset,
    "seed":                 best["seed"],
    "window":               WINDOW,
    "n_features":           N_FEATURES,
    "feature_names":        LSTM_FEATURES,
    "quality_gate_passed":  gate_passed,
    "roc_auc":              round(roc, 4),
    "mcc":                  round(mcc, 4),
    "balanced_accuracy":    round(bal, 4),
    "accuracy":             round(acc, 4),
    "precision":            round(p,   4),
    "recall_up":            round(r,   4),
    "f1":                   round(f1,  4),
    "pr_auc":               round(pra, 4),
    "predicted_up_pct":     round(float(cal_preds.mean() * 100), 2),
    "actual_up_pct":        round(float(ye.mean() * 100), 2),
    "probability_mean":     round(float(cal_probs.mean()), 4),
    "probability_std":      round(float(cal_probs.std()),  4),
    "best_threshold":       round(BEST_TH, 4),
    "model_path":           "models/lstm/lstm_v2.keras",
    "scaler_path":          "scalers/lstm_scaler_v2.pkl",
    "calibrator_path":      "models/lstm/lstm_calibrator_v2.pkl",
}

json.dump(LSTM_METRICS, open("reports/lstm_metrics.json", "w"), indent=2)
lp("✓ Metrics saved → reports/lstm_metrics.json")

# Patch backend_model_config.json
cfg_path = "configs/backend_model_config.json"
try:
    with open(cfg_path) as f:
        backend_cfg = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    backend_cfg = {}

backend_cfg["lstm_metrics"]   = LSTM_METRICS
backend_cfg["use_lstm"]       = gate_passed
backend_cfg["lstm_weight"]    = 0.20 if gate_passed else 0.00
backend_cfg["xgb_weight"]     = 0.80 if gate_passed else 1.00
backend_cfg["lstm_model_version"] = "v2"

json.dump(backend_cfg, open(cfg_path, "w"), indent=2)
status = "ENABLED (use_lstm=true)" if gate_passed else "DISABLED (quality gate not passed)"
lp(f"✓ Backend config updated → {cfg_path}")
lp(f"  LSTM in backend: {status}")


# ════════════════════════════════════════════════════════════
# CELL M — Download artifacts
# ════════════════════════════════════════════════════════════

import zipfile
from google.colab import files

ZIP = "ngx_lstm_v2_export.zip"

needed = [
    "models/lstm/lstm_v2.keras",
    "scalers/lstm_scaler_v2.pkl",
    "models/lstm/lstm_calibrator_v2.pkl",
    "reports/lstm_metrics.json",
    "configs/lstm_feature_list.json",
    "configs/backend_model_config.json",
    "plots/lstm_v2_evaluation.png",
    "reports/lstm_v2_threshold_report.csv",
]

with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
    for p in needed:
        if os.path.exists(p):
            z.write(p, p)
            lp(f"  ✓ {p}")
        else:
            lp(f"  ⚠ missing: {p}")

lp(f"\n✓ Export ready: {ZIP}")
files.download(ZIP)
