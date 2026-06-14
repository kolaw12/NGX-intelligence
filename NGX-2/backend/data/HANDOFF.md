# Data Ingestion → Data Engineering Handoff

This document is the single source of truth for what the ingestion team
(Tomi + colleague) produces and what's available for the Data Engineering
team to consume. Start here before touching anything else in the repo.

**Last updated:** 2026-05-15 (backfill complete)
**Owner:** Tomi (tomioluwasile@gmail.com)
**Repo:** github.com/NUPAT-TECHNOLOGIES/ai-stock-broker-backend
**Branch:** `data-ingestion` (this is where all ingestion work lives)

---

## TL;DR

| Question | Answer |
|---|---|
| Can we start working? | **Yes — full historical price dataset ready.** |
| Is the dataset complete? | **Yes** — 272 of 292 NGX tickers have data (19 have no history on source — expected). |
| Is the schema stable? | **Yes** — won't change without telling you. |
| Is there daily auto-update? | **Implementation done, testing in progress.** No scheduler yet. |
| Where does data live? | GitHub (this repo) for now. Move to S3/HF later — your call. |
| Is news data here? | No — scaffolding exists, colleague handling four sources. |
| Is macro data here? | CBN fetcher skeleton exists; URL/parser verification pending. |
| What about corporate actions / fundamentals? | Not collected yet. Future work. |

---

## 1. What's Ready

### Historical OHLCV (prices) — COMPLETE

- **Per-ticker parquets:** `data/output/processed/prices/historical/<TICKER>.parquet`
  - **272 files**, ~7 MB total
  - One file per NGX ticker that has data on BroadStreet
- **Consolidated single table:** `data/output/processed/prices/historical_consolidated.parquet`
  - **1,125,466 rows across 272 tickers**
  - Date range: **1993-01-05 → 2026-05-15** (~33 years)
  - Long-format (one row per `(date, ticker)`)
  - **This is the canonical artifact to load into your warehouse.**
- **Manifest:** `data/output/processed/prices/historical/_manifest.json`
  - Run status, per-ticker stats, last-update timestamp
- **19 tickers with no data on source:** these exist in the NGX ticker
  list but BroadStreet has no historical prices for them (delisted,
  newly listed with no trades yet, etc.). They are excluded from the
  consolidated file. This is expected, not an error.

### Schema — historical_consolidated.parquet

| Column   | Type             | Description                                | Example      |
|----------|------------------|--------------------------------------------|--------------|
| `date`   | `datetime64[ms]` | Trading date                               | 2026-05-14   |
| `ticker` | `str`            | NGX ticker symbol                          | "MTN"        |
| `pclose` | `float64`        | Previous close                             | 99.00        |
| `high`   | `float64`        | Day's high                                 | 108.90       |
| `low`    | `float64`        | Day's low                                  | 99.00        |
| `close`  | `float64`        | Day's close                                | 108.90       |
| `volume` | `Int64`          | Shares traded (nullable integer)           | 32098599     |
| `change` | `float64`        | Change vs previous close (absolute, not %) | 9.90         |

