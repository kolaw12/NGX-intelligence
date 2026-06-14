"""
Fetcher for macro market data from Yahoo Finance (via the `yfinance` library).

Currently pulls:
  - Brent crude oil futures (ticker BZ=F)

Future additions follow the same pattern:
  - WTI crude oil (CL=F)
  - Gold (GC=F)
  - US 10-year Treasury yield (^TNX)
  - Dollar index (DX-Y.NYB)

Output schema (long-format, matches HANDOFF.md section 11):
    date         datetime64
    indicator    str           e.g. "brent_oil_usd"
    value        float64       Close price (USD per unit, depends on instrument)
    source       str           "yahoo"
    unit         str           e.g. "USD/barrel"

Usage:
    from data.fetchers.yfinance import YFinanceFetcher
    fetcher = YFinanceFetcher()
    df = fetcher.fetch_brent_oil()
    fetcher.save(df)

Note on imports:
    This module is named `yfinance` to mirror the data source. Internally
    it imports the installed `yfinance` package via absolute import — Python 3
    resolves this correctly (the local module is `data.fetchers.yfinance`,
    not `yfinance`).
"""
from pathlib import Path

import pandas as pd
# pyrefly: ignore [missing-import]
from loguru import logger

# The installed yfinance package — absolute import, NOT this module
import yfinance as _yf

from data.config import (
    LOG_DIR,
    DATA_DIR,
)

MACRO_PROCESSED_DIR = f"{DATA_DIR}/output/processed/macro"

Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
logger.add(
    f"{LOG_DIR}/yahoo.log",
    rotation="1 MB",
    level="INFO",
)


# ---------- the fetcher ----------

class YFinanceFetcher:
    """
    Wraps yfinance.download() and emits long-format DataFrames matching
    the macro_indicators schema.

    yfinance handles its own HTTP, retries, and rate limiting internally,
    so we don't need the polite_get / killswitch scaffolding here. The
    Yahoo Finance API is meant to be hit programmatically.
    """

    SOURCE_ID = "yahoo"

    def __init__(self):
        # yfinance is configured globally; nothing to instantiate per-fetcher
        pass

    # ---------- specific instruments ----------

    def fetch_brent_oil(self, start_date="2001-01-01", end_date=None):
        """
        Pull Brent crude oil daily prices (USD/barrel).

        Returns long-format DataFrame with one row per trading day.
        Indicator: "brent_oil_usd", unit: "USD/barrel".
        """
        return self._fetch_ticker(
            ticker="BZ=F",
            indicator="brent_oil_usd",
            unit="USD/barrel",
            start_date=start_date,
            end_date=end_date,
        )

    # ---------- generic helper ----------

    def _fetch_ticker(self, ticker, indicator, unit, start_date, end_date=None):
        """
        Download an OHLCV time series from Yahoo Finance and reshape it
        to our long-format schema. Stores the daily Close as the value.
        """

        logger.info(
            f"[yahoo] downloading {ticker} ({indicator}) "
            f"from {start_date} to {end_date or 'today'}"
        )

        raw = _yf.download(
            ticker,
            start=start_date,
            end=end_date,
            progress=False,
            auto_adjust=False,
        )

        if raw is None or raw.empty:
            logger.warning(f"[yahoo] {ticker} returned empty — skipping")
            return self._empty_frame()

        # yfinance returns a multi-index column ('Close', 'BZ=F') when downloading
        # a single ticker. Flatten and pick the Close column.
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw["Close"].iloc[:, 0]
        else:
            close = raw["Close"]

        df = pd.DataFrame({
            "date": close.index,
            "indicator": indicator,
            "value": close.astype(float).values,
            "source": self.SOURCE_ID,
            "unit": unit,
        })

        df["date"] = pd.to_datetime(df["date"])
        df = df.dropna(subset=["value"]).sort_values("date").reset_index(drop=True)

        logger.success(
            f"[yahoo] {ticker}: {len(df)} rows "
            f"({df['date'].min().date()} -> {df['date'].max().date()})"
        )
        return df

    @staticmethod
    def _empty_frame():
        return pd.DataFrame(columns=["date", "indicator", "value", "source", "unit"])

    # ---------- output ----------

    def save(self, df, filename="yahoo_macro.parquet"):
        """
        Persist to data/output/processed/macro/<filename>.

        Append-and-dedupe on (date, indicator) — same pattern as CBNFetcher.save.
        """
        if df.empty:
            logger.warning("[yahoo] save() called with empty DataFrame — skipping")
            return

        required = ["date", "indicator", "value", "source", "unit"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"DataFrame missing required columns: {missing}")

        out_dir = Path(MACRO_PROCESSED_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / filename

        if out_path.exists():
            existing = pd.read_parquet(out_path)
            existing["date"] = pd.to_datetime(existing["date"])
            combined = pd.concat([existing, df], ignore_index=True)
        else:
            combined = df

        combined = (
            combined
            .drop_duplicates(subset=["date", "indicator"], keep="last")
            .sort_values(["indicator", "date"])
            .reset_index(drop=True)
        )

        combined.to_parquet(out_path, index=False)
        logger.success(
            f"[yahoo] Wrote {len(combined):,} rows to {out_path} "
            f"({len(df)} new this run)"
        )
        return out_path
