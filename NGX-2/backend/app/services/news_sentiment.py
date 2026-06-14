"""Lightweight news sentiment from the pulled NLP/data pipeline.

The current NLP branch provides lexicon-based article scoring and a daily
ticker sentiment summary. This service exposes the same idea to the API layer
without introducing a separate NLP microservice yet.
"""

from __future__ import annotations

import ast
import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from app.db.crud import canonical_ticker, load_tickers, public_ticker

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NEWS_ARTICLES_DIR = PROJECT_ROOT / "data" / "output" / "processed" / "news" / "articles"
SENTIMENT_SUMMARY_PATH = PROJECT_ROOT / "data" / "output" / "processed" / "news" / "daily_sentiment_summary.parquet"
SENTIMENT_PACKAGE_GLOB = "nupat_daily_package_*.json"

SENTIMENT_COLUMNS = [
    "date",
    "ticker",
    "avg_sentiment",
    "positive_count",
    "negative_count",
    "neutral_count",
    "total_articles",
    "ingested_at",
]

POSITIVE_WORDS = {
    "good",
    "great",
    "positive",
    "up",
    "gain",
    "strong",
    "bull",
    "surge",
    "beat",
    "improve",
    "growth",
    "rise",
    "record",
    "win",
    "benefit",
    "profit",
    "profits",
    "upgrade",
    "dividend",
    "expansion",
    "resilient",
    "improved",
    "outperform",
    "approval",
    "approved",
    "award",
    "contract",
    "listing",
    "oversubscribed",
    "recovery",
    "stable",
}
NEGATIVE_WORDS = {
    "bad",
    "poor",
    "negative",
    "down",
    "loss",
    "weak",
    "bear",
    "drop",
    "miss",
    "decline",
    "fall",
    "risks",
    "challenge",
    "worse",
    "pain",
    "losses",
    "downgrade",
    "bearish",
    "default",
    "delay",
    "penalty",
    "sanction",
    "suspend",
    "suspended",
    "warning",
    "impairment",
    "debt",
}
INTENSIFIERS = {
    "very",
    "significant",
    "significantly",
    "major",
    "sharp",
    "strongly",
    "material",
    "materially",
}
NEGATIONS = {
    "not",
    "no",
    "never",
    "without",
    "hardly",
    "barely",
    "neither",
    "nor",
}

# Words that indicate catastrophic or criminal events — model confidence must be reduced
CRITICAL_SEVERITY_WORDS: frozenset[str] = frozenset({
    "fraud", "fraudulent", "arrested", "arraigned", "convicted", "criminal",
    "efcc", "icpc", "laundering", "embezzlement", "bribery", "corrupt", "forgery",
    "delisted", "delisting", "suspended",
    "winding", "liquidation", "bankrupt", "insolvency", "insolvent", "receivership",
    "revoked", "revocation", "seized",
    "falsified", "restatement", "manipulation",
})

# Words indicating high-impact but non-catastrophic events
HIGH_SEVERITY_WORDS: frozenset[str] = frozenset({
    "sanction", "sanctioned", "penalized", "penalty", "fined", "investigated",
    "investigation", "probe", "injunction", "lawsuit", "litigation",
    "default", "defaulted", "covenant", "negative_equity", "going_concern",
    "material_weakness", "impairment",
    "resigned", "sacked", "dismissed", "terminated", "ousted",
    "fire", "explosion", "cyberattack", "shutdown",
    "omitted", "cancelled", "withheld",
})
EVENT_KEYWORDS = {
    "earnings": {"earnings", "profit", "profits", "profitability", "revenue", "results", "quarter", "audited"},
    "dividend": {"dividend", "bonus", "payout", "distribution"},
    "corporate_action": {"rights", "issue", "listing", "delisting", "merger", "acquisition", "restructuring"},
    "regulatory": {"ngx", "sec", "cbn", "approval", "approved", "sanction", "compliance", "suspend", "suspended"},
    "debt_capital": {"bond", "debt", "commercial", "paper", "notes", "coupon", "maturity"},
    "macro": {"inflation", "rate", "rates", "fx", "naira", "oil", "monetary", "policy", "tax", "taxation"},
}


