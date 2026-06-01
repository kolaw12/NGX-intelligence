"""Small user-data endpoints required by the local frontend."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.crud import get_ticker_metadata, get_ticker_prices, public_ticker
from app.db.database import get_db
from app.db.models import Alert, PortfolioPosition, User, WatchlistItem
from app.routers.auth import get_current_user
from app.services.model_snapshot import get_model_signal_snapshot

router = APIRouter(tags=["user-data"])

DEFAULT_WATCHLIST_ID = "default"


class WatchlistCreate(BaseModel):
    name: str
    description: str | None = None


class SymbolInput(BaseModel):
    symbol: str


class AlertCreate(BaseModel):
    symbol: str
    condition: str
    threshold: float


class PortfolioPositionInput(BaseModel):
    symbol: str
    units: float
    avgCost: float


@router.get("/watchlists")
def list_watchlists(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    symbols = [
        public_ticker(item.ticker)
        for item in db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).order_by(WatchlistItem.created_at).all()
    ]
    return [_watchlist_payload(symbols)]


@router.post("/watchlists")
def create_watchlist(
    input: WatchlistCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Return the persisted default watchlist.

    The current database schema stores per-user watchlist symbols, not multiple
    named watchlists. The response keeps the frontend contract stable.
    """

    symbols = [public_ticker(item.ticker) for item in db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).all()]
    return _watchlist_payload(symbols, name=input.name, description=input.description)


@router.post("/watchlists/{watchlist_id}/symbols")
def add_symbol(
    watchlist_id: str,
    input: SymbolInput,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    canonical = str(get_ticker_metadata(input.symbol)["ticker"]).upper()
    exists = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user.id, WatchlistItem.ticker == canonical)
        .one_or_none()
    )
    if not exists:
        db.add(WatchlistItem(user_id=user.id, ticker=canonical))
        db.commit()
    return _current_watchlist_payload(db, user)


@router.delete("/watchlists/{watchlist_id}/symbols/{symbol}")
def remove_symbol(
    watchlist_id: str,
    symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    canonical = str(get_ticker_metadata(symbol)["ticker"]).upper()
    item = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user.id, WatchlistItem.ticker == canonical)
        .one_or_none()
    )
    if item:
        db.delete(item)
        db.commit()
    return _current_watchlist_payload(db, user)


@router.delete("/watchlists/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist(
    watchlist_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).delete()
    db.commit()
    return None


