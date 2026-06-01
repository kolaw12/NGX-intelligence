# News Ingestion — Handbook

Welcome. This document is your guide to building the news ingestion layer of
the AI Stock Advisor project. Read this whole thing before you start coding.

---

## 1. The Goal

Collect news articles about NGX-listed companies from Nigerian financial news
sources. Your output feeds downstream teams who turn raw text into the
"explanation layer" of our stock advisor — the part that lets the product
tell users **why** a stock moved, not just **what** it did.

---

## 2. Who Uses This Data, And What For

Your work is the **foundation** for several teams downstream. The cleaner and
more consistent your output, the better everything built on top works.

```
[1] YOU collect raw news articles
    Output: parquets with raw headline + article_text
                              ↓
[2] DATA ENGINEERING TEAM ingests it
    - Loads parquets into the data warehouse
    - De-duplicates across sources (same story, different sites)
    - Normalizes timestamps (timezone, format)
    - Adds metadata, lineage tracking
    - Exposes a clean "articles" table to consumers
                              ↓
[3] NLP TEAM (subset of ML Engineering) processes the text
    - SENTIMENT ANALYSIS: scores each article positive / negative / neutral
    - NAMED ENTITY RECOGNITION (NER): which companies, people, places mentioned
    - TOPIC MODELING: what themes (earnings, M&A, regulation, sector trends)
    - EVENT DETECTION: identifies key events (scandals, earnings releases,
      leadership changes)
    - HEADLINE CLASSIFICATION: bullish / bearish / neutral signal
    Output: enriched articles + sentiment scores + event tags
                              ↓
[4] ML TEAM (broader) builds the actual stock advisor model
    Combines:
      - Tomi's price data (what stocks did)
      - NLP team's sentiment / events (why stocks did it)
      - Fundamentals, macro (context)
    Trains models that predict:
      - Price moves over various horizons
      - Risk levels
      - Sector rotation signals
                              ↓
[5] BACKEND / API TEAM serves recommendations
    Wraps ML model outputs in API endpoints
    Adds business logic (e.g. don't recommend stocks below a price floor)
                              ↓
[6] FRONTEND TEAM builds the user interface
    User sees:
      "Buy MTN — strong Q3 earnings drove 5% rally,
       momentum signals positive, sentiment up 30%"
                              ↓
[7] END USER (retail investor) makes a decision
```

**The bottom line:** news data isn't just "extra context" — it's the
*explanation layer* of our entire product. The model can predict that a
stock will go up; news data lets the model **explain why**. That explanation
is what makes our advisor *trustworthy* to users — and that trust is the
entire reason this product exists.

If your news data is wrong, late, or inconsistent, every team after you
suffers. If it's solid, every team after you can do their best work.

---

## 3. The Schema Contract

Every fetcher you write **must** produce a DataFrame with these exact columns,
in this order, with these types. This is non-negotiable — downstream teams
depend on it.

| Column              | Type           | Example                                      |
|---------------------|----------------|----------------------------------------------|
| `published_date`    | `datetime64`   | `2026-05-14 09:30:00+01:00` (Africa/Lagos)   |
| `source`            | `string`       | `"nairametrics"` — matches `source_id` in `news_sources.csv` |
| `headline`          | `string`       | `"MTN Nigeria posts ₦690bn Q3 revenue"`      |
| `article_text`      | `string`       | full article body, plain text, **no HTML**   |
| `url`               | `string`       | `https://nairametrics.com/2026/05/14/mtn-...` |
| `mentioned_tickers` | `list[string]` | `["MTN"]` — NGX tickers mentioned (empty list `[]` is OK for v1) |

These columns are defined as `ARTICLE_COLUMNS` in `base.py`. Use that
constant rather than retyping the list — it keeps everything in sync.

**Rules:**
- Use **timezone-aware** timestamps. Africa/Lagos (WAT, UTC+1) is preferred.
  If the source only gives a date, set the time to `00:00:00+01:00`.
- `article_text` must be **plain text** — strip HTML tags, scripts, ads.
  But DON'T strip aggressively (no stemming, no lowercasing, no removing
  punctuation). Leave that to the NLP team.
- `url` must be the **canonical** URL (no query parameters like `?ref=share`).
- Save as parquet to:
  ```
  data/output/processed/news/articles/source=<source_id>/year=<YYYY>/articles.parquet
  ```
  Use the `self.write_parquet(df, year)` helper in `base.py` — it enforces
  the path and validates the schema.