**Notes:**
- Per-ticker parquets do NOT contain the `ticker` column (it's encoded in the filename). The consolidated parquet adds it.
- Dates are timezone-naive — they represent trading days, not instants.
- `volume = 0` is a legitimate value (no-trade days). Not NaN.
- `change` is in price units (NGN), not percentage.

### Source ticker registry

- **File:** `data/master/tickers.csv`
- Columns: `ticker, name, sector, sector_id, detail_url`
- 292 total tickers across 11+ NGX sectors
- This is the authoritative list — anything not here is not on NGX

---

## 2. What's Coming (in progress)

### Daily incremental updates

- `daily()` function in `data/pipeline.py` is **implemented** — being tested now
- Will fetch only new rows since each ticker's last known date
- Auto-rebuilds `historical_consolidated.parquet` at the end of each run
- **Scheduler not set up yet** — will use GitHub Actions cron or your orchestrator

### Macro data — CBN fetcher

- Skeleton at `data/fetchers/cbn.py` — written, **not yet verified against real CBN page**
- Pulls USD/NGN, EUR/NGN, GBP/NGN exchange rates
- Output schema: long-format `(date, indicator, value, source, unit)` matching section 11
- Requires ~30-45 min of URL / parser verification before first real run
- See section 11 for the broader macro plan (oil, MPR, CPI, etc.)

### News data (colleague's work)

- Scaffolding ready at `data/fetchers/news/` (see `data/fetchers/news/README.md`)
- 4 sources planned: Nairametrics, NGX Announcements, BusinessDay, Proshare
- Schema is defined but no real data yet
- Expected schema for news (when it arrives):

| Column              | Type              | Description                                 |
|---------------------|-------------------|---------------------------------------------|
| `published_date`    | `datetime64`      | Timezone-aware (Africa/Lagos preferred)     |
| `source`            | `string`          | Source ID (matches `news_sources.csv`)      |
| `headline`          | `string`          | Original headline                           |
| `article_text`      | `string`          | Plain text body (HTML stripped)             |
| `url`               | `string`          | Canonical URL                               |
| `mentioned_tickers` | `list[string]`    | NGX tickers mentioned in article            |

- Output location: `data/output/processed/news/articles/source=<id>/year=<YYYY>/articles.parquet`

---

## 3. What's NOT Done (be aware)

These exist in the project roadmap but are not yet collected. Do NOT design your warehouse around assumptions they exist.

| Dataset | Status | Priority | Notes |
|---|---|---|---|
| Daily incremental updates | **Done — tested live** | HIGH | `python -m data.pipeline daily` works; needs scheduler |
| Corporate actions (dividends, splits) | Not started | **CRITICAL** | Returns will be wrong without these. Flag this. |
| **NGX All-Share Index (snapshot)** | **Live — daily snapshot** | HIGH | `broadstreet_index.parquet` — 8 indicators per day. Back-history TODO. |
| Macro data — CBN exchange rates | **Live** | HIGH | 60K rows, 14 currencies, 24yr history |
| Macro data — Brent oil | **TEMP DISABLED** | HIGH | yfinance + protobuf incompatible with Python 3.14. Existing data preserved. |
| Macro data — NBS inflation / FRED Fed rate | Not started | HIGH | See section 11 |
| Quarterly / annual fundamentals | Not started | MEDIUM | Earnings, P/E, ratios |
| News data — BusinessDay | **Live — 20 articles** | MEDIUM | Colleague's work; live verified |
| News data — NGX Announcements | **Live — 20 articles, 10 tagged** | MEDIUM | Throttled; needs care |
| News data — Nairametrics / Proshare | Stubs only | MEDIUM | Nairametrics in progress; Proshare blocked (SSL cert expired) |
| Real-time / intraday prices | Not planned for MVP | LOW | End-of-day is the target |

---

## 4. How the Pipeline Works

### Commands

```bash
# Discover all NGX tickers (already done — tickers.csv exists)
python -m data.pipeline discover

# Backfill historical OHLCV for all tickers (resumable)
python -m data.pipeline backfill

# Backfill just specific tickers (pilot mode)
python -m data.pipeline backfill MTN GTB DCE

# Daily incremental price updates (implemented + tested)
python -m data.pipeline daily

# Rebuild the consolidated single-table parquet
python -m data.pipeline consolidate

# Macro data fetchers — CBN exchange rates + Brent crude oil (Yahoo)
python -m data.pipeline macro

# News fetchers — NGX Announcements + BusinessDay (20 articles/source by default)
python -m data.pipeline news

# Override the news article cap (e.g. for an initial backfill)
NEWS_MAX_ARTICLES=200 python -m data.pipeline news
```

### Suggested daily cron sequence

```bash
# Every weekday after market close (e.g. 17:00 WAT)
python -m data.pipeline daily       # incremental price updates + auto-consolidate
python -m data.pipeline macro       # CBN rates + Brent oil (~20s)
python -m data.pipeline news        # NGX + BusinessDay articles (~5 min)
```

### Resumability

- `backfill` skips tickers that already have a parquet — safe to re-run after crashes / interruptions
- `consolidate` always rebuilds from scratch — safe to re-run any time
- After every `backfill`, `consolidate` runs automatically. You always have a fresh single-table artifact.

### Safety controls

- **Killswitch:** `touch data/.killswitch` — next HTTP request aborts cleanly
- **Request cap:** Hard-coded per-run cap to prevent runaway scraping
- **Polite delays:** 2-3 seconds between requests, env-tunable
- **Retry logic:** Exponential backoff on transient errors via tenacity
- **Soft-block detection:** Aborts on login redirects, captchas, 403/451

---

## 5. Directory Map

```
data/
├── HANDOFF.md                            ← you are here
├── KNOWN_ISSUES.md                       ← gotchas you should know about
├── master/
│   ├── tickers.csv                       ← 292 NGX tickers
│   └── news_sources.csv                  ← news source registry
├── config.py                             ← env vars, paths, politeness settings
├── pipeline.py                           ← CLI orchestrator
├── fetchers/
│   ├── broadstreet.py                    ← price fetcher (working)
│   ├── cbn.py                            ← (stub — for future macro work)
│   ├── yfinance.py                       ← (stub — for future cross-validation)
│   └── news/                             ← news fetchers (scaffolding ready)
│       ├── README.md                     ← colleague's handbook
│       ├── base.py                       ← shared base class
│       ├── nairametrics.py               ← (stub)
│       ├── ngx_announcements.py          ← (stub)
│       ├── businessday.py                ← (stub)
│       └── proshare.py                   ← (stub)
├── validators/
│   └── basic_validator.py
└── output/
    ├── raw/                              ← cached HTML (debug/replay)
    │   └── broadstreet/
    └── processed/                        ← THE ARTIFACTS YOU CONSUME
        ├── prices/
        │   ├── historical/               ← per-ticker parquets
        │   │   ├── <TICKER>.parquet
        │   │   └── _manifest.json
        │   └── historical_consolidated.parquet   ← ← ← canonical single table
        └── news/
            ├── articles/                 ← per-source-per-year parquets (when ready)
            ├── _manifest.json
            └── KNOWN_ISSUES.md
```

---

## 6. Open Questions — Your Call

These decisions are yours, not ours. Tell us what you decide.

### Q1: Long-term storage location

GitHub works for now (5 MB), but won't scale once daily updates accumulate.
**Options:**

| Option | Pros | Cons |
|---|---|---|
| Stay on GitHub | Already set up, free, version-controlled | Repo bloat over time, 100 MB file limit, slow clones |
| **AWS S3 / Backblaze B2** | Cheap, scalable, standard pattern | Requires AWS/B2 setup, credentials management |
| **Hugging Face Datasets** | Free for public, ML-ready, versioned | Locks you in somewhat, smaller ecosystem |
| Cloud warehouse (BigQuery, Snowflake) | SQL, joins, fast queries | More expensive, more setup |

**Recommendation:** Stay on GitHub for the next 2-3 months while the pipeline stabilizes. Plan a migration once daily updates start producing significant volume. Your call.

### Q2: Daily update scheduling

Once `daily()` is implemented, **someone** has to schedule it. Who owns this?

| Option | Pros | Cons |
|---|---|---|
| Ingestion team runs GitHub Actions cron | Easy, free, no infra | Tied to GitHub, less observable |
| Data Eng team runs in their orchestrator (Airflow / Prefect) | Centralized monitoring, proper alerting | More setup, requires coordination |

**Recommendation:** Discuss in our first call. Likely answer: GitHub Actions for the next few weeks, then migrate to your orchestrator once you have one set up.

### Q3: Schema changes

Are there columns you'd want added/renamed/typed differently? Examples:
- Convert `volume` from `Int64` to `int64` (no nullable)?
- Rename `pclose` to `prev_close`?
- Add a `currency` column (always "NGN") for explicitness?
- Use `datetime64[ns, Africa/Lagos]` instead of timezone-naive?

**Flag this NOW, before we backfill the remaining 105 tickers.** Schema changes after backfill = pain.

### Q4: Refresh cadence for the consolidated file

Right now `historical_consolidated.parquet` is rebuilt after every `backfill` run. Once daily updates land, should it:
- Be rebuilt fully every day (simple, fine at current scale)?
- Be incrementally appended (faster, more complex)?
- Be replaced by a partitioned dataset (`prices/ticker=X/data.parquet`)?

---

## 7. How to Get the Data

### Today (while data lives on GitHub)

```bash
git clone https://github.com/NUPAT-TECHNOLOGIES/ai-stock-broker-backend.git
cd ai-stock-broker-backend
git checkout data-ingestion
ls data/output/processed/prices/
```

```python
import pandas as pd
df = pd.read_parquet("data/output/processed/prices/historical_consolidated.parquet")
print(df.shape, df.columns.tolist())
```

### Later (once moved to S3 / HF / warehouse)

To be determined per Q1 above.

---

## 8. Contact / Escalation

- **Anything about prices / backfill / pipeline:** Tomi (tomioluwasile@gmail.com)
- **Anything about news ingestion:** Tomi's colleague (TBD)
- **Schema questions:** Tomi — schema changes should be discussed before committing
- **Production / scaling questions:** Discuss with the Data Engineering team lead

If you find data quality issues (gaps, duplicates, weird values), please file
them in `data/output/processed/prices/historical/KNOWN_ISSUES.md` or message
Tomi directly.

---

## 9. Known Limitations (read before you build on top of this)

1. **Empty-history tickers are skipped, not represented.** Some NGX tickers (like ASX) have no price data in BroadStreet. They are excluded from the consolidated file. Manifest may show them as "failed" — that's expected, not an error.

2. **Some tickers have huge date gaps.** A company may have traded 2005-2010, gone silent, then resumed. The data reflects what BroadStreet has. Don't assume continuous daily coverage.

3. **Volume can be zero.** Days with no trades show `volume = 0`. Don't filter these out blindly — they're real data points.

4. **No corporate actions adjustments.** Prices are AS REPORTED. If a stock split 2-for-1, the price drops in half — that's real data, not an error, but it means raw returns will look distorted across split events. **This is critical for any return calculations downstream.**

5. **`change` is in price units, not percentage.** A close of 100 with `change=5` means the price went from 95 → 100, not that it gained 5%.

6. **All times are trading-day granularity.** No intraday data.

7. **JS-rendered cells return empty (older known issue, not relevant to historical prices).** This affected the original exchange-rate POC, not the current historical price pipeline.

---

## 10. Open Tasks Tracker

| Task                              | Owner        | Status        |
|-----------------------------------|--------------|---------------|
| Historical backfill (full 292 tickers) | Tomi   | ✅ **Complete** (272 with data, 19 with no source data) |
| Implement `daily()` function      | Tomi         | ✅ **Done — testing in progress** |
| CBN macro fetcher skeleton        | Tomi         | ✅ **Done — URL/parser verification pending** |
| Set up GitHub Actions scheduler   | Tomi or DE   | Not started   |
| Move storage off GitHub           | DE team      | Not started   |
| Build warehouse loader            | DE team      | Not started   |
| News fetcher: Nairametrics        | Colleague    | Not started   |
| News fetcher: BusinessDay         | Colleague    | Not started   |
| Corporate actions ingestion       | Tomi (next)  | Not started   |
| NGX index data                    | Tomi (next)  | Not started   |
| Brent oil / FRED / NBS fetchers   | Tomi (next)  | Not started   |

---

## 11. Macro Data — Next Workstream (HIGH PRIORITY)

NGX is unusually sensitive to a few global macro signals. The model will
have a serious blind spot without these. This is the planned next workstream
on the ingestion side, immediately after `daily()` is implemented.

### What to ingest

| Signal | Source | Frequency | Why it matters for NGX |
|---|---|---|---|
| **Brent crude oil price** | EIA API / Yahoo Finance / TradingEconomics | Daily | Nigeria's economy is ~80% oil-dependent for FX. Oil moves the whole NGX. |
| **USD/NGN exchange rate** | CBN (cbn.gov.ng) | Daily | Drives inflation, foreign investor flows, import costs |
| **CBN Monetary Policy Rate (MPR)** | CBN press releases | Event-based (~6 per year) | Moves the entire banking sector and bond yields |
| **Inflation rate (CPI)** | NBS (nigerianstat.gov.ng) | Monthly | Sets the real return floor for any investment |
| **Foreign reserves** | CBN | Weekly | Indicates FX stability outlook |
| **US Fed rate decisions** | FRED API | Event-based (8 per year) | Drives global emerging-market capital flows; affects NGX foreign inflows |

### Proposed shape

Single long-format parquet at:
```
data/output/processed/macro/macro_indicators.parquet
```

With columns:
| Column | Type | Description |
|---|---|---|
| `date` | `datetime64` | Observation date |
| `indicator` | `string` | e.g. `"brent_oil_usd"`, `"usdngn_rate"`, `"cbn_mpr"`, `"ng_cpi_yoy"` |
| `value` | `float64` | Numeric value (rate, price, level) |
| `source` | `string` | e.g. `"eia"`, `"cbn"`, `"nbs"`, `"fred"` |
| `unit` | `string` | e.g. `"USD/barrel"`, `"NGN/USD"`, `"percent"` |

### Status

- Code: `data/fetchers/cbn.py` exists as a stub (for CBN data). Other fetchers not started.
- Estimated effort: ~1-2 weeks of part-time work for all six signals
- Will be wired into `daily()` so it runs alongside price updates

### Why this can't wait

If the model has prices + Nigerian news but **no oil/FX/MPR data**, it'll be
confidently wrong during macro-driven moves (which is most large NGX moves).
This is not "nice to have" — it's the second-most-important data stream
after prices themselves.

---

**Welcome to the project. Read this whole doc, then let's talk.**
