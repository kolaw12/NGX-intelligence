"""Local database-backed auth endpoints for the React frontend."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.db.database import ensure_database_tables, get_db
from app.db.models import PortfolioPosition, User

router = APIRouter(prefix="/auth", tags=["auth"])
_tables_checked = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class SignupRequest(LoginRequest):
    name: str = Field(min_length=2)
    organization: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


def _role_for(email: str, organization: str | None = None) -> str:
    if email.lower().startswith("admin") or email.lower().startswith("admin."):
        return "admin"
    if organization:
        return "institutional"
    return "professional"


def _hash_password(password: str) -> str:
    salt = os.getenv("AUTH_SALT", "ngx-local-dev").encode("utf-8")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return base64.urlsafe_b64encode(digest).decode("ascii")


def _is_development() -> bool:
    env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
    return env in {"development", "dev", "test", "testing", "local"}


def _ensure_tables() -> None:
    global _tables_checked
    if not _tables_checked:
        ensure_database_tables()
        _tables_checked = True


def _encode_token(user: User) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    payload = {
        "sub": user.id,
        "email": user.email,
        "exp": int(expires_at.timestamp()),
    }
    body = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
    secret = os.getenv("AUTH_SECRET", "ngx-local-dev-secret").encode("utf-8")
    signature = hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest()
    sig = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"dev.{body}.{sig}"


def _decode_token(token: str) -> dict[str, object]:
    try:
        prefix, body, sig = token.split(".", 2)
        if prefix != "dev":
            raise ValueError("unsupported token")
        secret = os.getenv("AUTH_SECRET", "ngx-local-dev-secret").encode("utf-8")
        expected = base64.urlsafe_b64encode(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest()).decode("ascii").rstrip("=")
        if not hmac.compare_digest(sig, expected):
            raise ValueError("bad signature")
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        if int(payload["exp"]) < int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("expired")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc


def _user_payload(user: User) -> dict[str, object]:
    role = "admin" if user.is_superuser else user.subscription_plan
    if role == "basic":
        role = "professional"
    return {
        "id": user.id,
        "email": user.email,
        "name": user.full_name or user.email.split("@", 1)[0],
        "role": role,
        "status": "active" if user.is_active else "suspended",
        "organization": user.subscription_plan if user.subscription_plan == "institutional" else None,
        "createdAt": user.created_at.isoformat(),
    }


def _session_payload(user: User) -> dict[str, object]:
    token = _encode_token(user)
    return {
        "token": token,
        "user": _user_payload(user),
        "expiresAt": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
    }


def _create_user(db: Session, email: str, password: str, name: str | None = None, organization: str | None = None) -> User:
    normalized_email = email.lower()
    user = db.query(User).filter(User.email == normalized_email).one_or_none()
    if user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already exists")

    user = User(
        email=normalized_email,
        hashed_password=_hash_password(password),
        full_name=name or normalized_email.split("@", 1)[0],
        is_superuser=_role_for(normalized_email) == "admin",
        subscription_plan="institutional" if organization else "basic",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _seed_demo_portfolio(db, user)
    return user


def _verify_user(db: Session, email: str, password: str) -> User:
    normalized_email = email.lower()
    user = db.query(User).filter(User.email == normalized_email).one_or_none()
    if not user and _is_development():
        return _create_user(
            db,
            normalized_email,
            password,
            name=normalized_email.split("@", 1)[0].replace(".", " ").title(),
            organization="Demo Institution",
        )
    if not user or user.hashed_password != _hash_password(password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is suspended")
    return user


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated bearer-token user for protected endpoints."""

    _ensure_tables()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    payload = _decode_token(authorization.split(" ", 1)[1])
    user = db.get(User, str(payload["sub"]))
    if not user and _is_development():
        email = str(payload.get("email") or "demo@ngx-intelligence.local").lower()
        user = User(
            id=str(payload["sub"]),
            email=email,
            hashed_password=_hash_password("RestoredDemo123"),
            full_name=email.split("@", 1)[0].replace(".", " ").title(),
            subscription_plan="institutional",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        _seed_demo_portfolio(db, user)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is suspended")
    return user


@router.post("/login")
def login(input: LoginRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    _ensure_tables()
    user = _verify_user(db, input.email, input.password)
    return _session_payload(user)


@router.post("/signup")
def signup(input: SignupRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    _ensure_tables()
    user = _create_user(db, input.email, input.password, input.name, input.organization)
    return _session_payload(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict[str, object]:
    return _user_payload(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> None:
    return None


@router.post("/forgot-password")
def forgot_password(input: ForgotPasswordRequest) -> dict[str, str]:
    return {"message": f"If {input.email} matches an account, reset instructions will be sent shortly."}


def _seed_demo_portfolio(db: Session, user: User) -> None:
    """Create local demo holdings so portfolio intelligence has real prices to analyze."""

    if not _is_development() or user.is_superuser:
        return
    existing = db.query(PortfolioPosition).filter(PortfolioPosition.user_id == user.id).first()
    if existing:
        return
    demo_positions = [
        ("ZENITHBANK", 1200.0, 118.0),
        ("GTCO", 900.0, 68.0),
        ("VIT", 120.0, 150.0),
        ("7UP", 80.0, 110.0),
        ("ZAI", 350.0, 31.0),
    ]
    for ticker, quantity, average_cost in demo_positions:
        db.add(
            PortfolioPosition(
                user_id=user.id,
                ticker=ticker,
                quantity=quantity,
                average_cost=average_cost,
            )
        )
    db.commit()