---

## 4. Sources to Tackle

In priority order, with current assignments:

| Source              | Owner          | Priority | Why                                                       |
|---------------------|----------------|----------|-----------------------------------------------------------|
| Nairametrics        | **Tomi**       | 1        | Most NGX-focused; clear ticker tagging                    |
| BusinessDay Nigeria | **Colleague**  | 1        | Major business daily; broad coverage                      |
| NGX Announcements   | unassigned     | 1        | PRIMARY source — companies required to disclose here      |
| Proshare Nigeria    | unassigned     | 2        | Investor-focused analysis                                 |
| Premium Times, CBN  | unassigned     | 3+       | Lower priority; tackle after the above are solid          |

**Your focus: `businessday.py` only for now.** Tomi is handling Nairametrics
in parallel so the two of you can compare approaches and share patterns.

The source registry lives in `data/master/news_sources.csv`. Add new sources
there before writing a fetcher for them.

### Scope: Nigerian-only for now

**Phase 1 (your work): Nigerian sources only.** Don't expand beyond the four
listed above, even if you come across interesting global sources. The goal
of Phase 1 is to get the pipeline working end-to-end with real articles
flowing — quality and reliability over breadth.

**Phase 2 (later, not your concern yet):** We'll add targeted global news
sources that affect NGX specifically — oil-price reporting, USD/NGN-related
news, regional African business news (because NGX companies like MTN have
international parents). This is Phase 2 work, not your focus right now.

Note: NGX is also affected by global *macro time-series data* (oil prices,
exchange rates, interest rates). Those aren't news articles — they're
numbers in a table — and they're a separate workstream owned by Tomi.
Don't try to collect them here.

---

## 5. Reference Implementation

There's already a working fetcher in `data/fetchers/broadstreet.py`. Read it.
The patterns are identical for news — only the parsing differs:

- Session management with polite user-agent ✓
- Polite delays between requests (2–3 seconds) ✓
- Retry on transient errors (tenacity, exponential backoff) ✓
- Killswitch support (touch `data/.killswitch` to abort) ✓
- Request cap per run ✓
- Soft-block detection (captcha, paywall, 403) ✓
- Raw HTML caching for replay/debugging ✓
- Progress manifest written after each unit ✓

**All of that scaffolding is already provided in `base.py`**. You just
implement `fetch_articles()` in your subclass. Look at how
`BroadStreetFetcher.fetch_historical_prices()` is structured — your method
should follow the same shape:

1. Iterate (pages, dates, categories — depends on the source)
2. Call `self._polite_get(url, save_raw_to=cache_path)` to fetch HTML
3. Parse the HTML (BeautifulSoup recommended)
4. Build a list of dicts matching `ARTICLE_COLUMNS`
5. Return as a `pandas.DataFrame`

---

## 6. Politeness Rules (READ THIS — DO NOT SKIP)

We are guests on these sites. Treat them well.

- **Always check `robots.txt`** for every source before scraping. Respect it.
  If `robots.txt` says don't crawl a path, don't crawl it.
- **Minimum 2–3 second delay between requests.** Already enforced by
  `_polite_get()` — don't bypass it.
- **Identify the scraper honestly.** The user-agent in `config.py` includes
  a `From:` email so site operators can contact us. Don't change this to
  pretend to be a regular browser.
- **If you get `429 Too Many Requests` or `403 Forbidden`: STOP immediately.**
  Don't retry. Tell Tomi. We will either back off, switch IPs, or stop
  scraping that source.
- **Never run two fetchers against the same source in parallel.** One source,
  one fetcher, sequential.
- **Don't scrape during peak hours if avoidable** — late evening / overnight
  is friendlier.

---

## 7. Legal & Ethical Rules

This matters. We're a commercial project, and news articles are copyrighted.

| ✅ DO                                                       | ❌ DON'T                                              |
|------------------------------------------------------------|-------------------------------------------------------|
| Store raw article text **internally** for model training   | Redistribute full article text publicly in our app    |
| Show users **headlines + short snippets + a link** to the source | Show full articles in our product without licensing |
| Cache raw HTML for debugging                                | Share scraped data with third parties                 |
| Respect `robots.txt`                                       | Bypass it because "everyone does"                     |
| Use real user-agent + contact email                         | Pretend to be a regular browser                       |
| Stop immediately on 429 / 403                              | Switch IPs and keep hammering                         |

