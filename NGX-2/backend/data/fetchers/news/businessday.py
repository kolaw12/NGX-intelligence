"""
Fetcher for BusinessDay Nigeria articles  (https://businessday.ng).

PRIORITY 1 — major business daily; broad coverage of NGX-listed companies,
banking, energy, regulation.

This module follows the pattern proven in data/fetchers/broadstreet.py:
  discover URLs  ->  cache-first fetch via self._polite_get  ->  parse in a
  static method  ->  build dicts matching ARTICLE_COLUMNS  ->  DataFrame.

All the hard parts (polite delay, retry/backoff, killswitch, request cap,
soft-block / 403 detection, raw-HTML caching) live in base.py and are reused
unchanged. This file only implements fetch_articles() and the parsing.

------------------------------------------------------------------------------
STATUS — selectors VERIFIED against a real browser-saved BusinessDay page
------------------------------------------------------------------------------
Headline (<h1 class="post-title">), date (<meta article:published_time>),
canonical (<link rel="canonical">) and the Yoast sitemap layout are confirmed
against real HTML. Free-article body extraction is NOT yet confirmed: the only
sample available so far was a paywalled BusinessDay PRO (/pro/) article whose
body is not served at all. The code therefore SKIPS paywalled / body-less
pages (never emits empty rows) and logs them for KNOWN_ISSUES.md.

Open items (handbook Sections 7 & 10), pending Tomi:
  - Is paywalled PRO content in scope? (licensing — Section 7)
  - Do FREE articles serve their body in static HTML, or is a browser engine
    (Selenium/Playwright) needed site-wide? (needs one free-article sample)

If a real run raises SoftBlockError (403/451/captcha): STOP. Do not retry.
Tell Tomi. base.py raises it; this code lets it abort the run by design.
------------------------------------------------------------------------------
"""

import datetime as _dt
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

# Nigeria (West Africa Time) is a fixed UTC+1 with no daylight saving, so a
# fixed offset is correct and dependency-free. The handbook asks for
# tz-aware Africa/Lagos timestamps; this satisfies that contract.
WAT = _dt.timezone(_dt.timedelta(hours=1))


