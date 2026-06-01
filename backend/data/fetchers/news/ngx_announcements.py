"""
Fetcher for NGX Official Announcements  (https://ngxgroup.com).

PRIORITY 1 — the PRIMARY source. NGX-listed companies are required to
disclose material events here (earnings, board changes, dividends, M&A),
so every other news source is downstream of these announcements.

This module follows the SAME proven pattern as data/fetchers/news/
businessday.py (which was verified end-to-end against real HTML) and
data/fetchers/broadstreet.py:
  discover URLs -> cache-first fetch via self._polite_get -> parse in a
  static method -> build dicts matching ARTICLE_COLUMNS -> DataFrame.

All the hard parts (polite delay, retry/backoff, killswitch, request cap,
soft-block / 403 detection, raw-HTML caching) live in base.py and are
reused unchanged. This file implements fetch_articles() + parsing only.

------------------------------------------------------------------------------
VERIFICATION STATUS — READ THIS
------------------------------------------------------------------------------
VERIFIED end-to-end against real browser-saved ngxgroup.com HTML:
  - Discovery: listing at /media-center/news/, announcements parsed from the
    WordPress <article class="post"> cards (root-level slugs), nav/footer
    excluded, pagination via /media-center/news/page/N/ (capped).
  - Detail parse: headline from og:title (" - Nigerian Exchange Group"
    suffix stripped; pages have no <h1>), date from <meta
    article:published_time> (tz-aware Africa/Lagos), body from
    <div class="entry-content">, canonical from <link rel="canonical">.
  - mentioned_tickers matcher: verified offline vs the real tickers.csv,
    with the exchange self-tag suppressed (see KNOWN_ISSUES NGX-2).

Still pending before ANY live run (handbook Sections 6 & 10), same as
BusinessDay: read ngxgroup.com/robots.txt and respect it; resolve the
.env scraper-identity question with Tomi. A real run that raises
SoftBlockError (403/451/captcha) STOPS by design — base.py raises it,
this code lets it abort. Do not retry; tell Tomi.
------------------------------------------------------------------------------
"""

import csv
import datetime as _dt
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pandas as pd
from bs4 import BeautifulSoup

# pyrefly: ignore [missing-import]
from loguru import logger

from .base import (
    NewsFetcherBase,
    ARTICLE_COLUMNS,
    NEWS_RAW_DIR,
    KillSwitchError,
    SoftBlockError,
    RequestCapExceeded,
)

# Nigeria (West Africa Time): fixed UTC+1, no DST — correct & dependency-free.
WAT = _dt.timezone(_dt.timedelta(hours=1))

# Where the NGX ticker registry lives (already in the repo; uploaded sample
# confirmed columns: ticker,name,sector,sector_id,detail_url).
TICKERS_CSV = "data/master/tickers.csv"


# ========================================================================= #
#  Ticker matcher (handbook Section 8). VERIFIED offline against the real    #
#  tickers.csv. Written as a standalone, reusable unit so it can later be    #
#  lifted into a shared module and used by businessday.py too (Week 3).      #
# ========================================================================= #

