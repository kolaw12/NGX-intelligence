"""API bridge layer database foundation.

This module owns SQLAlchemy engine/session configuration for the FastAPI backend.
It connects environment configuration from `.env` to downstream routers, CRUD
helpers, Alembic migrations, and service-layer persistence.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)

load_dotenv()


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


def get_database_url() -> str:
    """Return the configured database URL or a development SQLite fallback."""

    database_url = os.getenv("DATABASE_URL", "").strip()
    env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()

    if database_url:
        logger.info("Database URL loaded from environment")
        return database_url

    if env in {"development", "test", "testing"}:
        fallback_url = "sqlite:///./ngx_ai_dev.db"
        logger.warning(
            "DATABASE_URL is not set; using local SQLite fallback for %s environment",
            env,
        )
        return fallback_url

    raise RuntimeError("DATABASE_URL must be set for non-development environments")


def _connect_args(database_url: str) -> dict[str, object]:
    """Return SQLAlchemy connect args required by the active database driver."""

    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


DATABASE_URL = get_database_url()
engine: Engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=_connect_args(DATABASE_URL),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for FastAPI dependency injection."""

    db = SessionLocal()
    try:
        logger.info("Opening database session")
        yield db
    except Exception:
        logger.exception("Database session failed")
        db.rollback()
        raise
    finally:
        logger.info("Closing database session")
        db.close()


def init_dev_database() -> None:
    """Create tables for local development only.

    Production deployments should use Alembic migrations instead of this helper.
    """

    env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
    if env not in {"development", "test", "testing"}:
        raise RuntimeError("init_dev_database() is only allowed in development/testing")

    logger.warning("Creating database tables through Base.metadata for local development")
    Base.metadata.create_all(bind=engine)