@dataclass(frozen=True)
class SentimentSignal:
    """Latest available ticker sentiment summary."""

    score: float
    label: str
    total_articles: int
    as_of_date: str | None
    source: str = "neutral_fallback"


@dataclass(frozen=True)
class NLPAnalysis:
    """Article-level NLP features used by API responses and summaries."""

    score: float
    label: str
    positive_hits: int
    negative_hits: int
    event_tags: list[str]
    relevance_score: float


def score_text(text: str) -> float:
    """Return an NLP sentiment score between -1 and 1."""

    return analyze_text(text).score


def analyze_text(text: str, tickers: list[str] | None = None) -> NLPAnalysis:
    """Analyze article text using local financial lexicons and event tags."""

    if not isinstance(text, str) or not text.strip():
        return NLPAnalysis(0.0, "neutral", 0, 0, [], 0.0)
    tokens = re.findall(r"\w+", text.lower())
    if not tokens:
        return NLPAnalysis(0.0, "neutral", 0, 0, [], 0.0)

    weighted_score = 0.0
    positive_hits = 0
    negative_hits = 0
    for index, token in enumerate(tokens):
        base = 0.0
        if token in POSITIVE_WORDS:
            base = 1.0
            positive_hits += 1
        elif token in NEGATIVE_WORDS:
            base = -1.0
            negative_hits += 1
        if not base:
            continue

        window = tokens[max(0, index - 3) : index]
        if any(word in NEGATIONS for word in window):
            base *= -1
        if any(word in INTENSIFIERS for word in window):
            base *= 1.4
        weighted_score += base

    event_tags = [
        event
        for event, keywords in EVENT_KEYWORDS.items()
        if any(token in keywords for token in tokens)
    ]
    evidence_count = positive_hits + negative_hits
    score = 0.0 if evidence_count == 0 else weighted_score / max(evidence_count, 1)
    score = max(-1.0, min(1.0, score))
    relevance_score = _relevance_score(tokens, tickers or [], event_tags, evidence_count)
    if relevance_score < 0.2 and not event_tags:
        score = 0.0
    return NLPAnalysis(
        score=score,
        label=sentiment_label(score),
        positive_hits=positive_hits,
        negative_hits=negative_hits,
        event_tags=event_tags,
        relevance_score=relevance_score,
    )


def sentiment_label(score: float) -> str:
    """Map score to the frontend/news sentiment label."""

    if score > 0.05:
        return "positive"
    if score < -0.05:
        return "negative"
    return "neutral"