@router.get("/alerts")
def list_alerts(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return [
        _alert_payload(alert)
        for alert in db.query(Alert).filter(Alert.user_id == user.id).order_by(Alert.created_at.desc()).all()
    ]


@router.post("/alerts")
def create_alert(
    input: AlertCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    canonical = str(get_ticker_metadata(input.symbol)["ticker"]).upper()
    alert = Alert(
        user_id=user.id,
        ticker=canonical,
        condition=input.condition,
        threshold=input.threshold,
        status="active",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return _alert_payload(alert)


@router.delete("/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(
    alert_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == user.id).one_or_none()
    if alert:
        db.delete(alert)
        db.commit()
    return None


@router.get("/portfolio")
def get_portfolio(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    """Return a portfolio summary using live backend prices and model signals."""

    return _portfolio_payload(db, user)


@router.post("/portfolio/positions")
def upsert_portfolio_position(
    input: PortfolioPositionInput,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Create or update a local portfolio holding."""

    symbol = input.symbol.upper().strip()
    canonical = str(get_ticker_metadata(symbol)["ticker"]).upper()
    existing = (
        db.query(PortfolioPosition)
        .filter(PortfolioPosition.user_id == user.id, PortfolioPosition.ticker == canonical)
        .one_or_none()
    )
    if existing:
        existing.quantity = input.units
        existing.average_cost = input.avgCost
    else:
        db.add(PortfolioPosition(user_id=user.id, ticker=canonical, quantity=input.units, average_cost=input.avgCost))
    db.commit()
    return _portfolio_payload(db, user)


@router.delete("/portfolio/positions/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
def delete_portfolio_position(
    symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Remove a local portfolio holding."""

    canonical = str(get_ticker_metadata(symbol)["ticker"]).upper()
    db.query(PortfolioPosition).filter(
        PortfolioPosition.user_id == user.id,
        PortfolioPosition.ticker == canonical,
    ).delete()
    db.commit()
    return None


def _portfolio_holding(position: dict[str, object]) -> dict[str, object] | None:
    """Build one holding row using the latest available market data."""

    symbol = str(position["symbol"]).upper()
    try:
        prices = get_ticker_prices(symbol)
        latest = prices.iloc[-1]
        metadata = get_ticker_metadata(symbol)
    except Exception:
        return None

    units = float(position["units"])
    avg_cost = float(position["avgCost"])
    current_price = float(latest["close"])
    previous_close = float(latest["pclose"]) if float(latest["pclose"]) else current_price
    market_value = units * current_price
    total_cost = units * avg_cost
    pnl = market_value - total_cost
    canonical = str(metadata["ticker"]).upper()
    signal = get_model_signal_snapshot().get(canonical)
    return {
        "symbol": public_ticker(canonical),
        "name": str(metadata.get("name", public_ticker(canonical))),
        "sector": str(metadata.get("sector", "Unknown")),
        "units": units,
        "avgCost": avg_cost,
        "currentPrice": round(current_price, 2),
        "marketValue": round(market_value, 2),
        "unrealizedPnl": round(pnl, 2),
        "unrealizedPnlPct": round((pnl / total_cost) * 100, 2) if total_cost else 0.0,
        "allocationPct": 0.0,
        "aiOutlook": signal.outlook if signal else "neutral",
        "dayChange": (current_price - previous_close) * units,
    }


def _portfolio_payload(db: Session, user: User) -> dict[str, object]:
    positions = db.query(PortfolioPosition).filter(PortfolioPosition.user_id == user.id).all()
    holdings = [_portfolio_holding(_position_payload(position)) for position in positions]
    holdings = [holding for holding in holdings if holding is not None]
    total_value = sum(float(holding["marketValue"]) for holding in holdings)
    total_cost = sum(float(holding["units"]) * float(holding["avgCost"]) for holding in holdings)
    day_change = sum(float(holding["dayChange"]) for holding in holdings)
    total_pnl = total_value - total_cost

    for holding in holdings:
        holding["allocationPct"] = round((float(holding["marketValue"]) / total_value) * 100, 2) if total_value else 0.0
        holding.pop("dayChange", None)

    allocation_by_sector: dict[str, float] = {}
    for holding in holdings:
        allocation_by_sector[str(holding["sector"])] = allocation_by_sector.get(str(holding["sector"]), 0.0) + float(holding["marketValue"])
    allocation = [
        {"sector": sector, "weight": round((value / total_value) * 100, 2) if total_value else 0.0}
        for sector, value in sorted(allocation_by_sector.items())
    ]

    return {
        "totalValue": round(total_value, 2),
        "totalCost": round(total_cost, 2),
        "unrealizedPnl": round(total_pnl, 2),
        "unrealizedPnlPct": round((total_pnl / total_cost) * 100, 2) if total_cost else 0.0,
        "dayChange": round(day_change, 2),
        "dayChangePct": round((day_change / max(total_value - day_change, 1.0)) * 100, 2),
        "holdings": holdings,
        "allocation": allocation,
        "performanceSeries": _portfolio_performance_series([_position_payload(position) for position in positions]),
        "riskScore": _portfolio_risk_score(holdings),
        "diversificationScore": _portfolio_diversification_score(allocation),
    }


def _portfolio_performance_series(positions: list[dict[str, object]]) -> list[dict[str, object]]:
    """Build a simple historical portfolio value series from close prices."""

    values_by_date: dict[str, float] = {}
    for position in positions:
        try:
            prices = get_ticker_prices(str(position["symbol"]))
        except Exception:
            continue
        units = float(position["units"])
        for _, row in prices.tail(90).iterrows():
            date_key = row["date"].date().isoformat()
            values_by_date[date_key] = values_by_date.get(date_key, 0.0) + float(row["close"]) * units
    return [
        {"time": date_key, "value": round(value, 2)}
        for date_key, value in sorted(values_by_date.items())[-90:]
    ]


def _portfolio_risk_score(holdings: list[dict[str, object]]) -> float:
    """Estimate portfolio risk from concentration and bearish exposure."""

    if not holdings:
        return 0.0
    max_allocation = max(float(holding["allocationPct"]) for holding in holdings)
    bearish_weight = sum(
        float(holding["allocationPct"]) for holding in holdings if holding.get("aiOutlook") == "bearish"
    )
    score = 25 + max(0.0, max_allocation - 20.0) * 1.2 + bearish_weight * 0.4
    return round(max(0.0, min(100.0, score)), 1)


def _portfolio_diversification_score(allocation: list[dict[str, object]]) -> float:
    """Score diversification using sector concentration."""

    if not allocation:
        return 0.0
    concentration = sum((float(row["weight"]) / 100.0) ** 2 for row in allocation)
    score = (1.0 - concentration) * 100
    return round(max(0.0, min(100.0, score)), 1)


def _current_watchlist_payload(db: Session, user: User) -> dict[str, object]:
    symbols = [
        public_ticker(item.ticker)
        for item in db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).order_by(WatchlistItem.created_at).all()
    ]
    return _watchlist_payload(symbols)


def _watchlist_payload(
    symbols: list[str],
    name: str = "My Watchlist",
    description: str | None = None,
) -> dict[str, object]:
    """Return frontend-compatible watchlist JSON."""

    return {
        "id": DEFAULT_WATCHLIST_ID,
        "name": name,
        "description": description,
        "symbols": symbols,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }


def _alert_payload(alert: Alert) -> dict[str, object]:
    """Return frontend-compatible alert JSON."""

    return {
        "id": alert.id,
        "symbol": public_ticker(alert.ticker),
        "condition": alert.condition,
        "threshold": alert.threshold,
        "status": alert.status,
        "createdAt": alert.created_at.isoformat(),
        "triggeredAt": alert.triggered_at.isoformat() if alert.triggered_at else None,
        "message": alert.message,
    }


def _position_payload(position: PortfolioPosition) -> dict[str, object]:
    """Convert a persisted portfolio row into the local calculation shape."""

    return {
        "symbol": public_ticker(position.ticker),
        "units": float(position.quantity),
        "avgCost": float(position.average_cost or 0.0),
    }