class BusinessDayFetcher(NewsFetcherBase):

    SOURCE_ID = "businessday"
    BASE_URL = "https://businessday.ng"

    # Where this source's raw HTML cache lives (handbook Section 12).
    RAW_DIR = f"{NEWS_RAW_DIR}/businessday"

    # robots.txt advertises this sitemap and the search endpoints (/?s=,
    # /search/) are Disallowed, so the sitemap is the sanctioned discovery
    # path. VERIFIED against a real browser-fetched copy: it is a standard
    # Yoast index. Freshest articles are in news-sitemap.xml (~48h window,
    # ideal for daily incremental runs) and post-sitemap.xml (latest batch).
    # post-sitemap2..N.xml are deep history and must NOT be crawled by
    # default (hundreds of files = a huge, impolite crawl).
    SITEMAP_INDEX = f"{BASE_URL}/sitemap_index.xml"
    NEWS_SITEMAP = f"{BASE_URL}/news-sitemap.xml"

    # PROVISIONAL fallback discovery — only used if the sitemap yields
    # nothing. Section listing pages; none collide with robots.txt Disallow.
    CATEGORY_PATHS = [
        "/category/markets/",
        "/category/companies/",
        "/category/financial-inclusion/",
        "/category/energy/",
        "/category/economy/",
    ]

    # BusinessDay PRO (/pro/...) is premium/paywalled content. Handbook
    # Section 7 makes scraping paywalled content a licensing decision, not a
    # default behaviour. We SKIP it unless an operator explicitly opts in
    # AND the legal question has been cleared with Tomi.
    SKIP_PAYWALLED = True
    PAYWALL_PATH_MARKERS = ("/pro/",)

    # --------------------------------------------------------------------- #
    #  Public entry point — the abstract method base.py requires.           #
    # --------------------------------------------------------------------- #

    def fetch_articles(self, since_date=None, max_articles=None,
                        use_cache=True, backfill=False):
        """
        Collect BusinessDay articles into a DataFrame matching ARTICLE_COLUMNS.

        Args:
            since_date:   datetime/date — only keep articles published on or
                          after this. None = no lower bound.
            max_articles: int — soft cap on number of articles. None = no cap.
            use_cache:    if True, reuse raw HTML already on disk instead of
                          re-fetching (zero HTTP). Mirrors broadstreet.py and
                          makes the handbook's "one article first" test cheap
                          and repeatable.

        Returns:
            pandas.DataFrame with exactly ARTICLE_COLUMNS.

        Operator signals (KillSwitchError / SoftBlockError / RequestCapExceeded)
        are NOT caught here — they bubble up and abort the run, per handbook
        Sections 6 and 10.
        """
        since_date = self._coerce_date(since_date)

        article_urls = self._discover_article_urls(
            since_date=since_date, use_cache=use_cache, backfill=backfill
        )
        logger.info(
            f"[{self.SOURCE_ID}] discovered {len(article_urls)} candidate URLs"
        )

        rows = []
        for url in article_urls:

            if max_articles is not None and len(rows) >= max_articles:
                logger.info(
                    f"[{self.SOURCE_ID}] hit max_articles={max_articles}"
                )
                break

            html = self._get_html(url, use_cache=use_cache)
            if html is None:
                continue  # non-fatal fetch error already logged; skip article

            record = self._parse_article(html, url)
            if record is None:
                logger.warning(f"[{self.SOURCE_ID}] unparseable: {url}")
                continue

            if since_date and record["published_date"] is not None:
                if record["published_date"].date() < since_date:
                    continue

            rows.append(record)

        if not rows:
            logger.warning(f"[{self.SOURCE_ID}] no articles collected")
            return pd.DataFrame(columns=ARTICLE_COLUMNS)

        df = self._build_dataframe(rows)
        logger.success(
            f"[{self.SOURCE_ID}] collected {len(df)} articles "
            f"({df['published_date'].min()} -> {df['published_date'].max()})"
        )
        return df

    # --------------------------------------------------------------------- #
    #  Convenience: split by year and persist via the base helper.          #
    # --------------------------------------------------------------------- #

    def run(self, since_date=None, max_articles=None, use_cache=True,
            backfill=False):
        """
        Fetch, then write one parquet per calendar year via the base-class
        helper (which enforces the canonical path and validates the schema).
        Returns the list of written paths.
        """
        df = self.fetch_articles(
            since_date=since_date,
            max_articles=max_articles,
            use_cache=use_cache,
            backfill=backfill,
        )
        if df.empty:
            return []

        written = []
        years = df["published_date"].dt.year.dropna().unique()
        for year in sorted(int(y) for y in years):
            year_df = df[df["published_date"].dt.year == year]
            written.append(self.write_parquet(year_df, year))
        return written

    # --------------------------------------------------------------------- #
    #  Discovery (Stage 1) — mirrors broadstreet.fetch_companies_in_sector. #
    # --------------------------------------------------------------------- #

    def _discover_article_urls(self, since_date=None, use_cache=True,
                               backfill=False):
        """
        Return a de-duplicated list of canonical article URLs.

        Strategy, in order of preference:
          1. Verified Yoast sitemap (news-sitemap.xml + latest post-sitemap;
             full history only when backfill=True). robots.txt-sanctioned;
             avoids the Disallowed /search/ path.
          2. Fallback: scrape the section listing pages and collect links.

        If the sitemap raises SoftBlockError (e.g. 403), that bubbles up and
        aborts the run — we do NOT silently fall back, because the handbook
        says a 403 is a stop-and-ask event, not a "try another way" event.
        """
        try:
            urls = self._discover_via_sitemap(
                since_date=since_date, use_cache=use_cache,
                backfill=backfill,
            )
            if urls:
                return urls
            logger.warning(
                f"[{self.SOURCE_ID}] sitemap yielded no URLs — using "
                f"PROVISIONAL category fallback (verify CATEGORY_PATHS)"
            )
        except (KillSwitchError, SoftBlockError, RequestCapExceeded):
            raise  # operator-level signal — bubble up and abort
        except Exception as e:
            logger.error(
                f"[{self.SOURCE_ID}] sitemap discovery failed ({e!r}); "
                f"falling back to category pages"
            )

        return self._discover_via_categories(use_cache=use_cache)

    def _discover_via_sitemap(self, since_date=None, use_cache=True,
                              backfill=False):
        """
        VERIFIED Yoast structure. By default we only read:
          - news-sitemap.xml   (Google-News sitemap, ~last 48h)
          - post-sitemap.xml   (latest posts batch)
        Set backfill=True to additionally walk post-sitemap2..N.xml (deep
        history — hundreds of files; only for a deliberate one-off backfill).
        """
        targets = [self.NEWS_SITEMAP]

        idx_html = self._get_html(
            self.SITEMAP_INDEX,
            cache_name="_sitemap_index.xml",
            use_cache=use_cache,
        )
        if idx_html is not None:
            idx = BeautifulSoup(idx_html, "xml")
            child = [loc.get_text(strip=True) for loc in idx.find_all("loc")]
            # Latest posts batch is the un-numbered post-sitemap.xml.
            for c in child:
                if c.rsplit("/", 1)[-1] == "post-sitemap.xml":
                    targets.append(c)
            if backfill:
                for c in child:
                    name = c.rsplit("/", 1)[-1]
                    if name.startswith("post-sitemap") and name != \
                            "post-sitemap.xml":
                        targets.append(c)

        seen = set()
        urls = []
        for sm in targets:
            sm_name = "_sm_" + urlsplit(sm).path.strip("/").replace("/", "_")
            sm_html = self._get_html(
                sm, cache_name=sm_name, use_cache=use_cache
            )
            if sm_html is None:
                continue

            sm_soup = BeautifulSoup(sm_html, "xml")
            for url_tag in sm_soup.find_all("url"):
                loc_tag = url_tag.find("loc")
                if loc_tag is None:
                    continue
                canon = self._canonical_url(loc_tag.get_text(strip=True))
                if not canon or canon in seen:
                    continue

                if self.SKIP_PAYWALLED and any(
                    m in canon for m in self.PAYWALL_PATH_MARKERS
                ):
                    logger.info(
                        f"[{self.SOURCE_ID}] skip paywalled (handbook S7): "
                        f"{canon}"
                    )
                    continue

                if since_date is not None:
                    lastmod = url_tag.find("lastmod")
                    if lastmod is not None:
                        ts = self._parse_date(lastmod.get_text(strip=True))
                        if ts is not None and ts.date() < since_date:
                            continue

                seen.add(canon)
                urls.append(canon)

        return urls

    def _discover_via_categories(self, use_cache=True):
        seen = set()
        urls = []
        for path in self.CATEGORY_PATHS:
            list_url = f"{self.BASE_URL}{path}"
            cache_name = "_cat_" + path.strip("/").replace("/", "_") + ".html"
            html = self._get_html(
                list_url, cache_name=cache_name, use_cache=use_cache
            )
            if html is None:
                continue

            soup = BeautifulSoup(html, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("/"):
                    href = self.BASE_URL + href
                if not href.startswith(self.BASE_URL):
                    continue
                # Heuristic for WordPress article permalinks: a dated or
                # slugged path that is not itself a category/tag/author page.
                low = href.lower()
                if any(seg in low for seg in
                       ("/category/", "/tag/", "/author/", "/page/",
                        "/wp-", "?", "#")):
                    continue
                canon = self._canonical_url(href)
                if canon and canon not in seen and canon.rstrip("/") != \
                        self.BASE_URL.rstrip("/"):
                    seen.add(canon)
                    urls.append(canon)

        return urls

    # --------------------------------------------------------------------- #
    #  Fetch helper — cache-first, mirroring broadstreet's use_cache logic.  #
    # --------------------------------------------------------------------- #

    def _get_html(self, url, cache_name=None, use_cache=True):
        """
        Return HTML text for `url`, reading the on-disk cache first when
        possible (zero HTTP), otherwise fetching via self._polite_get (which
        applies the polite delay, killswitch, cap and soft-block checks).

        Operator signals bubble up. Other fetch errors are logged and return
        None so the caller can skip that one URL without aborting the whole
        run (same philosophy as broadstreet's per-page error handling).
        """
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
    #  Parsing (Stage 2) — a static method, like broadstreet's parsers.     #
    #                                                                       #
    #  Selectors VERIFIED against a real browser-saved page. Body extraction #
    #  for FREE articles still needs one non-/pro/ sample to confirm; until  #
    #  then body-less/paywalled pages are skipped, never emitted empty.      #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _parse_article(html, url):
        """
        Parse one article page into a dict matching ARTICLE_COLUMNS.
        Returns None if the page is paywalled or has no real body — a
        skipped article is far better than an empty one (handbook Section 2).

        Selectors below are VERIFIED against a real browser-saved
        BusinessDay page, not guessed.
        """
        soup = BeautifulSoup(html, "lxml")

        # ---- paywall / premium guard (handbook Section 7) -------------- #
        # VERIFIED: the reliable signal is the URL path (/pro/). Site-wide
        # "BusinessDay PRO" nav/branding appears on FREE pages too, so a
        # text-count heuristic false-positives — we deliberately do not use
        # it. Body presence is checked separately below.
        paywalled = any(m in url for m in BusinessDayFetcher.PAYWALL_PATH_MARKERS)

        # ---- headline (VERIFIED: <h1 class="post-title">) -------------- #
        headline = None
        h1 = soup.find("h1", class_="post-title") or soup.find("h1")
        if h1:
            headline = h1.get_text(strip=True)
        if not headline:
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                headline = og_title["content"].strip()
                # og:title carries a " - Businessday NG" site suffix.
                for suf in (" - Businessday NG", " - BusinessDay NG",
                            " - BusinessDay", " | Businessday NG"):
                    if headline.endswith(suf):
                        headline = headline[: -len(suf)].strip()
        if not headline and soup.title:
            headline = soup.title.get_text(strip=True)
        if not headline:
            return None

        # ---- published date (VERIFIED: article:published_time) --------- #
        published = None
        meta_time = soup.find("meta", property="article:published_time")
        if meta_time and meta_time.get("content"):
            published = BusinessDayFetcher._parse_date(meta_time["content"])
        if published is None:
            t = soup.find("time")
            if t and t.get("datetime"):
                published = BusinessDayFetcher._parse_date(t["datetime"])

        # ---- article body --------------------------------------------- #
        # Try the known WP containers. NOTE: on the verified PRO sample the
        # body was absent entirely (JS-rendered / paywalled). We therefore
        # treat a missing/too-short body as "skip + flag", never as success.
        body_node = (
            soup.select_one("div.entry-content")
            or soup.select_one("div.post-content")
            or soup.select_one("article .post-content")
            or soup.find("article")
        )
        article_text = ""
        if body_node is not None:
            for junk in body_node.select(
                "script, style, noscript, figure, .ad, .ads, .advert, "
                ".newsletter, .share, .social, .related, "
                ".related-author-news, .wp-block-embed, nav, .breadcrumb"
            ):
                junk.decompose()
            paragraphs = [
                p.get_text(" ", strip=True)
                for p in body_node.find_all(["p", "h2", "h3", "li"])
            ]
            article_text = "\n\n".join(t for t in paragraphs if t)

        if not article_text or len(article_text) < 200:
            # No usable body. Distinguish the two causes for KNOWN_ISSUES.md.
            reason = ("paywalled/PRO" if paywalled
                      else "no body in static HTML (likely JS-rendered)")
            logger.warning(
                f"[businessday] SKIP — {reason}: {url} "
                f"(headline ok='{headline[:60]}'). Escalate per handbook "
                f"Section 10 if this affects free articles too."
            )
            return None

        # ---- canonical URL (VERIFIED: <link rel="canonical">) ---------- #
        canon_url = None
        link_canon = soup.find("link", rel="canonical")
        if link_canon and link_canon.get("href"):
            canon_url = BusinessDayFetcher._canonical_url(link_canon["href"])
        if not canon_url:
            canon_url = BusinessDayFetcher._canonical_url(url)

        return {
            "published_date": published,
            "source": "businessday",
            "headline": headline,
            "article_text": article_text,
            "url": canon_url,
            # v1 contract: empty list is acceptable (handbook Section 8).
            "mentioned_tickers": [],
        }

    # --------------------------------------------------------------------- #
    #  Small typed helpers                                                  #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _canonical_url(url):
        """Strip query string and fragment — handbook Section 3 requires a
        canonical URL with no params like ?ref=share."""
        if not url:
            return None
        parts = urlsplit(url.strip())
        if not parts.scheme or not parts.netloc:
            return None
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    @staticmethod
    def _parse_date(value):
        """
        Parse an ISO-ish date/datetime string into a tz-aware datetime in
        Africa/Lagos. If only a date is present, time is set to
        00:00:00+01:00 (handbook Section 3). Returns None on failure.
        """
        if not value:
            return None
        raw = value.strip().replace("Z", "+00:00")
        ts = None
        try:
            ts = _dt.datetime.fromisoformat(raw)
        except ValueError:
            for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y"):
                try:
                    ts = _dt.datetime.strptime(raw, fmt)
                    break
                except ValueError:
                    continue
        if ts is None:
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=WAT)
        else:
            ts = ts.astimezone(WAT)
        return ts

    @staticmethod
    def _coerce_date(value):
        if value is None:
            return None
        if isinstance(value, _dt.datetime):
            return value.date()
        if isinstance(value, _dt.date):
            return value
        parsed = BusinessDayFetcher._parse_date(str(value))
        return parsed.date() if parsed else None

    @staticmethod
    def _build_dataframe(rows):
        """Assemble the final DataFrame with the contract's dtypes."""
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
#  Handbook Section 13 first test: "fetch 1 page, parse 1 article, print a   #
#  dict matching ARTICLE_COLUMNS." Run this module directly to do exactly    #
#  that against ONE url before scaling. Replace TEST_URL with a real         #
#  BusinessDay article URL once you have one.                                #
#                                                                            #
#      python -m data.fetchers.news.businessday                              #
# ------------------------------------------------------------------------- #
if __name__ == "__main__":
    import json

    TEST_URL = "https://businessday.ng/REPLACE-WITH-A-REAL-ARTICLE-URL/"

    fetcher = BusinessDayFetcher(max_requests=1)
    html = fetcher._get_html(TEST_URL, use_cache=True)
    if html is None:
        print("No HTML (fetch failed or blocked). See log; do not retry a 403.")
    else:
        record = fetcher._parse_article(html, TEST_URL)
        if record is None:
            print("Parsed nothing — adjust the selectors in _parse_article().")
        else:
            preview = dict(record)
            preview["published_date"] = str(preview["published_date"])
            preview["article_text"] = (
                preview["article_text"][:300] + " ...[truncated]"
            )
            print(json.dumps(preview, indent=2, ensure_ascii=False))