class TickerMatcher:
    """
    A deliberately CONSERVATIVE first-pass matcher (handbook Section 8 says
    a reasonable first pass is enough; the NLP team builds real NER later).

    Two signals, both low-false-positive:
      1. Exact ticker token, upper-case, on word boundaries, length >= 3
         (so "ABC" matches "ABC" but not the substring in "abcdef"; very
         short/ambiguous tickers are skipped to avoid noise).
      2. Distinctive company-name phrase, case-insensitive, after stripping
         generic suffixes (PLC, Nigeria, Limited, Company, ...).

    Returns a sorted, de-duplicated list[str] of tickers — never None;
    an empty list is valid per the v1 contract.
    """

    _SUFFIXES = (
        "plc", "ltd", "limited", "nigeria", "nig", "company", "co",
        "group", "holdings", "of", "the", "and", "&", "inc",
    )
    # Tokens that look like tickers but are common English / finance words —
    # excluded from the bare-ticker signal to cut false positives.
    _STOPWORD_TICKERS = {
        "THE", "AND", "FOR", "PLC", "CEO", "CFO", "NGX", "NSE", "AGM",
        "EGM", "USD", "NGN", "GDP", "FY", "Q1", "Q2", "Q3", "Q4", "ALL",
        "ARM", "RED", "SUN", "MAY", "ICE", "AIR", "BIG", "ETI",
    }

    def __init__(self, tickers_csv=TICKERS_CSV, exclude=None):
        self.ticker_to_ticker = {}     # "DANGCEM" -> "DANGCEM"
        self.name_to_ticker = []       # [(normalized_name, ticker)] longest-first
        # Tickers to NOT auto-tag (e.g. the exchange itself on its own
        # filings — see KNOWN_ISSUES). A reasonable first pass under-tags
        # here rather than tagging the venue on ~100% of announcements;
        # proper disambiguation is the NLP team's NER job (handbook S8).
        self.exclude = {t.upper() for t in (exclude or set())}
        self._load(tickers_csv)

    @staticmethod
    def _norm(text):
        text = text.lower()
        text = re.sub(r"[^a-z0-9 ]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _distinctive_name(self, name):
        """Drop generic suffix words so 'Dangote Cement PLC' -> 'dangote cement'."""
        words = [w for w in self._norm(name).split()
                 if w not in self._SUFFIXES]
        return " ".join(words).strip()

    def _load(self, tickers_csv):
        path = Path(tickers_csv)
        if not path.exists():
            logger.warning(
                f"[ngx_announcements] tickers.csv not found at {tickers_csv}; "
                f"mentioned_tickers will be empty (valid for v1)."
            )
            return
        rows = 0
        with path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                tk = (row.get("ticker") or "").strip()
                nm = (row.get("name") or "").strip()
                if not tk:
                    continue
                self.ticker_to_ticker[tk.upper()] = tk
                dn = self._distinctive_name(nm)
                # Require a name with real signal. CONSERVATIVE: only use
                # the name signal for multi-token distinctive names. A
                # single common word (e.g. "total" -> Total Nigeria PLC,
                # "the", "cutix") causes systematic false positives in
                # prose; such companies still match via the bare-ticker
                # signal. This deliberately trades a little recall for much
                # less noise (handbook S8: reasonable first pass; NER later).
                if dn and len(dn) >= 4 and dn != tk.lower() \
                        and len(dn.split()) >= 2:
                    self.name_to_ticker.append((dn, tk))
                rows += 1
        # Match longer names first so "dangote sugar" wins over "dangote".
        self.name_to_ticker.sort(key=lambda x: len(x[0]), reverse=True)
        logger.info(
            f"[ngx_announcements] ticker matcher loaded {rows} tickers"
        )

    def find(self, *texts):
        blob = " ".join(t for t in texts if t)
        if not blob:
            return []
        found = set()

        # Signal 1: bare upper-case ticker token on word boundaries.
        for token in set(re.findall(r"\b[A-Z][A-Z0-9.]{2,}\b", blob)):
            if token in self._STOPWORD_TICKERS or token in self.exclude:
                continue
            if token in self.ticker_to_ticker:
                found.add(self.ticker_to_ticker[token])

        # Signal 2: distinctive company-name phrase (case-insensitive).
        norm_blob = self._norm(blob)
        for dn, tk in self.name_to_ticker:
            if tk.upper() in self.exclude:
                continue
            # surround with spaces for a cheap word-boundary phrase check
            if f" {dn} " in f" {norm_blob} ":
                found.add(tk)

        return sorted(found)


# ========================================================================= #
#  The fetcher                                                               #
# ========================================================================= #

class NGXAnnouncementsFetcher(NewsFetcherBase):

    SOURCE_ID = "ngx_announcements"
    BASE_URL = "https://ngxgroup.com"

    RAW_DIR = f"{NEWS_RAW_DIR}/ngx_announcements"

    # VERIFIED against the real saved listing page. Canonical listing URL
    # is /media-center/news/ (NOT /issuers/news). Announcements are
    # root-level slugs, discovered via the WordPress post-card structure
    # below (not by URL pattern, which would miss them / catch nav pages).
    LISTING_PATHS = [
        "/media-center/news/",
    ]
    # WordPress paginates as /media-center/news/page/2/ etc. Capped so a
    # run can't walk the entire archive unintentionally (politeness, S6).
    MAX_LISTING_PAGES = 5

    def __init__(self, max_requests=None, tickers_csv=TICKERS_CSV):
        super().__init__(max_requests=max_requests)
        # Built once per run; offline; no network. Exclude "NGX": every
        # announcement is filed TO the Nigerian Exchange, so its own name
        # would otherwise tag ~100% of rows (see KNOWN_ISSUES). Conservative
        # under-tagging; proper disambiguation is the NLP team's job.
        self._ticker_matcher = TickerMatcher(tickers_csv, exclude={"NGX"})

    # --------------------------------------------------------------------- #
    #  Public entry point — the abstract method base.py requires.           #
    # --------------------------------------------------------------------- #

    def fetch_articles(self, since_date=None, max_articles=None,
                        use_cache=True):
        """
        Collect NGX announcements into a DataFrame matching ARTICLE_COLUMNS.

        Operator signals (KillSwitch / SoftBlock / RequestCapExceeded) are
        NOT caught here — they bubble up and abort the run (handbook 6/10).
        """
        since_date = self._coerce_date(since_date)

        urls = self._discover_announcement_urls(use_cache=use_cache)
        logger.info(
            f"[{self.SOURCE_ID}] discovered {len(urls)} candidate URLs"
        )

        rows = []
        for url in urls:
            if max_articles is not None and len(rows) >= max_articles:
                logger.info(
                    f"[{self.SOURCE_ID}] hit max_articles={max_articles}"
                )
                break

            html = self._get_html(url, use_cache=use_cache)
            if html is None:
                continue

            record = self._parse_announcement(
                html, url, self._ticker_matcher
            )
            if record is None:
                logger.warning(f"[{self.SOURCE_ID}] unparseable: {url}")
                continue

            if since_date and record["published_date"] is not None:
                if record["published_date"].date() < since_date:
                    continue

            rows.append(record)

        if not rows:
            logger.warning(f"[{self.SOURCE_ID}] no announcements collected")
            return pd.DataFrame(columns=ARTICLE_COLUMNS)

        df = self._build_dataframe(rows)
        logger.success(
            f"[{self.SOURCE_ID}] collected {len(df)} announcements "
            f"({df['published_date'].min()} -> {df['published_date'].max()})"
        )
        return df

    def run(self, since_date=None, max_articles=None, use_cache=True):
        """Fetch then write one parquet per year via the base helper."""
        df = self.fetch_articles(
            since_date=since_date,
            max_articles=max_articles,
            use_cache=use_cache,
        )
        if df.empty:
            return []
        written = []
        for year in sorted(
            int(y) for y in df["published_date"].dt.year.dropna().unique()
        ):
            written.append(
                self.write_parquet(
                    df[df["published_date"].dt.year == year], year
                )
            )
        return written

    # --------------------------------------------------------------------- #
    #  Discovery (Stage 1) — PROVISIONAL until real HTML is inspected.       #
    # --------------------------------------------------------------------- #

    def _discover_announcement_urls(self, use_cache=True):
        """
        Fetch the listing page(s) and collect announcement permalinks from
        the WordPress post-card structure.

        VERIFIED against the real saved listing: each announcement is an
        <article class="... post type-post ..."> card whose first on-site
        <a href> is the permalink (a root-level slug). We extract links
        from the cards only — NOT by scanning every <a> on the page — so
        header/footer/nav links (advertise-with-us, careers, etc.) are
        naturally excluded. Pagination follows /media-center/news/page/N/.
        """
        seen = set()
        urls = []

        for path in self.LISTING_PATHS:
            for page in range(1, self.MAX_LISTING_PAGES + 1):
                if page == 1:
                    list_url = f"{self.BASE_URL}{path}"
                    cache_name = ("_list_"
                                  + path.strip("/").replace("/", "_")
                                  + ".html")
                else:
                    list_url = f"{self.BASE_URL}{path}page/{page}/"
                    cache_name = ("_list_"
                                  + path.strip("/").replace("/", "_")
                                  + f"_p{page}.html")

                html = self._get_html(
                    list_url, cache_name=cache_name, use_cache=use_cache
                )
                if html is None:
                    break  # no more pages / fetch issue already logged

                soup = BeautifulSoup(html, "lxml")
                cards = soup.find_all("article")
                if not cards:
                    break  # structure changed or end of listing

                page_new = 0
                for card in cards:
                    cls = " ".join(card.get("class", []))
                    if "post" not in cls:
                        continue  # not a post card
                    a = card.find("a", href=True)
                    if a is None:
                        continue
                    href = a["href"]
                    if href.startswith("/"):
                        href = self.BASE_URL + href
                    if not href.startswith(self.BASE_URL):
                        continue
                    canon = self._canonical_url(href)
                    if not canon:
                        continue  # '#' or junk -> _canonical_url returns None
                    if canon.rstrip("/") == self.BASE_URL.rstrip("/"):
                        continue
                    key = canon.rstrip("/")
                    if key in seen:
                        continue
                    seen.add(key)
                    urls.append(canon)
                    page_new += 1

                if page_new == 0:
                    break  # nothing new on this page -> stop paginating

        return urls

    # --------------------------------------------------------------------- #
    #  Fetch helper — cache-first (identical philosophy to businessday.py).  #
    # --------------------------------------------------------------------- #

    def _get_html(self, url, cache_name=None, use_cache=True):
        if cache_name is None:
            slug = urlsplit(url).path.strip("/").replace("/", "_") or "index"
            cache_name = f"{slug}.html"
        cache_path = Path(self.RAW_DIR) / cache_name

        if use_cache and cache_path.exists():
            try:
                logger.info(f"[{self.SOURCE_ID}] cache hit {cache_path.name}")
                return cache_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(
                    f"[{self.SOURCE_ID}] cache read failed "
                    f"({cache_path.name}): {e}"
                )

        try:
            response = self._polite_get(url, save_raw_to=str(cache_path))
        except (KillSwitchError, SoftBlockError, RequestCapExceeded):
            raise  # operator-level signal — STOP the run (handbook 6/10)
        except Exception as e:
            logger.error(f"[{self.SOURCE_ID}] fetch failed {url}: {e!r}")
            return None

        return response.text

    # --------------------------------------------------------------------- #
    #  Parsing (Stage 2) — PROVISIONAL selectors, broad fallbacks.          #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _parse_announcement(html, url, ticker_matcher):
        """
        Parse one announcement page into a dict matching ARTICLE_COLUMNS.
        Returns None if there is no usable body (never emits empty rows —
        handbook Section 2).

        Selectors are provisional with broad fallbacks. The ticker matching
        is the verified part. When the real HTML is available, prefer NGX's
        OWN explicit ticker tag on the announcement (the stub notes NGX tags
        the ticker) over the text scan, by filling in `tagged_ticker` below.
        """
        soup = BeautifulSoup(html, "lxml")

        # ---- headline (broad fallbacks) -------------------------------- #
        headline = None
        og_t = soup.find("meta", property="og:title")
        if og_t and og_t.get("content"):
            headline = og_t["content"].strip()
        if not headline:
            h1 = soup.find("h1")
            if h1:
                headline = h1.get_text(strip=True)
        if not headline and soup.title:
            headline = soup.title.get_text(strip=True)
        if not headline:
            return None
        for suf in (" - NGX", " | NGX", " - Nigerian Exchange Group"):
            if headline.endswith(suf):
                headline = headline[: -len(suf)].strip()

        # ---- published date -------------------------------------------- #
        published = None
        mt = soup.find("meta", property="article:published_time")
        if mt and mt.get("content"):
            published = NGXAnnouncementsFetcher._parse_date(mt["content"])
        if published is None:
            t = soup.find("time")
            if t and t.get("datetime"):
                published = NGXAnnouncementsFetcher._parse_date(t["datetime"])

        # ---- body ------------------------------------------------------ #
        body_node = (
            soup.select_one("div.entry-content")
            or soup.select_one("div.post-content")
            or soup.select_one("div.news-detail")
            or soup.select_one("article")
            or soup.find("main")
        )
        article_text = ""
        if body_node is not None:
            for junk in body_node.select(
                "script, style, noscript, figure, nav, .breadcrumb, "
                ".share, .social, .related, .ad, .ads, .menu, header, footer"
            ):
                junk.decompose()
            parts = [
                p.get_text(" ", strip=True)
                for p in body_node.find_all(["p", "h2", "h3", "li", "td"])
            ]
            article_text = "\n\n".join(t for t in parts if t)

        if not article_text or len(article_text) < 120:
            logger.warning(
                f"[ngx_announcements] SKIP — no usable body: {url} "
                f"(headline ok='{headline[:60]}'). Verify selectors against "
                f"real saved HTML (handbook Section 13)."
            )
            return None

        # ---- canonical URL --------------------------------------------- #
        canon = None
        lc = soup.find("link", rel="canonical")
        if lc and lc.get("href"):
            canon = NGXAnnouncementsFetcher._canonical_url(lc["href"])
        if not canon:
            canon = NGXAnnouncementsFetcher._canonical_url(url)

        # ---- mentioned_tickers (HIGH VALUE for NGX — handbook S8) ------- #
        # TODO when real HTML available: if NGX renders an explicit ticker
        # tag/symbol field on the announcement, parse it here and prepend it
        # (most authoritative). Until then, the conservative text matcher
        # below is a solid, tested first pass.
        tagged_ticker = None  # placeholder for NGX's explicit tag
        tickers = ticker_matcher.find(headline, article_text)
        if tagged_ticker and tagged_ticker not in tickers:
            tickers = sorted({tagged_ticker, *tickers})

        return {
            "published_date": published,
            "source": "ngx_announcements",
            "headline": headline,
            "article_text": article_text,
            "url": canon,
            "mentioned_tickers": tickers,
        }

    # --------------------------------------------------------------------- #
    #  Shared small helpers (same contracts as businessday.py)              #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _canonical_url(url):
        if not url:
            return None
        p = urlsplit(url.strip())
        if not p.scheme or not p.netloc:
            return None
        return urlunsplit((p.scheme, p.netloc, p.path, "", ""))

    @staticmethod
    def _parse_date(value):
        if not value:
            return None
        raw = value.strip().replace("Z", "+00:00")
        ts = None
        try:
            ts = _dt.datetime.fromisoformat(raw)
        except ValueError:
            for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%d", "%d/%m/%Y", "%d %B %Y", "%B %d, %Y"):
                try:
                    ts = _dt.datetime.strptime(raw, fmt)
                    break
                except ValueError:
                    continue
        if ts is None:
            return None
        ts = ts.replace(tzinfo=WAT) if ts.tzinfo is None \
            else ts.astimezone(WAT)
        return ts

    @staticmethod
    def _coerce_date(value):
        if value is None:
            return None
        if isinstance(value, _dt.datetime):
            return value.date()
        if isinstance(value, _dt.date):
            return value
        parsed = NGXAnnouncementsFetcher._parse_date(str(value))
        return parsed.date() if parsed else None

    @staticmethod
    def _build_dataframe(rows):
        df = pd.DataFrame(rows, columns=ARTICLE_COLUMNS)
        df["published_date"] = pd.to_datetime(
            df["published_date"], utc=False, errors="coerce"
        )
        for col in ("source", "headline", "article_text", "url"):
            df[col] = df[col].astype("string")
        df = (
            df.dropna(subset=["url"])
              .drop_duplicates(subset=["url"])
              .sort_values("published_date")
              .reset_index(drop=True)
        )
        return df


# ------------------------------------------------------------------------- #
#  Handbook Section 13 first test. Replace TEST_URL with a real NGX          #
#  announcement URL once you have one (or point use_cache at a saved page).  #
#      python -m data.fetchers.news.ngx_announcements                        #
# ------------------------------------------------------------------------- #
if __name__ == "__main__":
    import json

    TEST_URL = "https://ngxgroup.com/equities-market-gains-n3-17tn-as-asi-crosses-250000-mark/"

    f = NGXAnnouncementsFetcher(max_requests=1)
    html = f._get_html(TEST_URL, use_cache=True)
    if html is None:
        print("No HTML (fetch failed/blocked). See log; do not retry a 403.")
    else:
        rec = f._parse_announcement(html, TEST_URL, f._ticker_matcher)
        if rec is None:
            print("Parsed nothing — adjust selectors in _parse_announcement().")
        else:
            prev = dict(rec)
            prev["published_date"] = str(prev["published_date"])
            prev["article_text"] = prev["article_text"][:300] + " ...[trunc]"
            print(json.dumps(prev, indent=2, ensure_ascii=False))
