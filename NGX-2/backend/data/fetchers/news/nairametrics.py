"""
Fetcher for Nairametrics articles — NGX-focused business news.

Uses RSS feeds (explicitly allowed by robots.txt for aggregation) so we
never hammer the site with HTML scraping. Nairametrics publishes per-category
RSS that gives us title, link, pubDate, and a full <content:encoded> body.

RSS feeds used:
  - /category/ngx-market/feed/         — NGX stock market news
  - /category/company-news/feed/       — company-specific coverage
  - /category/money-market/feed/       — bonds, T-bills, CBN decisions
  - /category/banking-financial/feed/  — banks and financial services

No credentials required. No paywalled content — all RSS items are free.
Polite delay between feed fetches. robots.txt verified 2026-06-11: RSS/feed
paths are NOT disallowed; only admin/wp-login/xmlrpc paths are blocked.
"""

from __future__ import annotations

import datetime as _dt
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from html import unescape

import pandas as pd

# pyrefly: ignore [missing-import]
from loguru import logger

from .base import NewsFetcherBase, ARTICLE_COLUMNS

# Nigeria (West Africa Time) = UTC+1, no DST
WAT = _dt.timezone(_dt.timedelta(hours=1))

# RSS namespaces used by WordPress
_NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc":      "http://purl.org/dc/elements/1.1/",
    "atom":    "http://www.w3.org/2005/Atom",
}

# Load the canonical NGX ticker list once
_TICKERS_CSV = Path("data/master/tickers.csv")


def _load_ticker_set() -> set[str]:
    """Return a set of canonical NGX tickers for mention matching."""
    try:
        df = pd.read_csv(_TICKERS_CSV)
        return set(str(t).upper().strip() for t in df["ticker"] if str(t).strip())
    except Exception as exc:
        logger.warning("NairametricsFetcher: could not load tickers.csv: %s", exc)
        return set()


# Short/ambiguous tokens that are also common English words — skip them to
# avoid false ticker matches (e.g. "MAY", "ALL", "FX").
_SKIP_TOKENS = {
    "THE", "AND", "FOR", "PLC", "CEO", "CFO", "NGX", "NSE", "AGM", "EGM",
    "USD", "NGN", "GDP", "FY", "Q1", "Q2", "Q3", "Q4", "ALL", "MAY", "ICE",
    "AIR", "RED", "SUN", "BIG", "ETI", "NB", "NA", "FX", "IT",
}


def _extract_tickers(text: str, ticker_set: set[str]) -> list[str]:
    """Return NGX tickers mentioned in text (conservative exact-match only)."""
    if not text or not ticker_set:
        return []
    tokens = set(re.findall(r"\b[A-Z]{2,12}\b", text.upper()))
    hits = (tokens & ticker_set) - _SKIP_TOKENS
    return sorted(hits)


def _strip_html(html: str) -> str:
    """Strip HTML tags and decode entities to get plain text."""
    if not html:
        return ""
    # Remove script/style blocks entirely
    html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all remaining tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Decode HTML entities
    text = unescape(text)
    # Collapse whitespace
    return re.sub(r"\s+", " ", text).strip()


def _parse_rss_date(date_str: str) -> _dt.datetime | None:
    """Parse RSS pubDate format: 'Wed, 11 Jun 2026 12:00:00 +0000'."""
    if not date_str:
        return None
    # Try the standard RSS date formats
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
    ):
        try:
            return _dt.datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    logger.warning("NairametricsFetcher: unrecognised date format: %r", date_str)
    return None


