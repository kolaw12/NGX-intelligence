"""Admin endpoints backed by local database state."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import ensure_database_tables, get_db
from app.db.models import Alert, RecommendationSignal, User, WatchlistItem

router = APIRouter(prefix="/admin", tags=["admin"])


class UpdateUserRequest(BaseModel):
    """Admin user patch request from the React admin console."""

    role: str | None = None
    status: str | None = None


@router.get("/metrics")
def get_admin_metrics(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return operational metrics derived from persisted local data."""

    _ensure_tables()
    now = datetime.now(timezone.utc)
    users = db.query(User).all()
    alerts = db.query(Alert).all()
    watchlist_count = db.query(WatchlistItem).count()
    signups_by_day = _series_by_day([user.created_at for user in users], days=14)
    role_counts = Counter(_role_for_user(user) for user in users)
    return {
        "totalUsers": len(users),
        "activeUsers": sum(1 for user in users if user.is_active),
        "suspendedUsers": sum(1 for user in users if not user.is_active),
        "newSignupsToday": sum(1 for user in users if _same_day(user.created_at, now)),
        "newSignups7d": sum(1 for user in users if _aware(user.created_at) >= now - timedelta(days=7)),
        "dau": len(users),
        "mau": len(users),
        "totalAlerts": len(alerts),
        "activeAlerts": sum(1 for alert in alerts if alert.status == "active"),
        "triggeredAlertsToday": sum(1 for alert in alerts if alert.triggered_at and _same_day(alert.triggered_at, now)),
        "totalWatchlists": watchlist_count,
        "apiRequests24h": db.query(RecommendationSignal).filter(RecommendationSignal.created_at >= now - timedelta(days=1)).count(),
        "apiErrorRate24h": 0,
        "signupsSeries": signups_by_day,
        "dauSeries": signups_by_day,
        "roleBreakdown": [{"role": role, "count": count} for role, count in sorted(role_counts.items())],
    }


@router.get("/users")
def list_users(q: str | None = Query(default=None), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Return users for the admin user table."""

    _ensure_tables()
    query = db.query(User)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.filter(User.email.ilike(pattern) | User.full_name.ilike(pattern))
    return [_user_payload(user, db) for user in query.order_by(User.created_at.desc()).all()]


@router.put("/users/{user_id}")
def update_user(user_id: str, patch: UpdateUserRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Update user role/status in the local database."""

    _ensure_tables()
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if patch.status:
        user.is_active = patch.status == "active"
    if patch.role:
        user.is_superuser = patch.role == "admin"
        user.subscription_plan = "institutional" if patch.role == "institutional" else "basic"
    db.commit()
    db.refresh(user)
    return _user_payload(user, db)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, db: Session = Depends(get_db)) -> None:
    """Delete a local user and cascading user data."""

    _ensure_tables()
    user = db.get(User, user_id)
    if user:
        db.delete(user)
        db.commit()
    return None


@router.get("/activity")
def get_activity(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Return recent activity synthesized from persisted rows."""

    _ensure_tables()
    events: list[dict[str, Any]] = []
    user_by_id = {user.id: user for user in db.query(User).all()}
    for user in user_by_id.values():
        events.append(_activity(user, user, "signup", "Account created", user.created_at))
    for alert in db.query(Alert).all():
        user = user_by_id.get(alert.user_id)
        if user:
            events.append(_activity(user, alert, "alert.create", f"Alert created for {alert.ticker}", alert.created_at))
    for item in db.query(WatchlistItem).all():
        user = user_by_id.get(item.user_id)
        if user:
            events.append(_activity(user, item, "watchlist.update", f"Watchlist updated with {item.ticker}", item.created_at))
    for signal in db.query(RecommendationSignal).order_by(RecommendationSignal.created_at.desc()).limit(limit).all():
        events.append(
            {
                "id": signal.id,
                "userId": signal.user_id or "system",
                "userEmail": "system@ngx.local",
                "userName": "NGX AI Advisor",
                "type": "profile.update",
                "description": f"Generated {signal.recommendation.value} recommendation for {signal.ticker}",
                "timestamp": signal.created_at.isoformat(),
                "metadata": {"ticker": signal.ticker, "confidence": signal.confidence},
            }
        )
    return sorted(events, key=lambda event: str(event["timestamp"]), reverse=True)[:limit]


def _user_payload(user: User, db: Session) -> dict[str, Any]:
    """Map ORM user to frontend admin user shape."""

    return {
        "id": user.id,
        "email": user.email,
        "name": user.full_name or user.email.split("@", 1)[0],
        "role": _role_for_user(user),
        "status": "active" if user.is_active else "suspended",
        "organization": user.subscription_plan if user.subscription_plan == "institutional" else None,
        "createdAt": user.created_at.isoformat(),
        "totalLogins": 0,
        "watchlistCount": db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).count(),
        "alertCount": db.query(Alert).filter(Alert.user_id == user.id).count(),
    }


def _activity(user: User, row: Any, event_type: str, description: str, timestamp: datetime) -> dict[str, Any]:
    """Build one admin activity event."""

    return {
        "id": getattr(row, "id", f"{event_type}-{user.id}"),
        "userId": user.id,
        "userEmail": user.email,
        "userName": user.full_name or user.email.split("@", 1)[0],
        "type": event_type,
        "description": description,
        "timestamp": timestamp.isoformat(),
    }


def _role_for_user(user: User) -> str:
    if user.is_superuser:
        return "admin"
    if user.subscription_plan == "institutional":
        return "institutional"
    return "professional"


def _series_by_day(datetimes: list[datetime], days: int) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).date()
    counts = Counter(_aware(value).date().isoformat() for value in datetimes)
    return [
        {"date": (now - timedelta(days=offset)).isoformat(), "count": counts[(now - timedelta(days=offset)).isoformat()]}
        for offset in range(days - 1, -1, -1)
    ]


def _same_day(value: datetime, reference: datetime) -> bool:
    return _aware(value).date() == reference.date()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _ensure_tables() -> None:
    ensure_database_tables()
