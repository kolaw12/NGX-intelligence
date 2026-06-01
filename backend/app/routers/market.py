"""Market metadata endpoints consumed by the React dashboard."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.db.crud import get_latest_by_ticker, get_ticker_metadata, load_prices, sector_slug
from app.services.cache import ttl_cache

router = APIRouter(tags=["market"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MACRO_DIR = PROJECT_ROOT / "data" / "output" / "processed" / "macro"

@router.get("/sectors")
@ttl_cache(ttl_seconds=600, name="sectors")
def list_sectors() -> list[dict[str, object]]:
    latest = get_latest_by_ticker()
    prices = load_prices()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    buckets: dict[str, list[dict[str, object]]] = defaultdict(list)
    for _, row in latest.iterrows():
        metadata = get_ticker_metadata(str(row["ticker"]))
        sector = str(metadata.get("sector", "Unknown"))
        close = _float(row["close"])
        pclose = _float(row["pclose"], close) or close
        change_pct = 0.0 if pclose == 0 else (close - pclose) / pclose * 100
        buckets[sector].append(
            {
                "ticker": str(row["ticker"]),
                "name": str(metadata.get("name", row["ticker"])),
                "close": close,
                "volume": _float(row["volume"]),
                "changePct": change_pct,
            }
        )

    sectors = []
    for sector, rows in buckets.items():
        avg_day = sum(float(row["changePct"]) for row in rows) / max(len(rows), 1)
        tickers = [str(row["ticker"]) for row in rows]
        volume = sum(float(row["volume"]) for row in rows)
        momentum = round(max(0.0, min(100.0, 50 + avg_day * 8 + min(len(rows), 20))))
        risk = round(max(20.0, min(85.0, 48 + abs(avg_day) * 4)))
        outlook = "bullish" if avg_day > 0.6 else "bearish" if avg_day < -0.6 else "neutral"
        top = sorted(rows, key=lambda row: float(row["volume"]), reverse=True)[:5]
        sector_prices = prices[prices["ticker"].isin(tickers)].copy()
        sectors.append(
            {
                "slug": sector_slug(sector),
                "name": sector,
                "performanceDay": round(avg_day, 2),
                "performanceWeek": round(_sector_return(sector_prices, 5), 2),
                "performanceMonth": round(_sector_return(sector_prices, 22), 2),
                "performanceYtd": round(_sector_ytd_return(sector_prices), 2),
                "marketCap": round(volume * 1000),
                "componentCount": len(rows),
                "aiOutlook": outlook,
                "momentum": momentum,
                "riskScore": risk,
                "sparkline": _sector_sparkline(sector_prices),
                "summary": f"{sector} contains {len(rows)} tracked NGX names with average latest performance of {avg_day:.2f}%.",
                "topConstituents": [str(row["ticker"]) for row in top],
            }
        )
    return sorted(sectors, key=lambda row: str(row["name"]))


@router.get("/sectors/{slug}")
def get_sector(slug: str) -> dict[str, object]:
    for sector in list_sectors():
        if sector["slug"] == slug:
            return sector
    raise HTTPException(status_code=404, detail="Sector not found")


@router.get("/macro/indicators")
@ttl_cache(ttl_seconds=300, name="macro_indicators")
def macro_indicators() -> list[dict[str, object]]:
    latest = _latest_macro_values()
    if not latest:
        return []

    indicators = []
    mapping = {
        "nse_asi_close": ("asi", "NGX All-Share Index", "index_points"),
        "nse_asi_change_pct": ("asi-change", "NGX ASI Daily Change", "%"),
        "nse_asi_mkt_cap": ("market-cap", "NGX Market Capitalization", "NGN"),
        "usd_ngn_rate": ("fx-official", "NGN / USD", "NGN"),
        "brent_oil_usd": ("brent", "Brent Crude", "$"),
    }
    for indicator, (key, label, default_unit) in mapping.items():
        row = latest.get(indicator)
        if not row:
            continue
        indicators.append(
            {
                "key": key,
                "label": label,
                "value": round(float(row["value"]), 2),
                "unit": str(row.get("unit") or default_unit),
                "changePct": round(_macro_change_pct(indicator), 2),
                "asOf": row["date"],
                "source": str(row.get("source", "local")),
            }
        )
    return indicators


@router.get("/macro/events")
@ttl_cache(ttl_seconds=300, name="macro_events")
def macro_events() -> list[dict[str, object]]:
    indicators = macro_indicators()
    events = [
        {
            "id": f"macro-{item['key']}",
            "date": str(item["asOf"]),
            "title": f"{item['label']} updated",
            "description": f"{item['label']} is {item['value']} {item['unit']} from {item['source']}.",
            "impact": "high" if item["key"] in {"asi", "fx-official"} else "medium",
            "category": "fx" if item["key"] == "fx-official" else "external" if item["key"] == "brent" else "policy",
        }
        for item in indicators[:5]
    ]
    return events


@router.get("/market/overview")
@ttl_cache(ttl_seconds=45, name="market_overview")
def market_overview() -> dict[str, object]:
    latest = get_latest_by_ticker()
    close = latest["close"].apply(_float)
    pclose = latest["pclose"].apply(_float)
    pclose = pclose.where(pclose != 0, close)
    changes = close - pclose
    volume = latest["volume"].apply(_float)
    macro = _latest_macro_values()
    asi_row = macro.get("nse_asi_close")
    asi_change_row = macro.get("nse_asi_change_pct")
    market_cap_row = macro.get("nse_asi_mkt_cap")
    asi_change_pct = float(asi_change_row["value"]) if asi_change_row else None
    return {
        "asi": round(float(asi_row["value"]), 2) if asi_row else None,
        "asiChange": None,
        "asiChangePct": round(asi_change_pct, 2) if asi_change_pct is not None else None,
        "totalMarketCap": round(float(market_cap_row["value"]), 2) if market_cap_row else None,
        "totalVolume": round(float(volume.sum())),
        "totalValue": round(float((close * volume).sum())),
        "advancing": int((changes > 0).sum()),
        "declining": int((changes < 0).sum()),
        "unchanged": int((changes == 0).sum()),
        "deals": None,
        "marketStatus": "closed" if date.today().weekday() >= 5 else "open",
        "lastUpdated": pd.to_datetime(latest["date"]).max().isoformat(),
    }


def _sector_return(prices: pd.DataFrame, sessions: int) -> float:
    """Return real sector average close return over a session window."""

    returns = []
    for _, group in prices.sort_values("date").groupby("ticker"):
        closes = group["close"].astype(float).dropna()
        if len(closes) > sessions and float(closes.iloc[-sessions - 1]) != 0:
            returns.append(((float(closes.iloc[-1]) - float(closes.iloc[-sessions - 1])) / float(closes.iloc[-sessions - 1])) * 100)
    return sum(returns) / len(returns) if returns else 0.0


def _sector_ytd_return(prices: pd.DataFrame) -> float:
    """Return real sector average year-to-date close return."""

    if prices.empty:
        return 0.0
    latest_date = pd.to_datetime(prices["date"], errors="coerce").max()
    year_prices = prices[pd.to_datetime(prices["date"], errors="coerce").dt.year == latest_date.year]
    returns = []
    for _, group in year_prices.sort_values("date").groupby("ticker"):
        closes = group["close"].astype(float).dropna()
        if len(closes) >= 2 and float(closes.iloc[0]) != 0:
            returns.append(((float(closes.iloc[-1]) - float(closes.iloc[0])) / float(closes.iloc[0])) * 100)
    return sum(returns) / len(returns) if returns else 0.0


def _sector_sparkline(prices: pd.DataFrame) -> list[float]:
    """Return real indexed sector close history for compact sparklines."""

    if prices.empty:
        return []
    pivot = prices.sort_values("date").pivot_table(index="date", columns="ticker", values="close", aggfunc="last").tail(24)
    if pivot.empty:
        return []
    indexed = pivot.divide(pivot.iloc[0].replace(0, pd.NA), axis=1) * 100
    series = indexed.mean(axis=1, skipna=True).dropna()
    return [round(float(value), 2) for value in series.tolist()]


def _float(value: object, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _latest_macro_values() -> dict[str, dict[str, object]]:
    """Load latest local macro indicators from parquet artifacts."""

    frames = []
    for path in MACRO_DIR.glob("*.parquet"):
        try:
            frames.append(pd.read_parquet(path))
        except Exception:
            continue
    if not frames:
        return {}
    macro = pd.concat(frames, ignore_index=True)
    macro["date"] = pd.to_datetime(macro["date"], errors="coerce")
    macro = macro.dropna(subset=["date", "indicator", "value"]).sort_values(["indicator", "date"])
    latest = macro.groupby("indicator", as_index=False).tail(1)
    return {
        str(row["indicator"]): {
            "date": row["date"].date().isoformat(),
            "value": float(row["value"]),
            "source": row.get("source", "local"),
            "unit": row.get("unit", ""),
        }
        for _, row in latest.iterrows()
    }


def _macro_change_pct(indicator: str) -> float:
    """Return latest percent change for one macro indicator."""

    frames = []
    for path in MACRO_DIR.glob("*.parquet"):
        try:
            frame = pd.read_parquet(path)
            matched = frame[frame["indicator"].astype(str) == indicator]
            if not matched.empty:
                frames.append(matched)
        except Exception:
            continue
    if not frames:
        return 0.0
    rows = pd.concat(frames, ignore_index=True)
    rows["date"] = pd.to_datetime(rows["date"], errors="coerce")
    rows = rows.dropna(subset=["date", "value"]).sort_values("date").tail(2)
    if len(rows) < 2:
        return 0.0
    previous = float(rows.iloc[0]["value"])
    current = float(rows.iloc[-1]["value"])
    if previous == 0:
        return 0.0
    return ((current - previous) / abs(previous)) * 100
