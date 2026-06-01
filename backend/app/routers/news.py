"""News and local NLP endpoints for processed article data."""

from __future__ import annotations

import hashlib
import re
from typing import Any

import pandas as pd
from fastapi import APIRouter, Query

from app.db.crud import canonical_ticker, public_ticker
from app.services.news_sentiment import (
    analyze_text,
    build_daily_sentiment_summary,
    extractive_summary,
    load_daily_sentiment_summary,
    load_news_articles,
    save_daily_sentiment_summary,
    valid_public_tickers,
)

router = APIRouter(tags=["news"])

@router.get("/news")
def list_news(symbol: str | None = Query(default=None), limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, Any]]:
    """Return processed news articles enriched with local NLP features."""

    articles = load_news_articles()
    if articles.empty:
        return []

    requested_symbol = public_ticker(canonical_ticker(symbol)) if symbol else None
    if symbol:
        canonical = canonical_ticker(symbol)
        articles = articles[
            articles["mentioned_tickers"].apply(lambda tickers: canonical in tickers or public_ticker(canonical) in tickers)
        ]

    articles = articles.sort_values("published_date", ascending=False).head(limit * 3)
    payloads = [_article_payload(row, requested_symbol=requested_symbol) for _, row in articles.iterrows()]
    if not symbol:
        payloads = [
            article
            for article in payloads
            if _is_market_relevant(article)
        ]
    return payloads[:limit]


@router.get("/news/sentiment-summary")
def sentiment_summary(symbol: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=500)) -> list[dict[str, Any]]:
    """Return daily ticker sentiment rows used by the recommendation layer."""

    summary = load_daily_sentiment_summary()
    if summary.empty:
        return []
    if symbol:
        canonical = canonical_ticker(symbol)
        summary = summary[summary["ticker"].astype(str).str.upper() == canonical]
    summary = summary.sort_values(["date", "ticker"], ascending=[False, True]).head(limit)
    return [
        {
            "date": pd.to_datetime(row["date"]).date().isoformat(),
            "symbol": public_ticker(str(row["ticker"])),
            "sentimentScore": round(float(row["avg_sentiment"]), 3),
            "sentiment": "positive" if float(row["avg_sentiment"]) > 0.05 else "negative" if float(row["avg_sentiment"]) < -0.05 else "neutral",
            "positiveCount": int(row["positive_count"]),
            "negativeCount": int(row["negative_count"]),
            "neutralCount": int(row["neutral_count"]),
            "totalArticles": int(row["total_articles"]),
        }
        for _, row in summary.iterrows()
    ]


@router.get("/news/sentiment-diagnostics")
def sentiment_diagnostics() -> dict[str, Any]:
    """Return real NLP data availability so the UI can distinguish fallback sentiment."""

    articles = load_news_articles()
    summary = load_daily_sentiment_summary()
    latest_article_date = None
    latest_summary_date = None
    if not articles.empty and "published_date" in articles.columns:
        latest_article_date = pd.to_datetime(articles["published_date"], errors="coerce").max()
    if not summary.empty and "date" in summary.columns:
        latest_summary_date = pd.to_datetime(summary["date"], errors="coerce").max()
    return {
        "source": "nlp_engine" if not summary.empty else "neutral_fallback",
        "articlesLoaded": int(len(articles)),
        "summaryRows": int(len(summary)),
        "tickersCovered": int(summary["ticker"].nunique()) if not summary.empty and "ticker" in summary.columns else 0,
        "latestArticleDate": latest_article_date.isoformat() if pd.notna(latest_article_date) else None,
        "latestSummaryDate": latest_summary_date.date().isoformat() if pd.notna(latest_summary_date) else None,
        "fallbackActive": bool(summary.empty),
    }


@router.post("/news/rebuild-sentiment")
def rebuild_sentiment_summary() -> dict[str, Any]:
    """Rebuild ticker sentiment summary after news ingestion."""

    load_news_articles.cache_clear()
    load_daily_sentiment_summary.cache_clear()
    summary = build_daily_sentiment_summary()
    save_daily_sentiment_summary(summary)
    load_daily_sentiment_summary.cache_clear()
    return {
        "status": "ok",
        "rows": int(len(summary)),
        "tickers": int(summary["ticker"].nunique()) if not summary.empty else 0,
    }


def _article_payload(row: pd.Series, requested_symbol: str | None = None) -> dict[str, Any]:
    """Map a processed article row to the frontend NewsItem contract."""

    headline = str(row.get("headline", "")).strip()
    url = str(row.get("url", "")).strip()
    source = str(row.get("source", "news")).strip() or "news"
    article_text = str(row.get("article_text", "")).strip()
    tickers = valid_public_tickers(row.get("mentioned_tickers", []))
    symbol = requested_symbol or (public_ticker(str(tickers[0])) if tickers else None)
    analysis = analyze_text(f"{headline} {article_text}", tickers=tickers)
    return {
        "id": hashlib.sha1(f"{source}|{url}|{headline}".encode("utf-8")).hexdigest()[:16],
        "symbol": symbol,
        "mentionedTickers": tickers,
        "headline": headline,
        "source": source,
        "publishedAt": pd.to_datetime(row.get("published_date")).isoformat(),
        "url": url,
        "sentiment": analysis.label,
        "sentimentScore": round(analysis.score, 3),
        "relevanceScore": analysis.relevance_score,
        "eventTags": analysis.event_tags,
        "summary": extractive_summary(article_text, headline=headline),
    }


def _is_market_relevant(article: dict[str, Any]) -> bool:
    """Filter generic/sports/politics articles from the general market feed."""

    if article["mentionedTickers"]:
        return True
    headline = str(article.get("headline", "")).lower()
    finance_terms = {
        "bank",
        "market",
        "ngx",
        "stock",
        "shares",
        "tax",
        "profit",
        "revenue",
        "inflation",
        "naira",
        "rate",
        "rates",
        "oil",
        "debt",
        "bond",
        "dividend",
        "earnings",
    }
    if not any(term in re.findall(r"\w+", headline) for term in finance_terms):
        return False
    return float(article.get("relevanceScore", 0.0)) >= 0.2
