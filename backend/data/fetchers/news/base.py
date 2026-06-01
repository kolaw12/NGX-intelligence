"""
Base class for all news fetchers.

Every news source fetcher (Nairametrics, BusinessDay, NGX announcements, etc.)
should inherit from `NewsFetcherBase` and implement `fetch_articles()`.

The base class provides:
  - Session management with a polite user-agent
  - Killswitch support (touch `data/.killswitch` to abort the next request)
  - Per-run request cap (so a runaway fetcher can't hammer a site)
  - Polite delays between requests (env-tunable via REQUEST_DELAY_MIN/MAX)
  - Retry on transient HTTP errors (tenacity, exponential backoff)
  - Soft-block detection (captcha, paywall, 403/451, suspiciously short body)
  - Raw HTML caching to data/output/raw/news/<source_id>/ for replay/debugging

The pattern mirrors `data/fetchers/broadstreet.py` — read that for a complete,
working reference. The principles are identical; only the parsing differs.
"""
import os
import random
import time
from pathlib import Path

import pandas as pd
import requests
import urllib3.exceptions

# pyrefly: ignore [missing-import]
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from data.config import (
    USER_AGENT,
    FROM_EMAIL,
    REQUEST_DELAY_MIN,
    REQUEST_DELAY_MAX,
    REQUEST_TIMEOUT,
    LOG_DIR,
    KILLSWITCH_PATH,
)

# News-specific paths. Defined here (not in config.py) until news ingestion
# is integrated into the main pipeline.
NEWS_RAW_DIR = "data/output/raw/news"
NEWS_PROCESSED_DIR = "data/output/processed/news"

Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
logger.add(
    f"{LOG_DIR}/news.log",
    rotation="1 MB",
    level="INFO",
)


# ---------- shared exceptions (mirroring broadstreet.py) ----------

class KillSwitchError(Exception):
    """Operator-triggered abort. Touch data/.killswitch to raise."""


class SoftBlockError(Exception):
    """Response looks like a captcha, paywall, 403/451, or empty body."""


class RequestCapExceeded(Exception):
    """The per-run request cap has been hit."""


# ---------- the contract every fetcher must return ----------

ARTICLE_COLUMNS = [
    "published_date",     # datetime64[ns, UTC] or tz-aware Africa/Lagos
    "source",             # string — must match source_id in news_sources.csv
    "headline",           # string — original headline, untouched
    "article_text",       # string — full body, plain text, no HTML
    "url",                # string — canonical URL to the source article
    "mentioned_tickers",  # list[str] — NGX tickers mentioned (empty list OK for v1)
]


# ---------- base class ----------

class NewsFetcherBase:
    """
    Subclasses must set SOURCE_ID and BASE_URL, and implement fetch_articles().
    """

    SOURCE_ID = None     # e.g. "nairametrics" — must match news_sources.csv
    BASE_URL = None      # e.g. "https://nairametrics.com"

    def __init__(self, max_requests=None):

        if not self.SOURCE_ID or not self.BASE_URL:
            raise NotImplementedError(
                "Subclass must define SOURCE_ID and BASE_URL"
            )

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "From": FROM_EMAIL,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        })

        self.max_requests = max_requests
        self.request_count = 0

    # ---------- safety scaffolding ----------

    def _check_killswitch(self):
        if os.path.exists(KILLSWITCH_PATH):
            raise KillSwitchError(
                f"Killswitch file present at {KILLSWITCH_PATH}. Aborting."
            )

    def _check_cap(self):
        if self.max_requests is not None and self.request_count >= self.max_requests:
            raise RequestCapExceeded(
                f"Hit per-run cap of {self.max_requests} requests."
            )

    def _polite_sleep(self):
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        time.sleep(delay)

    def _detect_soft_block(self, response):
        """
        Subclasses MAY override to add site-specific checks (e.g. detecting
        a specific paywall pattern). Call super()._detect_soft_block(response)
        first to keep the shared checks.
        """
        lower = response.text.lower()

        if "captcha" in lower or "are you a human" in lower:
            raise SoftBlockError("Response mentions captcha.")

        if "cf-browser-verification" in lower or "checking your browser" in lower:
            raise SoftBlockError("Cloudflare browser check encountered.")

        if response.status_code in (403, 451):
            raise SoftBlockError(
                f"HTTP {response.status_code} — refusing to continue."
            )

        if len(response.text) < 200:
            raise SoftBlockError(
                f"Response unusually short ({len(response.text)} bytes)."
            )

    @retry(
        retry=retry_if_exception_type((
            requests.HTTPError,
            requests.ConnectionError,
            requests.Timeout,
            requests.exceptions.ChunkedEncodingError,
            urllib3.exceptions.ProtocolError,
            ConnectionResetError,
        )),
        wait=wait_exponential(multiplier=30, min=30, max=120),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _polite_get(self, url, save_raw_to=None):

        self._check_killswitch()
        self._check_cap()
        self._polite_sleep()

        logger.info(f"[{self.SOURCE_ID}] GET {url}")

        response = self.session.get(url, timeout=REQUEST_TIMEOUT)
        self.request_count += 1

        if response.status_code == 429:
            logger.warning(f"[{self.SOURCE_ID}] HTTP 429 — backing off")
            raise requests.HTTPError("429 Too Many Requests", response=response)

        if response.status_code >= 500:
            raise requests.HTTPError(
                f"{response.status_code} {response.reason}",
                response=response,
            )

        self._detect_soft_block(response)

        if save_raw_to:
            Path(save_raw_to).parent.mkdir(parents=True, exist_ok=True)
            Path(save_raw_to).write_text(response.text, encoding="utf-8")

        return response

    # ---------- the abstract method subclasses must implement ----------

    def fetch_articles(self, since_date=None, max_articles=None):
        """
        Fetch articles from this source.

        Args:
            since_date: datetime — only return articles published on/after this date.
                        Pass None to fetch all available history.
            max_articles: int    — soft cap on number of articles to return.
                                   Pass None for unlimited.

        Returns:
            pandas.DataFrame with the columns defined in ARTICLE_COLUMNS.

        Subclasses MUST implement this. See nairametrics.py for an example
        (once implemented). See data/fetchers/broadstreet.py for the parallel
        pattern on the price side.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement fetch_articles()"
        )

    # ---------- writing output ----------

    def write_parquet(self, df, year):
        """
        Persist a DataFrame of articles to the canonical location:
          data/output/processed/news/articles/source=<id>/year=<YYYY>/articles.parquet

        Args:
            df: DataFrame matching ARTICLE_COLUMNS exactly.
            year: int — the calendar year these articles belong to.
        """
        missing = [c for c in ARTICLE_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(
                f"DataFrame missing required columns: {missing}. "
                f"See ARTICLE_COLUMNS for the contract."
            )

        out_dir = Path(NEWS_PROCESSED_DIR) / "articles" / f"source={self.SOURCE_ID}" / f"year={year}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "articles.parquet"

        df[ARTICLE_COLUMNS].to_parquet(out_path, index=False)
        logger.success(
            f"[{self.SOURCE_ID}] wrote {len(df)} articles to {out_path}"
        )
        return out_path