@lru_cache(maxsize=1)
def load_latest_sentiment_package() -> dict:
    """Load the newest JSON package exported by backend/app/nlp/sentiment_pipeline.py."""

    candidates = sorted(PROJECT_ROOT.glob(SENTIMENT_PACKAGE_GLOB), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            payload = json.loads(path.read_text())
            if isinstance(payload, dict):
                payload["_package_path"] = str(path)
                return payload
        except Exception as exc:
            logger.warning("Failed to read NLP sentiment package %s: %s", path, exc)
    return {}


def latest_package_sentiment_for_ticker(ticker: str) -> SentimentSignal | None:
    """Return ticker sentiment from the newest sentiment_pipeline.py JSON export."""

    package = load_latest_sentiment_package()
    if not package:
        return None
    canonical = canonical_ticker(ticker)
    for row in package.get("stock_sentiments", []) or []:
        row_ticker = canonical_ticker(str(row.get("ticker", "")))
        if row_ticker != canonical:
            continue
        score = _bounded_score(row.get("sentiment_score"))
        return SentimentSignal(
            score=score,
            label=sentiment_label(score),
            total_articles=int(row.get("article_count", 0) or 0),
            as_of_date=str(package.get("date")) if package.get("date") else None,
            source="sentiment_pipeline_json",
        )
    return None


def latest_market_package_sentiment() -> dict | None:
    """Return aggregate market sentiment from the newest sentiment_pipeline.py JSON export."""

    package = load_latest_sentiment_package()
    market = package.get("market_sentiment") if package else None
    if not isinstance(market, dict):
        return None
    score = _bounded_score(market.get("score"))
    signal = str(market.get("signal") or sentiment_label(score)).lower()
    return {
        "score": score,
        "signal": signal,
        "article_count": int(market.get("article_count", 0) or 0),
        "as_of_date": str(package.get("date")) if package.get("date") else None,
        "generated_at": package.get("generated_at"),
        "total_articles": int(package.get("total_articles", 0) or 0),
        "package_path": package.get("_package_path"),
    }


@lru_cache(maxsize=1)
def load_news_articles() -> pd.DataFrame:
    """Read all processed news article parquet files from disk."""

    if not NEWS_ARTICLES_DIR.exists():
        return pd.DataFrame(columns=["published_date", "source", "headline", "article_text", "url", "mentioned_tickers"])

    frames = []
    for path in sorted(NEWS_ARTICLES_DIR.glob("**/articles.parquet")):
        try:
            frame = pd.read_parquet(path)
            frame["mentioned_tickers"] = frame.get("mentioned_tickers", pd.Series([[]] * len(frame))).apply(
                coerce_mentioned_tickers
            )
            frame["published_date"] = pd.to_datetime(frame.get("published_date"), errors="coerce")
            frames.append(frame)
        except Exception as exc:
            logger.warning("Skipping unreadable news parquet %s: %s", path, exc)
    if not frames:
        return pd.DataFrame(columns=["published_date", "source", "headline", "article_text", "url", "mentioned_tickers"])
    articles = pd.concat(frames, ignore_index=True)
    return articles.dropna(subset=["published_date", "headline"]).fillna("")


@lru_cache(maxsize=1)
def load_daily_sentiment_summary() -> pd.DataFrame:
    """Load or build the daily ticker sentiment summary."""

    if SENTIMENT_SUMMARY_PATH.exists() and not _summary_is_stale():
        try:
            summary = pd.read_parquet(SENTIMENT_SUMMARY_PATH)
            summary["date"] = pd.to_datetime(summary["date"], errors="coerce")
            return summary
        except Exception as exc:
            logger.warning("Failed to read sentiment summary %s: %s", SENTIMENT_SUMMARY_PATH, exc)

    summary = build_daily_sentiment_summary()
    save_daily_sentiment_summary(summary)
    return summary


def build_daily_sentiment_summary() -> pd.DataFrame:
    """Summarize article sentiment per date and mentioned ticker."""

    articles = load_news_articles()
    if articles.empty or "published_date" not in articles.columns:
        return pd.DataFrame(columns=SENTIMENT_COLUMNS)

    articles = articles.copy()
    articles["published_date"] = pd.to_datetime(articles["published_date"], errors="coerce")
    articles = articles.dropna(subset=["published_date"])
    if articles.empty:
        return pd.DataFrame(columns=SENTIMENT_COLUMNS)

    articles["date"] = articles["published_date"].dt.date
    articles["mentioned_tickers"] = articles["mentioned_tickers"].apply(coerce_mentioned_tickers)
    articles = articles.explode("mentioned_tickers")
    articles["ticker"] = articles["mentioned_tickers"].astype(str).str.strip().str.upper()
    valid_tickers = _valid_tickers()
    articles["ticker"] = articles["ticker"].apply(canonical_ticker)
    if valid_tickers:
        articles = articles[articles["ticker"].isin(valid_tickers)]
    articles = articles[articles["ticker"].str.len() > 0]
    if articles.empty:
        return pd.DataFrame(columns=SENTIMENT_COLUMNS)

    headline = articles["headline"] if "headline" in articles.columns else pd.Series([""] * len(articles), index=articles.index)
    article_text = (
        articles["article_text"] if "article_text" in articles.columns else pd.Series([""] * len(articles), index=articles.index)
    )
    text_source = headline.fillna("").astype(str) + " " + article_text.fillna("").astype(str)
    analyses = [
        analyze_text(text, tickers=coerce_mentioned_tickers(tickers))
        for text, tickers in zip(text_source, articles["ticker"], strict=False)
    ]
    articles["sentiment_score"] = [analysis.score for analysis in analyses]

    summary = (
        articles.groupby(["date", "ticker"], dropna=False, as_index=False)
        .agg(
            avg_sentiment=("sentiment_score", "mean"),
            positive_count=("sentiment_score", lambda scores: int((scores > 0).sum())),
            negative_count=("sentiment_score", lambda scores: int((scores < 0).sum())),
            neutral_count=("sentiment_score", lambda scores: int((scores == 0).sum())),
            total_articles=("sentiment_score", "count"),
        )
        .sort_values(["ticker", "date"])
    )
    summary["ingested_at"] = pd.Timestamp.utcnow()
    summary["date"] = pd.to_datetime(summary["date"], errors="coerce")
    return summary[SENTIMENT_COLUMNS]


def save_daily_sentiment_summary(summary: pd.DataFrame) -> None:
    """Persist the daily ticker sentiment summary locally."""

    SENTIMENT_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_parquet(SENTIMENT_SUMMARY_PATH, index=False)
    logger.info("Wrote daily sentiment summary to %s", SENTIMENT_SUMMARY_PATH)


def latest_sentiment_for_ticker(ticker: str) -> SentimentSignal:
    """Return latest known sentiment for a ticker."""

    package_signal = latest_package_sentiment_for_ticker(ticker)
    if package_signal:
        return package_signal

    canonical = canonical_ticker(ticker)
    summary = load_daily_sentiment_summary()
    if summary.empty:
        return SentimentSignal(score=0.0, label="neutral", total_articles=0, as_of_date=None)
    ticker_rows = summary[summary["ticker"].astype(str).str.upper() == canonical].copy()
    if ticker_rows.empty:
        return SentimentSignal(score=0.0, label="neutral", total_articles=0, as_of_date=None)
    latest = ticker_rows.sort_values("date").iloc[-1]
    score = float(latest.get("avg_sentiment", 0.0) or 0.0)
    date_value = pd.to_datetime(latest.get("date"), errors="coerce")
    return SentimentSignal(
        score=max(-1.0, min(1.0, score)),
        label=sentiment_label(score),
        total_articles=int(latest.get("total_articles", 0) or 0),
        as_of_date=None if pd.isna(date_value) else date_value.date().isoformat(),
        source="daily_sentiment_summary",
    )


def _bounded_score(value: object) -> float:
    """Return a finite sentiment score clipped to the expected -1..1 range."""

    try:
        parsed = float(value)
        if np.isfinite(parsed):
            return max(-1.0, min(1.0, parsed))
    except (TypeError, ValueError):
        pass
    return 0.0


def coerce_mentioned_tickers(value: object) -> list[str]:
    """Normalize mentioned ticker values from parquet object columns."""

    if isinstance(value, list):
        return [str(ticker).strip().upper() for ticker in value if str(ticker).strip()]
    if isinstance(value, tuple):
        return [str(ticker).strip().upper() for ticker in value if str(ticker).strip()]
    if isinstance(value, np.ndarray) or hasattr(value, "tolist"):
        return coerce_mentioned_tickers(value.tolist())
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        if value.startswith("[") and value.endswith("]"):
            try:
                parsed = ast.literal_eval(value)
                if isinstance(parsed, list):
                    return coerce_mentioned_tickers(parsed)
            except Exception:
                pass
        return [ticker.strip().upper() for ticker in re.split(r"[;,|]", value) if ticker.strip()]
    if value is None:
        return []
    try:
        if pd.isna(value):
            return []
    except ValueError:
        pass
    return [str(value).strip().upper()] if str(value).strip() else []


def valid_public_tickers(values: object) -> list[str]:
    """Return only real NGX tickers from raw article metadata."""

    valid = _valid_tickers()
    output: list[str] = []
    for ticker in coerce_mentioned_tickers(values):
        canonical = canonical_ticker(ticker)
        if canonical in valid:
            output.append(public_ticker(canonical))
    return sorted(set(output))


def extractive_summary(text: str, headline: str = "", max_chars: int = 260) -> str:
    """Return a short article summary biased toward finance/event sentences."""

    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return ""
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", cleaned) if sentence.strip()]
    if not sentences:
        return cleaned[:max_chars].rstrip()
    ranked = sorted(
        sentences,
        key=lambda sentence: _sentence_weight(sentence, headline),
        reverse=True,
    )
    summary = ranked[0]
    if len(summary) > max_chars:
        return summary[: max_chars - 3].rstrip() + "..."
    return summary


def _sentence_weight(sentence: str, headline: str = "") -> float:
    """Rank sentences for extractive summaries."""

    tokens = re.findall(r"\w+", sentence.lower())
    headline_tokens = set(re.findall(r"\w+", headline.lower()))
    analysis = analyze_text(sentence)
    event_hits = sum(1 for event, words in EVENT_KEYWORDS.items() for token in tokens if token in words)
    overlap = sum(1 for token in tokens if token in headline_tokens)
    return event_hits * 2 + abs(analysis.score) * 2 + analysis.positive_hits + analysis.negative_hits + overlap * 0.25


def _relevance_score(tokens: list[str], tickers: list[str], event_tags: list[str], evidence_count: int) -> float:
    """Estimate whether an article contains useful market-moving context."""

    ticker_bonus = min(len([ticker for ticker in tickers if ticker]) * 0.25, 0.5)
    event_bonus = min(len(event_tags) * 0.15, 0.3)
    evidence_bonus = min(evidence_count * 0.05, 0.2)
    length_bonus = 0.1 if len(tokens) >= 80 else 0.0
    return round(max(0.0, min(1.0, ticker_bonus + event_bonus + evidence_bonus + length_bonus)), 3)


def _summary_is_stale() -> bool:
    """Return true when article parquet files are newer than the summary."""

    summary_mtime = SENTIMENT_SUMMARY_PATH.stat().st_mtime
    for path in NEWS_ARTICLES_DIR.glob("**/articles.parquet"):
        if path.stat().st_mtime > summary_mtime:
            return True
    return False


@lru_cache(maxsize=1)
def _valid_tickers() -> set[str]:
    """Return canonical tickers from master metadata."""

    try:
        return set(load_tickers()["ticker"].astype(str).str.upper().str.strip())
    except Exception as exc:
        logger.warning("Could not load ticker master for news NLP validation: %s", exc)
        return set()


def latest_package_breakdown_for_ticker(ticker: str) -> list[dict] | None:
    """Return per-headline sentiment breakdown from the newest sentiment_pipeline.py JSON export."""

    package = load_latest_sentiment_package()
    if not package:
        return None
    canonical = canonical_ticker(ticker)
    for row in package.get("stock_sentiments", []) or []:
        row_ticker = canonical_ticker(str(row.get("ticker", "")))
        if row_ticker != canonical:
            continue
        return [
            {
                "headline"     : item.get("headline", ""),
                "originalHeadline": item.get("original_headline", ""),
                "sentiment"    : item.get("sentiment", "neutral"),
                "confidence"   : float(item.get("confidence", 0.0) or 0.0),
                "score"        : float(item.get("score", 0.0) or 0.0),
                "source"       : item.get("source", ""),
                "url"          : item.get("url", ""),
            }
            for item in row.get("breakdown", [])
        ]
    return None


def latest_package_momentum_for_ticker(ticker: str) -> dict | None:
    """Return momentum / rolling-average context for one ticker from the newest package."""

    package = load_latest_sentiment_package()
    if not package:
        return None
    canonical = canonical_ticker(ticker)
    for row in package.get("stock_sentiments", []) or []:
        row_ticker = canonical_ticker(str(row.get("ticker", "")))
        if row_ticker != canonical:
            continue
        return {
            "ticker"          : canonical,
            "momentum"        : float(row.get("momentum", 0.0) or 0.0),
            "momentum_signal" : str(row.get("momentum_signal", "NEUTRAL") or "NEUTRAL"),
            "rolling_avg_7d"  : _safe_optional_float(row.get("rolling_avg_7d")),
            "rolling_avg_30d" : _safe_optional_float(row.get("rolling_avg_30d")),
            "trend_direction" : str(row.get("trend_direction", "flat") or "flat"),
            "as_of_date"      : str(package.get("date")) if package.get("date") else None,
            "sentiment_score" : float(row.get("sentiment_score", 0.0) or 0.0),
            "signal"          : str(row.get("signal", "NEUTRAL") or "NEUTRAL"),
            "article_count"   : int(row.get("article_count", 0) or 0),
        }
    return None


def load_sentiment_history_for_ticker(ticker: str, category: str = "stock", days: int = 30) -> pd.DataFrame:
    """Return recent historical sentiment rows for one ticker."""

    from pathlib import Path
    history_path = (
        Path(__file__).resolve().parents[2]
        / "backend" / "app" / "nlp"
        / "historical_sentiment.parquet"
    )
    if not history_path.exists():
        return pd.DataFrame(columns=["date", "ticker", "sentiment_score", "signal", "article_count", "category"])
    try:
        df = pd.read_parquet(history_path)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df = df[df["category"] == category]
        df = df[df["ticker"].str.upper() == canonical_ticker(ticker)]
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)
        df = df[df["date"] >= cutoff]
        return df.sort_values("date").reset_index(drop=True)
    except Exception as exc:
        logger.warning("Failed to load sentiment history for %s: %s", ticker, exc)
        return pd.DataFrame(columns=["date", "ticker", "sentiment_score", "signal", "article_count", "category"])