class NairametricsFetcher(NewsFetcherBase):
    """Fetch Nairametrics articles via RSS — no HTML scraping required."""

    SOURCE_ID = "nairametrics"
    BASE_URL  = "https://nairametrics.com"

    RSS_FEEDS = [
        f"{BASE_URL}/category/ngx-market/feed/",
        f"{BASE_URL}/category/company-news/feed/",
        f"{BASE_URL}/category/money-market/feed/",
        f"{BASE_URL}/category/banking-financial/feed/",
    ]

    # Max items to pull from each individual feed per run.
    MAX_ITEMS_PER_FEED = 50

    def fetch_articles(
        self,
        since_date: _dt.datetime | None = None,
        max_articles: int | None = None,
    ) -> pd.DataFrame:
        """Fetch articles from all configured RSS feeds and return a DataFrame."""

        ticker_set = _load_ticker_set()
        rows: list[dict] = []
        seen_urls: set[str] = set()

        for feed_url in self.RSS_FEEDS:
            try:
                feed_rows = self._fetch_feed(feed_url, since_date, ticker_set, seen_urls)
                rows.extend(feed_rows)
                logger.info(
                    "NairametricsFetcher: %s → %d new articles (total so far: %d)",
                    feed_url, len(feed_rows), len(rows),
                )
            except Exception as exc:
                logger.warning("NairametricsFetcher: error fetching %s: %s", feed_url, exc)

            if max_articles and len(rows) >= max_articles:
                rows = rows[:max_articles]
                break

        if not rows:
            logger.warning("NairametricsFetcher: no articles fetched from any feed")
            return pd.DataFrame(columns=ARTICLE_COLUMNS)

        df = pd.DataFrame(rows, columns=ARTICLE_COLUMNS)
        df["published_date"] = pd.to_datetime(df["published_date"], utc=True, errors="coerce")
        df = df.dropna(subset=["published_date", "headline"])
        df = df.sort_values("published_date", ascending=False).reset_index(drop=True)
        logger.success(
            "NairametricsFetcher: collected %d articles (%s → %s)",
            len(df),
            df["published_date"].min(),
            df["published_date"].max(),
        )
        return df

    def _fetch_feed(
        self,
        feed_url: str,
        since_date: _dt.datetime | None,
        ticker_set: set[str],
        seen_urls: set[str],
    ) -> list[dict]:
        """Fetch and parse one RSS feed, returning article rows."""
        response = self._polite_get(feed_url)
        if not response or not response.text:
            return []

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            logger.warning("NairametricsFetcher: XML parse error for %s: %s", feed_url, exc)
            return []

        channel = root.find("channel")
        if channel is None:
            return []

        rows = []
        for item in channel.findall("item")[: self.MAX_ITEMS_PER_FEED]:
            try:
                row = self._parse_item(item, ticker_set, since_date, seen_urls)
                if row:
                    rows.append(row)
                    seen_urls.add(row["url"])
            except Exception as exc:
                logger.debug("NairametricsFetcher: skipping item due to error: %s", exc)
        return rows

    def _parse_item(
        self,
        item: ET.Element,
        ticker_set: set[str],
        since_date: _dt.datetime | None,
        seen_urls: set[str],
    ) -> dict | None:
        """Extract one article dict from an RSS <item> element."""
        url = (item.findtext("link") or "").strip()
        if not url or url in seen_urls:
            return None

        headline = _strip_html(item.findtext("title") or "").strip()
        if not headline:
            return None

        pub_date_str = item.findtext("pubDate") or ""
        published = _parse_rss_date(pub_date_str)
        if published is None:
            return None

        # Apply since_date filter (compare timezone-aware)
        if since_date is not None:
            sd = since_date if since_date.tzinfo else since_date.replace(tzinfo=_dt.timezone.utc)
            pub_utc = published.astimezone(_dt.timezone.utc)
            if pub_utc < sd:
                return None

        # Prefer full content over truncated description
        content_el = item.find("content:encoded", _NS)
        if content_el is not None and content_el.text:
            article_text = _strip_html(content_el.text)
        else:
            description = item.findtext("description") or ""
            article_text = _strip_html(description)

        # Match NGX tickers from headline + body
        combined_text = f"{headline} {article_text}"
        mentioned = _extract_tickers(combined_text, ticker_set)

        return {
            "published_date": published,
            "source": self.SOURCE_ID,
            "headline": headline,
            "article_text": article_text[:8000],  # cap per article
            "url": url,
            "mentioned_tickers": mentioned,
        }

    def run(
        self,
        since_date: _dt.datetime | None = None,
        max_articles: int | None = None,
    ) -> list:
        """Fetch articles and write one parquet file per year."""
        df = self.fetch_articles(since_date=since_date, max_articles=max_articles)
        if df.empty:
            return []
        written = []
        for year in sorted(int(y) for y in df["published_date"].dt.year.dropna().unique()):
            written.append(
                self.write_parquet(df[df["published_date"].dt.year == year], year)
            )
        return written
