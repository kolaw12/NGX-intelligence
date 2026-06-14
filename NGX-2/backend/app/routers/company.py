"""Company intelligence endpoints — profile and news per ticker."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from app.db.crud import canonical_ticker
from app.services.fundamentals_service import latest_company_record
from app.services.news_sentiment import (
    latest_package_breakdown_for_ticker,
    latest_sentiment_for_ticker,
)

router = APIRouter(tags=["company"])


@router.get("/company/{ticker}/profile")
def get_company_profile(ticker: str) -> dict[str, Any]:
    """Return real company profile data for a ticker, or a clear unavailable message."""

    canonical = canonical_ticker(ticker.upper().strip())
    record = latest_company_record(canonical)

    if record.source == "unavailable" or not record.values:
        return {
            "ticker": canonical,
            "available": False,
            "message": f"Company profile unavailable for {canonical}. Profile data covers the top 35 NGX companies.",
        }

    v = record.values
    return {
        "ticker": canonical,
        "available": True,
        "company_name": v.get("company_name"),
        "description": v.get("description"),
        "business_model": v.get("business_model"),
        "sector": v.get("sector"),
        "industry": v.get("industry"),
        "founded": v.get("founded"),
        "headquarters": v.get("headquarters"),
        "employees": v.get("employees"),
        "ceo": v.get("ceo"),
        "website": v.get("website"),
        "key_risks": v.get("key_risks") or [],
        "data_source": record.source,
        "last_updated": datetime.now(timezone.utc).date().isoformat(),
    }


@router.get("/company/{ticker}/news")
def get_company_news(ticker: str) -> dict[str, Any]:
    """Return recent news articles for a ticker with per-article sentiment."""

    canonical = canonical_ticker(ticker.upper().strip())
    sentiment = latest_sentiment_for_ticker(canonical)
    articles = latest_package_breakdown_for_ticker(canonical) or []

    enriched = []
    for article in articles:
        score = float(article.get("sentiment_score", 0.0) or 0.0)
        if score > 0.1:
            sentiment_label = "positive"
            possible_impact = "Potential upward price pressure"
        elif score < -0.1:
            sentiment_label = "negative"
            possible_impact = "Potential downward price pressure"
        else:
            sentiment_label = "neutral"
            possible_impact = "Limited directional price impact expected"
        enriched.append({
            "title": article.get("title") or article.get("headline"),
            "url": article.get("url") or article.get("link"),
            "published_at": article.get("date") or article.get("published_at"),
            "source": article.get("source"),
            "sentiment_score": round(score, 3),
            "sentiment_label": sentiment_label,
            "possible_impact": possible_impact,
            "summary": article.get("summary") or article.get("snippet"),
        })

    if not enriched:
        return {
            "ticker": canonical,
            "news": [],
            "ticker_sentiment_score": round(sentiment.score, 3),
            "ticker_sentiment_label": sentiment.label,
            "message": f"No recent news articles found for {canonical}.",
        }

    return {
        "ticker": canonical,
        "news": enriched,
        "article_count": len(enriched),
        "ticker_sentiment_score": round(sentiment.score, 3),
        "ticker_sentiment_label": sentiment.label,
        "as_of": sentiment.as_of_date,
    }