def detect_high_severity_events_for_ticker(ticker: str) -> tuple[str, list[str]]:
    """Scan the latest news package for catastrophic or high-impact event signals.

    Returns:
        (severity_level, list_of_triggered_descriptions)

        severity_level is one of:
          "CRITICAL" — criminal, delisting, insolvency, fraud (override BUY/SELL → HOLD)
          "HIGH"     — regulatory action, default, executive shock (suppress BUY)
          "NORMAL"   — no high-impact events detected
    """
    package = load_latest_sentiment_package()
    if not package:
        return "NORMAL", []

    canonical = canonical_ticker(ticker)
    headlines: list[str] = []
    for row in package.get("stock_sentiments", []) or []:
        if canonical_ticker(str(row.get("ticker", ""))) != canonical:
            continue
        for item in row.get("breakdown", []) or []:
            h = str(item.get("headline", "") or "").strip()
            if h:
                headlines.append(h)
        break

    if not headlines:
        return "NORMAL", []

    triggered_critical: list[str] = []
    triggered_high: list[str] = []

    for headline in headlines:
        tokens = set(re.findall(r"\w+", headline.lower()))
        crit_hits = tokens & CRITICAL_SEVERITY_WORDS
        high_hits = tokens & HIGH_SEVERITY_WORDS
        short = headline[:100]
        if crit_hits:
            triggered_critical.append(f"{short!r} — keywords: {', '.join(sorted(crit_hits))}")
        elif high_hits:
            triggered_high.append(f"{short!r} — keywords: {', '.join(sorted(high_hits))}")

    if triggered_critical:
        return "CRITICAL", triggered_critical
    if triggered_high:
        return "HIGH", triggered_high
    return "NORMAL", []


def _safe_optional_float(value: object) -> float | None:
    """Return a float if the value is parseable, otherwise None."""

    try:
        parsed = float(value)
        if not pd.isna(parsed) and pd.isfinite(parsed):
            return float(parsed)
    except (TypeError, ValueError):
        pass
    return None
