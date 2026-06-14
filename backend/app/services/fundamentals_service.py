"""Company fundamentals/profile loader for real exported datasets.

The project currently ships market prices and ticker metadata, but no populated
fundamentals export. This service consumes real CSV/parquet files when they are
placed under data/output/processed/fundamentals or data/master; absent values
are returned as unavailable rather than fabricated.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.db.crud import PRICE_DATA_PATH, canonical_ticker

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FUNDAMENTALS_DIR = PROJECT_ROOT / "data" / "output" / "processed" / "fundamentals"
MASTER_DIR = PROJECT_ROOT / "data" / "master"

FUNDAMENTAL_FILES = (
    FUNDAMENTALS_DIR / "fundamentals.parquet",
    FUNDAMENTALS_DIR / "fundamentals.csv",
    FUNDAMENTALS_DIR / "company_fundamentals.parquet",
    FUNDAMENTALS_DIR / "company_fundamentals.csv",
    MASTER_DIR / "fundamentals.parquet",
    MASTER_DIR / "fundamentals.csv",
)

PROFILE_FILES = (
    FUNDAMENTALS_DIR / "company_profiles.parquet",
    FUNDAMENTALS_DIR / "company_profiles.csv",
    FUNDAMENTALS_DIR / "profiles.parquet",
    FUNDAMENTALS_DIR / "profiles.csv",
    MASTER_DIR / "company_profiles.parquet",
    MASTER_DIR / "company_profiles.csv",
)

ALIASES = {
    "ticker": ("ticker", "symbol", "code", "security", "ngx_code"),
    "market_cap": ("market_cap", "marketcap", "market_capitalization", "mkt_cap", "capitalization"),
    "pe": ("pe", "p_e", "pe_ratio", "price_earnings", "price_to_earnings"),
    "dividend_yield": ("dividend_yield", "div_yield", "yield", "dividend_yield_pct"),
    "beta": ("beta",),
    "sector_rank": ("sector_rank", "rank_in_sector", "sector_position"),
    "headquarters": ("headquarters", "hq", "location"),
    "founded": ("founded", "founded_year", "year_founded"),
    "employees": ("employees", "employee_count", "staff_count"),
    "website": ("website", "url", "web"),
    "ceo": ("ceo", "chief_executive", "managing_director", "md_ceo"),
    "description": ("description", "profile", "business_description", "company_description"),
    "business_model": ("business_model", "business_description_short"),
    "industry": ("industry", "subsector", "sub_sector"),
    "key_risks": ("key_risks", "risks", "risk_factors"),
    "fiscal_year": ("fiscal_year", "year", "fy"),
    "period": ("period", "reporting_period"),
    "revenue": ("revenue", "turnover", "gross_earnings"),
    "profit_after_tax": ("profit_after_tax", "pat", "net_income", "profit"),
    "eps": ("eps", "earnings_per_share"),
    "total_assets": ("total_assets", "assets"),
    "shareholders_equity": ("shareholders_equity", "equity", "book_value"),
}


@dataclass(frozen=True)
class FundamentalsRecord:
    source: str
    values: dict[str, Any]


def fundamentals_status() -> dict[str, Any]:
    """Return data availability without loading large market-price files."""

    loaded = load_fundamentals()
    profile = load_company_profiles()
    has_market_fallback = PRICE_DATA_PATH.exists() and PRICE_DATA_PATH.stat().st_size > 0
    if not loaded.empty:
        source = "fundamentals"
    elif not profile.empty:
        source = "company_profiles"
    elif has_market_fallback:
        source = "market_data_fallback"
    else:
        source = "unavailable"
    return {
        "ok": source != "unavailable",
        "source": source,
        "fundamentalsRows": int(len(loaded)),
        "profileRows": int(len(profile)),
        "marketDataFallback": has_market_fallback,
        "fundamentalsFiles": [_relative(path) for path in FUNDAMENTAL_FILES if path.exists()],
        "profileFiles": [_relative(path) for path in PROFILE_FILES if path.exists()],
    }


@lru_cache(maxsize=1)
def load_fundamentals() -> pd.DataFrame:
    """Load normalized fundamentals rows from the first available real export."""

    return _load_first_existing(FUNDAMENTAL_FILES)


@lru_cache(maxsize=1)
def load_company_profiles() -> pd.DataFrame:
    """Load normalized company profile rows from the first available real export, then JSON fallback."""

    frame = _load_first_existing(PROFILE_FILES)
    if not frame.empty:
        return frame
    return _load_json_profiles()


def _load_json_profiles() -> pd.DataFrame:
    """Load company profiles from data/master/company_profiles.json (ticker-keyed dict)."""
    json_path = MASTER_DIR / "company_profiles.json"
    if not json_path.exists():
        return pd.DataFrame()
    try:
        data = json.loads(json_path.read_text())
        rows = []
        for ticker, profile in data.items():
            row = {"ticker": ticker}
            row.update(profile)
            rows.append(row)
        frame = pd.DataFrame(rows)
        frame = _normalize_columns(frame)
        logger.info("Loaded %d company profiles from %s", len(frame), json_path)
        return frame
    except Exception as exc:
        logger.warning("Failed to load company profiles JSON: %s", exc)
        return pd.DataFrame()


def latest_company_record(ticker: str) -> FundamentalsRecord:
    """Return merged latest fundamentals/profile values for a ticker."""

    canonical = canonical_ticker(ticker)
    values: dict[str, Any] = {}
    sources: list[str] = []
    for frame, source_name in ((load_fundamentals(), "fundamentals"), (load_company_profiles(), "company_profiles")):
        if frame.empty or "ticker" not in frame.columns:
            continue
        rows = frame[frame["ticker"].astype(str).str.upper() == canonical].copy()
        if rows.empty:
            continue
        row = _latest_row(rows)
        values.update({key: _json_value(value) for key, value in row.items() if key != "ticker"})
        sources.append(source_name)
    return FundamentalsRecord(source="+".join(sources) if sources else "unavailable", values=values)


def financial_table_rows(ticker: str, price_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return fundamentals table rows from real filings when available.

    If there is no fundamentals export, price-derived rows from the existing
    market-data engine are returned and marked as market-data metrics.
    """

    canonical = canonical_ticker(ticker)
    frame = load_fundamentals()
    if frame.empty or "ticker" not in frame.columns or "fiscal_year" not in frame.columns:
        return price_rows
    rows = frame[frame["ticker"].astype(str).str.upper() == canonical].copy()
    if rows.empty:
        return price_rows
    rows["fiscal_year"] = pd.to_numeric(rows["fiscal_year"], errors="coerce")
    rows = rows.dropna(subset=["fiscal_year"]).sort_values("fiscal_year")
    if rows.empty:
        return price_rows

    metrics = [
        ("Revenue", "revenue"),
        ("Profit after tax", "profit_after_tax"),
        ("EPS", "eps"),
        ("Total assets", "total_assets"),
        ("Shareholders equity", "shareholders_equity"),
        ("P/E", "pe"),
        ("Dividend yield", "dividend_yield"),
    ]
    latest_years = [int(year) for year in rows["fiscal_year"].dropna().unique()[-3:]]
    output = []
    for label, column in metrics:
        if column not in rows.columns:
            continue
        by_year = rows.dropna(subset=[column]).groupby("fiscal_year")[column].last()
        if by_year.empty:
            continue
        output.append(
            {
                "metric": label,
                "fy2021": _year_value(by_year, latest_years, 3),
                "fy2022": _year_value(by_year, latest_years, 2),
                "fy2023": _year_value(by_year, latest_years, 1),
                "ttm": _json_value(by_year.iloc[-1]),
            }
        )
    return output or price_rows


