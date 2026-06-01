"""Authenticated account profile, settings, and API token endpoints."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db, init_dev_database
from app.db.models import ApiToken, User, UserSetting
from app.routers.auth import _user_payload, get_current_user

router = APIRouter(tags=["account"])

_tables_checked = False


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    organization: str | None = Field(default=None, max_length=255)
    role: str = Field(default="professional", pattern="^(retail|professional|institutional)$")


class SettingsUpdate(BaseModel):
    settings: dict[str, bool]


class TokenCreate(BaseModel):
    name: str = Field(default="Personal API token", min_length=2, max_length=120)


def _ensure_tables() -> None:
    global _tables_checked
    if not _tables_checked:
        init_dev_database()
        _tables_checked = True


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _setting_payload(row: UserSetting | None) -> dict[str, bool]:
    if not row:
        return {}
    return {str(key): bool(value) for key, value in row.value.items()}


def _token_payload(token: ApiToken, include_secret: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": token.id,
        "name": token.name,
        "prefix": token.token_prefix,
        "createdAt": token.created_at.isoformat(),
        "lastUsedAt": token.last_used_at.isoformat() if token.last_used_at else None,
        "revokedAt": token.revoked_at.isoformat() if token.revoked_at else None,
    }
    if include_secret:
        payload["token"] = include_secret
    return payload


@router.put("/profile")
def update_profile(input: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    """Update real persisted user profile fields used by the frontend."""

    _ensure_tables()
    if input.email and input.email.lower() != user.email:
        existing = db.query(User).filter(User.email == input.email.lower(), User.id != user.id).one_or_none()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already in use")
        user.email = input.email.lower()
    user.full_name = input.name
    user.subscription_plan = "institutional" if input.role == "institutional" else input.role
    _upsert_setting(db, user.id, "profile.organization", {"value": input.organization or ""})
    db.commit()
    db.refresh(user)
    payload = _user_payload(user)
    payload["organization"] = input.organization or None
    return payload


@router.get("/profile/settings")
def get_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    """Return persisted user settings; empty means the UI should use built-in defaults."""

    _ensure_tables()
    row = db.query(UserSetting).filter(UserSetting.user_id == user.id, UserSetting.key == "workspace.settings").one_or_none()
    return {"settings": _setting_payload(row)}


@router.put("/profile/settings")
def update_settings(input: SettingsUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    """Persist notification and display settings for the authenticated user."""

    _ensure_tables()
    row = _upsert_setting(db, user.id, "workspace.settings", input.settings)
    db.commit()
    db.refresh(row)
    return {"settings": _setting_payload(row)}


@router.get("/api-tokens")
def list_api_tokens(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    """List non-revoked personal API token metadata for the authenticated user."""

    _ensure_tables()
    rows = (
        db.query(ApiToken)
        .filter(ApiToken.user_id == user.id, ApiToken.revoked_at.is_(None))
        .order_by(ApiToken.created_at.desc())
        .all()
    )
    return [_token_payload(row) for row in rows]


@router.post("/api-tokens", status_code=status.HTTP_201_CREATED)
def create_api_token(input: TokenCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    """Create a real personal API token and return the secret once."""

    _ensure_tables()
    raw_token = "ngx_" + secrets.token_urlsafe(32)
    row = ApiToken(
        user_id=user.id,
        name=input.name,
        token_prefix=raw_token[:12],
        token_hash=_hash_token(raw_token),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _token_payload(row, include_secret=raw_token)


@router.delete("/api-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_token(token_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    """Revoke a personal API token without deleting audit metadata."""

    _ensure_tables()
    row = db.query(ApiToken).filter(ApiToken.id == token_id, ApiToken.user_id == user.id).one_or_none()
    if row:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return None


def _upsert_setting(db: Session, user_id: str, key: str, value: dict[str, object]) -> UserSetting:
    row = db.query(UserSetting).filter(UserSetting.user_id == user_id, UserSetting.key == key).one_or_none()
    if row:
        row.value = value
    else:
        row = UserSetting(user_id=user_id, key=key, value=value)
        db.add(row)
    return row
