"""Processing layer for NGX OHLCV data.

This module normalizes raw or processed market data from the data layer into a
clean DataFrame for feature engineering, risk analysis, and recommendation API
endpoints. It connects upstream Parquet/CSV outputs in `data/` to downstream
services such as `FeatureEngineer`, `RiskAnalyzer`, and stock routers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessingReport:
    """Summary of the cleaning actions applied to a market data frame."""

    input_rows: int
    output_rows: int
    dropped_rows: int
    duplicate_rows_removed: int
    outlier_cells_capped: int
    missing_after_processing: int
    tickers_processed: int


class DataProcessor:
    """Clean and normalize NGX daily OHLCV data for downstream AI services."""

    REQUIRED_COLUMNS = ("date", "ticker", "pclose", "high", "low", "close", "volume", "change")
    NUMERIC_COLUMNS = ("pclose", "high", "low", "close", "volume", "change")
    PRICE_COLUMNS = ("pclose", "high", "low", "close")

    COLUMN_ALIASES = {
        "symbol": "ticker",
        "stock": "ticker",
        "security": "ticker",
        "trade_date": "date",
        "datetime": "date",
        "previous_close": "pclose",
        "prev_close": "pclose",
        "open": "pclose",
        "open_price": "pclose",
        "day_high": "high",
        "high_price": "high",
        "day_low": "low",
        "low_price": "low",
        "close_price": "close",
        "last": "close",
        "last_trade": "close",
        "traded_volume": "volume",
        "vol": "volume",
    }

    def __init__(self, outlier_quantile: float = 0.995, min_outlier_group_size: int = 20) -> None:
        """Create a processor.

        Args:
            outlier_quantile: Upper quantile used to cap extreme positive
                values per ticker. The lower price bound remains zero.
            min_outlier_group_size: Minimum ticker history length before
                quantile capping is applied.
        """

        if not 0.90 <= outlier_quantile <= 1.0:
            raise ValueError("outlier_quantile must be between 0.90 and 1.0")
        if min_outlier_group_size < 2:
            raise ValueError("min_outlier_group_size must be at least 2")
        self.outlier_quantile = outlier_quantile
        self.min_outlier_group_size = min_outlier_group_size
        self.last_report: ProcessingReport | None = None

    def process(self, df: pd.DataFrame, ticker: str | None = None) -> pd.DataFrame:
        """Return a clean OHLCV DataFrame sorted by ticker and date.

        Args:
            df: Raw or processed market data.
            ticker: Optional ticker to inject when processing a single-ticker
                file that does not contain a ticker column.

        Raises:
            ValueError: If required fields cannot be derived from the input.
        """

        if df.empty:
            logger.warning("Received empty data frame for processing")
            self.last_report = ProcessingReport(0, 0, 0, 0, 0, 0, 0)
            return self._empty_frame()

        input_rows = len(df)
        logger.info("Processing %s raw OHLCV rows", input_rows)

        clean = self._standardize_columns(df)
        if "ticker" not in clean.columns and ticker:
            clean["ticker"] = ticker

        clean = self._derive_missing_columns(clean)
        self._validate_required_columns(clean)

        clean["ticker"] = clean["ticker"].astype(str).str.upper().str.strip()
        clean["date"] = pd.to_datetime(clean["date"], errors="coerce").dt.date

        for column in self.NUMERIC_COLUMNS:
            clean[column] = pd.to_numeric(clean[column], errors="coerce")

        before_drop = len(clean)
        clean = clean.dropna(subset=["date", "ticker", "close"])
        clean = clean[clean["ticker"].ne("")]
        dropped_rows = before_drop - len(clean)
        if dropped_rows:
            logger.warning("Dropped %s rows with missing date, ticker, or close", dropped_rows)

        clean = clean.sort_values(["ticker", "date"]).reset_index(drop=True)
        clean, duplicate_rows_removed = self._remove_duplicates(clean)
        clean = self._repair_ohlcv(clean)
        clean, outlier_cells_capped = self._cap_outliers(clean)

        clean = clean[list(self.REQUIRED_COLUMNS)]
        clean = clean.sort_values(["ticker", "date"]).reset_index(drop=True)

        missing_after = int(clean.isna().sum().sum())
        report = ProcessingReport(
            input_rows=input_rows,
            output_rows=len(clean),
            dropped_rows=dropped_rows,
            duplicate_rows_removed=duplicate_rows_removed,
            outlier_cells_capped=outlier_cells_capped,
            missing_after_processing=missing_after,
            tickers_processed=int(clean["ticker"].nunique()) if not clean.empty else 0,
        )
        self.last_report = report
        logger.info("Processing complete: %s rows across %s tickers", report.output_rows, report.tickers_processed)
        if missing_after:
            logger.warning("Processed data still contains %s missing values", missing_after)
        return clean

    def process_file(self, path: str | Path, ticker: str | None = None) -> pd.DataFrame:
        """Load CSV or Parquet market data from disk and process it."""

        file_path = Path(path)
        logger.info("Loading market data file: %s", file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Market data file not found: {file_path}")

        suffix = file_path.suffix.lower()
        if suffix == ".parquet":
            df = pd.read_parquet(file_path)
        elif suffix == ".csv":
            df = pd.read_csv(file_path)
        else:
            raise ValueError(f"Unsupported market data file type: {suffix}")

        inferred_ticker = ticker or (file_path.stem if "historical" in str(file_path.parent).lower() else None)
        return self.process(df, ticker=inferred_ticker)

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names and apply known data-layer aliases."""

        clean = df.copy()
        clean.columns = [str(column).strip().lower().replace(" ", "_") for column in clean.columns]
        aliases = {source: target for source, target in self.COLUMN_ALIASES.items() if source in clean.columns}
        if aliases:
            logger.info("Applying column aliases: %s", aliases)
            clean = clean.rename(columns=aliases)
        return clean

    def _derive_missing_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Derive columns that are safely inferable from other OHLCV fields."""

        clean = df.copy()
        if "pclose" not in clean.columns and "close" in clean.columns:
            logger.warning("pclose missing; deriving previous close per ticker from close lag")
            group_key = "ticker" if "ticker" in clean.columns else None
            clean = clean.sort_values([group_key, "date"] if group_key else ["date"])
            clean["pclose"] = clean.groupby(group_key)["close"].shift(1) if group_key else clean["close"].shift(1)
            clean["pclose"] = clean["pclose"].fillna(clean["close"])

        if "change" not in clean.columns and {"close", "pclose"}.issubset(clean.columns):
            logger.info("change missing; deriving change as close - pclose")
            clean["change"] = pd.to_numeric(clean["close"], errors="coerce") - pd.to_numeric(clean["pclose"], errors="coerce")

        if "volume" not in clean.columns:
            logger.warning("volume missing; setting volume to 0")
            clean["volume"] = 0
        return clean

    def _validate_required_columns(self, df: pd.DataFrame) -> None:
        """Raise a helpful error when required columns are unavailable."""

        missing = [column for column in self.REQUIRED_COLUMNS if column not in df.columns]
        if missing:
            raise ValueError(
                "Market data is missing required columns after normalization: "
                + ", ".join(missing)
                + ". Expected date, ticker, pclose, high, low, close, volume, change."
            )

    def _remove_duplicates(self, df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        """Remove duplicate ticker/date records while preserving the latest row."""

        before = len(df)
        clean = df.drop_duplicates(subset=["ticker", "date"], keep="last")
        removed = before - len(clean)
        if removed:
            logger.warning("Removed %s duplicate ticker/date rows", removed)
        return clean.reset_index(drop=True), removed

    def _repair_ohlcv(self, df: pd.DataFrame) -> pd.DataFrame:
        """Forward-fill ticker-level gaps and repair inconsistent high/low fields."""

        clean = df.copy()
        for column in self.NUMERIC_COLUMNS:
            clean[column] = clean.groupby("ticker", group_keys=False)[column].ffill()

        clean["volume"] = clean["volume"].fillna(0).clip(lower=0)
        clean["pclose"] = clean["pclose"].fillna(clean["close"])
        clean["change"] = clean["change"].fillna(clean["close"] - clean["pclose"])

        # Ensure high/low always contain the observed close and previous close.
        row_max = clean[list(self.PRICE_COLUMNS)].max(axis=1, skipna=True)
        row_min = clean[list(self.PRICE_COLUMNS)].min(axis=1, skipna=True)
        clean["high"] = np.maximum(clean["high"].fillna(row_max), row_max)
        clean["low"] = np.minimum(clean["low"].fillna(row_min), row_min)

        for column in self.PRICE_COLUMNS:
            clean[column] = clean[column].clip(lower=0)

        return clean

    def _cap_outliers(self, df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        """Cap extreme positive numeric values per ticker using robust quantiles."""

        clean = df.copy()
        capped_cells = 0
        for column in self.PRICE_COLUMNS + ("volume",):
            clean[column] = clean[column].astype(float)
            caps = clean.groupby("ticker")[column].transform(self._robust_upper_cap)
            mask = clean[column].notna() & caps.notna() & (clean[column] > caps) & (caps > 0)
            capped_cells += int(mask.sum())
            clean.loc[mask, column] = caps[mask]

        if capped_cells:
            logger.warning("Capped %s outlier cells using %.3f quantile", capped_cells, self.outlier_quantile)

        clean["change"] = clean["close"] - clean["pclose"]
        return clean, capped_cells

    def _robust_upper_cap(self, series: pd.Series) -> float:
        """Return an upper cap for extreme spikes without suppressing normal new highs."""

        valid = series.dropna()
        if len(valid) < self.min_outlier_group_size:
            return np.nan

        q1 = float(valid.quantile(0.25))
        q3 = float(valid.quantile(0.75))
        iqr = q3 - q1
        quantile_cap = float(valid.quantile(self.outlier_quantile))
        iqr_cap = q3 + (10.0 * iqr)

        if iqr <= 0:
            median = float(valid.median())
            return median * 20.0 if median > 0 else np.nan
        return max(quantile_cap, iqr_cap)

    def _empty_frame(self) -> pd.DataFrame:
        """Return an empty frame with the normalized OHLCV schema."""

        return pd.DataFrame(columns=list(self.REQUIRED_COLUMNS))