def _load_first_existing(paths: tuple[Path, ...]) -> pd.DataFrame:
    for path in paths:
        if not path.exists() or path.stat().st_size == 0:
            continue
        try:
            frame = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
            frame = _normalize_columns(frame)
            logger.info("Loaded %s rows from %s", len(frame), path)
            return frame
        except Exception as exc:
            logger.warning("Skipping unreadable fundamentals file %s: %s", path, exc)
    return pd.DataFrame()


def _normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized.columns = [str(column).strip().lower().replace(" ", "_").replace("-", "_") for column in normalized.columns]
    rename: dict[str, str] = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            if alias in normalized.columns:
                rename[alias] = target
                break
    normalized = normalized.rename(columns=rename)
    if "ticker" in normalized.columns:
        normalized["ticker"] = normalized["ticker"].astype(str).str.upper().str.strip().apply(canonical_ticker)
    _STRING_COLUMNS = {"ticker", "headquarters", "website", "ceo", "description", "business_model", "industry", "key_risks", "company_name", "sector", "period"}
    for column in normalized.columns:
        if column not in _STRING_COLUMNS:
            try:
                normalized[column] = pd.to_numeric(normalized[column])
            except (TypeError, ValueError):
                pass
    return normalized


def _latest_row(rows: pd.DataFrame) -> pd.Series:
    sort_columns = [column for column in ("fiscal_year", "period", "date", "report_date") if column in rows.columns]
    if sort_columns:
        return rows.sort_values(sort_columns).iloc[-1]
    return rows.iloc[-1]


def _year_value(series: pd.Series, years: list[int], offset: int) -> Any:
    if len(years) < offset:
        return "—"
    value = series.get(float(years[-offset]), series.get(years[-offset], np.nan))
    return _json_value(value) if not pd.isna(value) else "—"


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except ValueError:
        pass
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        parsed = float(value)
        return parsed if np.isfinite(parsed) else None
    return value


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)