If a site explicitly asks us to stop, we stop. If a story is sensitive
(scandal, investigation), be extra careful about how it appears in our
product. When in doubt, ask Tomi.

---

## 8. The `mentioned_tickers` Field

This field links articles to NGX tickers — critical for downstream models.

**For v1**, you can return an empty list `[]` for every article. Just get
articles collected.

**For v2** (after Week 2), populate it with a simple lookup:

```python
import pandas as pd
tickers_df = pd.read_csv("data/master/tickers.csv")
# Build a map of {company_name_lower: ticker, ticker: ticker}
# For each article, scan article_text for matches.
```

This is a basic string-match approach. The NLP team will build a proper
Named Entity Recognition model later — yours just needs to be a reasonable
first pass.

---

## 9. Milestones

| Milestone | Target                                                          |
|-----------|-----------------------------------------------------------------|
| Week 1    | Nairametrics fetcher returns 100+ articles; schema matches      |
| Week 1    | NGX Announcements fetcher returns 50+ announcements             |
| Week 2    | BusinessDay + Proshare fetchers working                         |
| Week 2    | All four fetchers integrated into a `news` pipeline command     |
| Week 3    | De-duplication across sources                                   |
| Week 3    | `mentioned_tickers` populated via lookup                        |
| Week 4    | Daily incremental runs (not just full backfills)                |

---

## 10. When to Ask for Help

Don't burn time spinning. Ask **early**, not after a day of frustration.

- **Stuck >30 min on the same problem** → ask Tomi
- **Site returns 403 / 429 / captcha** → STOP, ask before proceeding
- **Schema feels wrong for a particular source** → ask before changing it
- **HTML structure is too dynamic to parse with BeautifulSoup** → ask;
  we may need Selenium / Playwright for that source
- **You're not sure if a behavior is acceptable** → ask; it's cheaper to
  align early than to refactor later

---

## 11. What NOT to Do

- ❌ Don't change the schema (column names, types, order) without discussing
- ❌ Don't use a different output storage location
- ❌ Don't skip the HTML cache layer — we need it for replay and debugging
- ❌ Don't write your own retry logic — reuse `_polite_get` from `base.py`
- ❌ Don't push without running your code at least once
- ❌ Don't merge to `main` — push to `data-ingestion` (or a feature branch
  off `data-ingestion`)
- ❌ Don't commit your `.env` file
- ❌ Don't commit cached HTML to git (it goes under `data/output/raw/news/`
  which should be gitignored or kept local — confirm with Tomi)

---

## 12. Where Things Live

```
data/
├── master/
│   └── news_sources.csv             ← source registry (add new sources here)
├── fetchers/
│   ├── broadstreet.py               ← reference implementation (READ THIS)
│   └── news/
│       ├── __init__.py
│       ├── README.md                ← you are here
│       ├── base.py                  ← shared base class (don't modify lightly)
│       ├── nairametrics.py          ← your work
│       ├── ngx_announcements.py     ← your work
│       ├── businessday.py           ← your work
│       └── proshare.py              ← your work
└── output/
    ├── raw/
    │   └── news/<source_id>/        ← cached HTML (gitignored)
    └── processed/
        └── news/
            ├── articles/
            │   └── source=<id>/year=<YYYY>/articles.parquet  ← your output
            ├── _manifest.json       ← run progress tracking
            └── KNOWN_ISSUES.md      ← document anything unexpected
```

---

## 13. First Day Checklist

Before writing any code:

- [ ] Read this whole document
- [ ] Read `data/fetchers/broadstreet.py` (it's a working reference)
- [ ] Read `data/fetchers/news/base.py` (this is what you'll inherit from)
- [ ] Check `data/master/news_sources.csv` (source registry)
- [ ] Check Nairametrics' `robots.txt` and decide what's allowed
- [ ] Talk to Tomi about anything unclear

Then:

- [ ] Inspect Nairametrics manually in a browser — find the article-listing
      pattern (RSS feed? Category pages? Archive pages?)
- [ ] Start with a tiny version that fetches 1 page, parses 1 article, prints
      a dict matching `ARTICLE_COLUMNS`. Get one full article end-to-end
      before scaling.

---

## Questions? Ask early. Good luck.
