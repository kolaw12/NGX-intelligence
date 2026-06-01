"""FastAPI API bridge for the NGX AI Advisor backend.

This module wires CORS, health checks, stock data routes, and recommendation
routes so the existing React frontend can consume live backend data.
"""

from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv
from fastapi import Request
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.routers import account, admin, auth, engine, market, news, predict, recommendations, stocks, user_data
from app.db.database import init_dev_database
from app.services.backend_model_config import get_backend_model_config
from app.services.xgboost_predictor import warmup_xgboost

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(title="NGX AI Advisor API", version="0.1.0")
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://ngx-ai-advisor.vercel.app",
        "https://ngx-intelligence.vercel.app",
    ]
    frontend_url = os.getenv("FRONTEND_URL")
    if frontend_url and frontend_url not in allowed_origins:
        allowed_origins.append(frontend_url)
    frontend_urls = [origin.strip() for origin in os.getenv("FRONTEND_URLS", "").split(",") if origin.strip()]
    for origin in frontend_urls:
        if origin not in allowed_origins:
            allowed_origins.append(origin)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.middleware("http")
    async def _request_timing(request: Request, call_next):
        """Log slow API requests without exposing timings to users."""

        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
        if elapsed_ms >= 500:
            logger.warning("slow request %s %s %.1fms", request.method, request.url.path, elapsed_ms)
        else:
            logger.info("request %s %s %.1fms", request.method, request.url.path, elapsed_ms)
        return response
    app.include_router(stocks.router)
    app.include_router(recommendations.router)
    app.include_router(news.router)
    app.include_router(engine.router, prefix="/api")
    app.include_router(predict.router, prefix="/api")
    app.include_router(auth.router)
    app.include_router(account.router)
    app.include_router(admin.router)
    app.include_router(market.router)
    app.include_router(user_data.router)
    app.include_router(stocks.router, prefix="/api/v1")
    app.include_router(recommendations.router, prefix="/api/v1")
    app.include_router(news.router, prefix="/api/v1")
    app.include_router(engine.router, prefix="/api/v1")
    app.include_router(predict.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(account.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(market.router, prefix="/api/v1")
    app.include_router(user_data.router, prefix="/api/v1")
    logger.info("NGX AI Advisor API configured with CORS origins: %s", allowed_origins)

    @app.on_event("startup")
    def _startup() -> None:
        """Initialize local development tables; production should run Alembic."""

        env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
        if env in {"development", "test", "testing"}:
            init_dev_database()
        try:
            metadata = warmup_xgboost()
            config = get_backend_model_config()
            logger.info(
                "XGBoost ready: model=%s feature_list=%s feature_count=%s use_lstm=%s",
                metadata["model"],
                metadata["feature_list"],
                metadata["feature_count"],
                config.get("use_lstm", False),
            )
        except Exception as exc:
            logger.error("XGBoost startup warmup failed: %s", exc)

    return app


app = create_app()


@app.get("/health")
@app.get("/api/v1/health")
def health() -> dict[str, str]:
    """Return API health status."""

    return {"status": "ok", "service": "ngx-ai-advisor-api"}
