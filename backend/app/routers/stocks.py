"""API bridge layer stock endpoints.

This router serves read-only stock lists, details, OHLC, line series, and peers
from the existing data layer. It connects React stock pages to normalized NGX
market data while the database persistence layer is being completed.
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.db.crud import get_latest_by_ticker, get_ticker_metadata, get_ticker_prices, public_ticker, sector_slug
from app.services.cache import ttl_cache
from app.services.fundamentals_service import financial_table_rows, latest_company_record
from app.services.model_snapshot import get_model_signal_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stocks", tags=["stocks"])

RangeValue = Literal["1D", "5D", "1M", "3M", "6M", "1Y", "5Y", "MAX"]


@router.get("")
@ttl_cache(ttl_seconds=300, name="stocks_list")
def list_stocks(sector: str | None = None) -> list[dict[str, object]]:
    """Return latest stock cards for the frontend stocks table."""

    latest = get_latest_by_ticker()
    signals = get_model_signal_snapshot()
    rows = [_stock_card(row, include_analysis=False, signals=signals) for _, row in latest.iterrows()]
    if sector:
        rows = [row for row in rows if row["sectorSlug"] == sector]
    return rows


@router.get("/top-gainers")
@ttl_cache(ttl_seconds=60, name="top_gainers")
def top_gainers(limit: int = Query(default=5, ge=1, le=50)) -> list[dict[str, object]]:
    """Return top gainers by latest percentage move."""

    return sorted(list_stocks(), key=lambda row: float(row["changePct"]), reverse=True)[:limit]


@router.get("/top-losers")
@ttl_cache(ttl_seconds=60, name="top_losers")
def top_losers(limit: int = Query(default=5, ge=1, le=50)) -> list[dict[str, object]]:
    """Return top losers by latest percentage move."""

    return sorted(list_stocks(), key=lambda row: float(row["changePct"]))[:limit]


@router.get("/most-active")
@ttl_cache(ttl_seconds=60, name="most_active")
def most_active(limit: int = Query(default=5, ge=1, le=50)) -> list[dict[str, object]]:
    """Return most active stocks by latest volume."""

    return sorted(list_stocks(), key=lambda row: float(row["volume"]), reverse=True)[:limit]


@router.get("/{symbol}")
def get_stock(symbol: str) -> dict[str, object]:
    """Return stock detail for one ticker."""

    try:
        prices = get_ticker_prices(symbol)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    card = _stock_card(prices.iloc[-1], include_analysis=True)
    metadata = get_ticker_metadata(symbol)
    company = latest_company_record(symbol)
    company_values = company.values
    description = company_values.get("description")
    if not description:
        description = f"{card['name']} is listed on the Nigerian Exchange and tracked from real NGX market data."
    card.update(
        {
            "description": description,
            "founded": _optional_int(company_values.get("founded")),
            "headquarters": company_values.get("headquarters"),
            "employees": _optional_int(company_values.get("employees")),
            "website": company_values.get("website"),
            "ceo": company_values.get("ceo"),
            "industry": str(company_values.get("industry") or metadata.get("sector", card["sector"])),
            "exchange": "NGX",
            "fundamentalsSource": company.source,
            "ohlc": get_ohlc(symbol, "1Y"),
            "intradayLine": get_line(symbol, "1Y"),
        }
    )
    return card


@router.get("/{symbol}/ohlc")
def get_ohlc(symbol: str, range: RangeValue = "1Y") -> list[dict[str, object]]:
    """Return OHLC series for a frontend chart range."""

    try:
        prices = _range_prices(get_ticker_prices(symbol), range)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [
        {
            "time": row["date"].isoformat(),
            "open": _float(row["pclose"]),
            "high": _float(row["high"]),
            "low": _float(row["low"]),
            "close": _float(row["close"]),
            "volume": int(_float(row["volume"], 0.0)),
        }
        for _, row in prices.iterrows()
    ]


@router.get("/{symbol}/line")
def get_line(symbol: str, range: RangeValue = "1Y") -> list[dict[str, object]]:
    """Return close-price line series for a frontend chart range."""

    return [{"time": row["time"], "value": row["close"]} for row in get_ohlc(symbol, range)]


@router.get("/{symbol}/peers")
def get_peers(symbol: str) -> list[dict[str, object]]:
    """Return same-sector peer stocks."""

    metadata = get_ticker_metadata(symbol)
    target_sector = metadata.get("sector")
    return [
        {
            "symbol": row["symbol"],
            "name": row["name"],
            "price": row["price"],
            "changePct": row["changePct"],
            "marketCap": row["marketCap"],
            "pe": row["pe"],
            "aiOutlook": row["aiOutlook"],
        }
        for row in list_stocks()
        if row["sector"] == target_sector and row["symbol"] != public_ticker(str(metadata["ticker"]))
    ][:12]


@router.get("/{symbol}/fundamentals")
def get_fundamentals(symbol: str) -> list[dict[str, object]]:
    """Return derived market fundamentals from available price history."""

    prices = get_ticker_prices(symbol)
    latest = prices.iloc[-1]
    close = _float(latest["close"])
    pclose = _float(latest["pclose"], close)
    year_rows = prices.copy()
    year_rows["year"] = pd.to_datetime(year_rows["date"]).dt.year
    annual_close = year_rows.groupby("year")["close"].last().tail(3)
    annual_volume = year_rows.groupby("year")["volume"].mean().tail(3)

    def annual_value(series: pd.Series, offset: int, fallback: object = "N/A") -> object:
        if len(series) < offset:
            return fallback
        return round(_float(series.iloc[-offset]), 2)

    high_52w = _float(prices["high"].tail(252).max(), close)
    low_52w = _float(prices["low"].tail(252).min(), close)
    ytd_start = _float(year_rows[year_rows["year"] == pd.to_datetime(latest["date"]).year]["close"].iloc[0], close)
    ytd_return = 0.0 if ytd_start == 0 else ((close - ytd_start) / ytd_start) * 100
    daily_return = 0.0 if pclose == 0 else ((close - pclose) / pclose) * 100
    avg_volume_90d = _float(prices["volume"].tail(90).mean(), 0.0)
    price_rows = [
        {
            "metric": "Year-end close (market data)",
            "fy2021": annual_value(annual_close, 3),
            "fy2022": annual_value(annual_close, 2),
            "fy2023": annual_value(annual_close, 1),
            "ttm": round(close, 2),
        },
        {
            "metric": "Average daily volume (market data)",
            "fy2021": round(annual_value(annual_volume, 3, 0)),
            "fy2022": round(annual_value(annual_volume, 2, 0)),
            "fy2023": round(annual_value(annual_volume, 1, 0)),
            "ttm": round(avg_volume_90d),
        },
        {
            "metric": "Price return (market data)",
            "fy2021": "Unavailable",
            "fy2022": "Unavailable",
            "fy2023": f"{ytd_return:.2f}% YTD",
            "ttm": f"{daily_return:.2f}% latest",
        },
        {"metric": "52-week high (market data)", "fy2021": "Unavailable", "fy2022": "Unavailable", "fy2023": "Unavailable", "ttm": round(high_52w, 2)},
        {"metric": "52-week low (market data)", "fy2021": "Unavailable", "fy2022": "Unavailable", "fy2023": "Unavailable", "ttm": round(low_52w, 2)},
    ]
    return financial_table_rows(symbol, price_rows)


def _stock_card(row: pd.Series, include_analysis: bool = False, signals: dict[str, object] | None = None) -> dict[str, object]:
    """Format a price row as the frontend Stock type."""

    metadata = get_ticker_metadata(str(row["ticker"]))
    close = _float(row["close"])
    pclose = _float(row["pclose"], close)
    change = close - pclose
    change_pct = 0.0 if pclose == 0 else (change / pclose) * 100
    signal_map = signals if signals is not None else get_model_signal_snapshot()
    signal = signal_map.get(str(row["ticker"]).upper())
    company = latest_company_record(str(row["ticker"]))
    company_values = company.values
    outlook = signal.outlook if signal else "neutral"
    if include_analysis:
        prices = get_ticker_prices(str(row["ticker"]))
        risk_score = signal.risk_score if signal else _quick_risk_score_from_prices(prices, change_pct)
        high_52w = _float(prices["high"].tail(252).max(), close)
        low_52w = _float(prices["low"].tail(252).min(), close)
        sparkline = [round(_float(value), 2) for value in prices["close"].tail(30).tolist()]
    else:
        risk_score = _quick_risk_score_from_row(row, change_pct)
        high_52w = _float(row["high"], close)
        low_52w = _float(row["low"], close)
        sparkline = [round(close, 2)]
    confidence = signal.confidence if signal else 0.0
    if signal and not include_analysis:
        risk_score = signal.risk_score
    sector = str(metadata.get("sector", "Unknown"))
    return {
        "symbol": public_ticker(str(row["ticker"])),
        "name": str(metadata.get("name", public_ticker(str(row["ticker"])))),
        "sector": sector,
        "sectorSlug": sector_slug(sector),
        "price": round(close, 2),
        "change": round(change, 2),
        "changePct": round(change_pct, 2),
        "marketCap": _optional_float(company_values.get("market_cap")),
        "pe": _optional_float(company_values.get("pe")),
        "dividendYield": _optional_float(company_values.get("dividend_yield")),
        "volume": int(_float(row["volume"], 0.0)),
        "aiOutlook": outlook,
        "confidence": round(confidence),
        "riskScore": risk_score,
        "sectorRank": _optional_int(company_values.get("sector_rank")),
        "high52w": round(high_52w, 2),
        "low52w": round(low_52w, 2),
        "beta": _optional_float(company_values.get("beta")),
        "sparkline": sparkline,
    }


def _range_prices(prices: pd.DataFrame, range_value: RangeValue) -> pd.DataFrame:
    """Trim historical prices to the requested chart range."""

    points = {"1D": 1, "5D": 5, "1M": 22, "3M": 66, "6M": 130, "1Y": 260, "5Y": 1300, "MAX": len(prices)}
    return prices.tail(points[range_value]).copy()


def _quick_risk_score_from_row(row: pd.Series, change_pct: float) -> float:
    """Estimate risk quickly for list endpoints without full feature engineering."""

    close = _float(row["close"], 0.0)
    high = _float(row["high"], close)
    low = _float(row["low"], close)
    intraday_range = 0.0 if close == 0 else max((high - low) / close * 100, 0.0)
    score = 25 + min(intraday_range * 3.0, 35) + min(abs(change_pct) * 2.0, 20)
    return round(max(0.0, min(100.0, score)), 1)


def _quick_risk_score_from_prices(prices: pd.DataFrame, change_pct: float) -> float:
    """Estimate detail-page risk from real recent prices without model feature engineering."""

    latest = prices.iloc[-1]
    close = _float(latest["close"], 0.0)
    intraday = _quick_risk_score_from_row(latest, change_pct)
    returns = prices["close"].astype(float).pct_change(fill_method=None).tail(20)
    volatility = float(returns.std() * np.sqrt(252) * 100) if len(returns.dropna()) >= 5 else 0.0
    score = intraday + min(volatility * 0.5, 25.0)
    return round(max(0.0, min(100.0, score)), 1)


def _float(value: object, default: float = 0.0) -> float:
    """Safely convert values to float for JSON serialization."""

    try:
        if pd.isna(value):
            return default
        parsed = float(value)
        if np.isfinite(parsed):
            return parsed
        return default
    except (TypeError, ValueError):
        return default


def _optional_float(value: object) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        parsed = float(value)
        return parsed if np.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    parsed = _optional_float(value)
    return int(parsed) if parsed is not None else None
