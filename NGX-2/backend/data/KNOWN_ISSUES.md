# Known Issues & Gotchas — Data Layer

Things the data layer maintainer has hit and worked around — read this before you debug or build on top of these datasets.

---

## Scope — what this dataset does NOT have

Set expectations before you assume something is here. The data is **end-of-day equity prices** for NGX-listed companies. Anything outside that is either not built yet or blocked.

### Granularity / frequency

| Missing | Implication |
|---|---|
| **Intraday OHLC** (hourly, minute, tick) | Daily close is the finest resolution available |
| **Real-time / live quotes** | Data lags end of trading day — typically refreshed once per day |
| **Pre-market / after-hours prints** | Only regular-session prices |
| **Volume profile / time-and-sales** | Only daily aggregate volume |

### Market microstructure

| Missing | Implication |
|---|---|
| **Bid / ask quotes** | No spread analysis; close price only |
| **Order book depth (L2/L3)** | No market-impact modeling |
| **Trade-by-trade transactions** | No detection of block trades, sweeps, or hidden orders |

### Price adjustments

| Missing | Implication |
|---|---|
| **Split-adjusted prices** | Raw prices only. **A stock that did a 10-for-1 split will appear to drop 90% on the split date.** ML models will see this as a crash unless you adjust. |
| **Dividend-adjusted returns (total return series)** | Pure price series. To compute total return, you need to merge with dividend history. |
| **Corporate-actions history** | We have access to BroadStreet's "Dividend History" page per ticker, but it's not ingested yet. |

### Fundamentals & forward-looking

| Missing | Implication |
|---|---|
| **Fundamentals over time** (historical PE/EPS/Mkt Cap by quarter or year) | Stage 3 will add today's snapshot; building a back-series will accumulate over time, not retroactively |
| **Analyst estimates / consensus forecasts** | No forward EPS, no price targets |
| **Earnings call transcripts** | NLP team would need a different source |
| **Management guidance** | Not available |

### Macro & cross-asset

| Missing | Implication |
|---|---|
| **FX rates (NGN/USD/etc.)** | Blocked — BroadStreet's exchange-rate page is JavaScript-rendered. See item #3 below. |
| **CBN policy rates / inflation / GDP** | Not yet built. Planned via CBN portal fetcher. |
| **Bond yields, oil prices, commodity prices** | Not in scope of this layer |
| **Sector ETFs / index composition** | NGX-ASI index has its own page (`asiDetail.php`) but not ingested yet |

### Alternative data

| Missing | Implication |
|---|---|
| **News articles** | NLP team's input — not yet built, planned via BroadStreet "Headlines" page |
| **Sentiment scores** | NLP team's output, not source data |
| **Insider transactions / 13F equivalents** | NSE has filings but not on BroadStreet |
| **Major shareholder changes over time** | BroadStreet has a "Major Holders" page — snapshot only, no history |
| **ESG ratings** | Not available |
| **Options, futures, derivatives** | NGX has limited derivatives trading; not covered here |

### Data freshness reality

- **Latest available date** on a given parquet = the most recent trading day BroadStreet has published, **NOT today's live price**.
- After daily refresh (Stage 3) goes live, latest date will typically be **T-0 close** (after market hours) or **T-1** if you read before EOD.
- Don't promise "real-time" anywhere in the product. This is **end-of-day delayed**.

### TL;DR for downstream teams

- **ML team:** treat all prices as raw, unadjusted, end-of-day. Build a corporate-actions step into your feature pipeline OR filter out tickers with known splits.
- **NLP team:** no news data yet. Coordinate with data-layer maintainer on the schema you need before we build the scraper.
- **Data Eng team:** the pipeline produces daily snapshots, not streams. Anyone asking for "live" data needs to be redirected to a market-data vendor.
- **Anyone planning UI:** explicitly label timestamps as "End of trading day, [DATE]". Never imply live data.

---

## 1. BroadStreet ticker codes ≠ NGX official tickers

**Problem:** BroadStreet uses legacy 3-letter codes that don't match the modern NGX ticker conventions used by yfinance, Bloomberg, NGX official portal, etc.

| BroadStreet | NGX official | Company |
|---|---|---|
| `DCE` | `DANGCEM` | Dangote Cement |
| `DSR` | `DANGSUGAR` | Dangote Sugar |
| `MTN` | `MTNN` | MTN Nigeria |
| `NES` | `NESTLE` | Nestle Nigeria |
| `SPD` | `SEPLAT` | Seplat Petroleum |
| `BUA` | `BUACEMENT` | BUA Cement |
| `UNL` | `UNILEVER` | Unilever Nigeria |
| `NBL` | `NB` | Nigerian Breweries |
| `GTB` | `GTCO` | Guaranty Trust Holding |
| `ZEN` | `ZENITHBANK` | Zenith Bank |

**Impact:** Any cross-source join (yfinance, news APIs, NGX official, Bloomberg) needs a **ticker mapping table**. Not blocking for BroadStreet-only ML; blocking the moment anyone tries to enrich.

**Workaround:** None automated. To build the mapping, manually align `name` field in `master/tickers.csv` against the NGX official listings.

**Status:** Documented, not yet solved. Punt to whoever needs the cross-source join.

---

## 2. Broken pagination on BroadStreet historical pages

**Problem:** When you request a `qhp` page beyond the available data range, BroadStreet's server **returns the last real page again** instead of an empty response. Without detection, the loop runs forever (or until `max_pages` cap).

**Symptom we hit:** GTB page 200 returned 34 rows ending 1993-09-23. Pages 250, 300, 315… all returned the **same** 34 rows.

**Workaround:** `fetch_historical_prices` tracks every date seen across pages. When a page contributes zero new dates, we break the loop. Implemented in `data/fetchers/broadstreet.py`.

**Status:** Fixed. But if BroadStreet ever changes their pagination behavior again, this check is the canary — review the duplicate-page log lines.

---

## 3. Exchange-rate page is JavaScript-rendered

**Problem:** `https://broadstreetlagos.com/exchange-rate.php` displays NGN cross rates in the browser, but the **numbers are injected by JavaScript** (`coinmill.com/frame.js` widget). `requests` doesn't execute JS, so we get an HTML skeleton with `<script>currency_show_conversion(...)</script>` literal text in cells — no actual rate values.

**Impact:** Macro/FX data is **blocked via this path**.

**Workarounds (none implemented yet):**
- Find a different BroadStreet endpoint that serves rates server-rendered
- Switch this single fetcher to Playwright/Selenium (heavy)
- Use a different source entirely (CBN portal, exchangerate.host, openexchangerates)

**Status:** Open. Not blocking — equities data (the primary requirement) is fine without it.

---

## 4. Pre-2000 volume data is unreliable

**Problem:** Old historical rows from the 1990s often have `volume = 0`. BroadStreet didn't (or couldn't) track volume that far back for many tickers.

**Example (GTB):**
```
1993-09-23  close=12.60  volume=0
1993-09-24  close=12.75  volume=0
```

**Impact:** Any ML feature that depends on volume (turnover, liquidity, momentum) will be misleading for these dates. Models trained on raw data may extract spurious "low volume" signals from pre-2000 records.

**Workaround:** ML team should either:
- Filter to `date >= 2000-01-01` before training, OR
- Treat `volume = 0` as "missing" (replace with NaN), OR
- Use a different feature for pre-2000 data

**Status:** Documented. ML team's call on how to handle.

---

## 5. Ticker continuity across corporate reorganizations

**Problem:** Some BroadStreet tickers represent the **same underlying entity** across mergers, holding-company conversions, and name changes — but you can't tell from the ticker alone.

**Example:** `GTB` has data from 1993, but "Guaranty Trust Holding Company Plc" only existed from 2021. The price series is spliced together from:
- 1990-1996: Guaranty Trust Bank Ltd
- 1996-2007: GTBank Plc
- 2007-2021: Guaranty Trust Bank Plc
- 2021-present: Guaranty Trust Holding Company Plc

**Impact:** For ML this is **a feature, not a bug** — continuous price series across reorganizations is what you want for time-series modeling. But fundamentals (PE, EPS) from before/after a holdco conversion may not be directly comparable.

**Workaround:** None needed for price models. For fundamental analysis, treat pre/post-reorganization periods as different regimes.

**Status:** Documented. Will become relevant when we add fundamentals.

---

## 6. Defunct / delisted companies are included

**Problem (intentional):** Companies that have been merged, wound up, or delisted — Afribank, First Inland Bank, Diamond Bank, Skye Bank, etc. — are still in the master ticker list and have parquets.

**Impact:** ML training on this data is **survivorship-bias-free**, which is what you want. Models trained on only surviving companies systematically overestimate returns.

**Workaround:** ML team can filter to "active" tickers if they want, but **should not** unless they're comparing against a specific universe.

**Status:** Documented. Working as intended.

---

## 7. Tickers with `name == ticker` (cosmetic only)

**Problem:** Two tickers have a `name` field that's identical to the ticker because BroadStreet's HTML for those entries doesn't include a full company name anywhere:

- `ECO.f` (Banking)
- `IHS` (Telecommunication)

**Impact:** Cosmetic. Joins and lookups still work because `ticker` is the primary key.

**Workaround:** Manually patch `data/master/tickers.csv` with the real names if it bothers you:
- `IHS` → IHS Holding Limited (an infrastructure/towers company)
- `ECO.f` → likely a frozen/historical Eco Bank record (the `.f` suffix is BroadStreet's convention for a defunct variant)

**Status:** Acceptable for MVP. Punt unless someone complains.

---

## 8. Some tickers may share a name with different sectors

**Problem:** Discovery is sector-by-sector and dedupes by ticker. If a ticker accidentally appears in two sectors (e.g., reclassification), only the first-encountered sector is kept.

**Impact:** Sector classification might be slightly wrong for a handful of tickers.

**Workaround:** Cross-reference `master/tickers.csv` against NGX's official sector classifications when sector accuracy matters.

**Status:** Low priority. Affects probably <5 tickers.

---

## 9. Manifest reflects the most recent run, not full disk state

**Problem:** `_manifest.json` records the tickers processed **in the most recent backfill run**. If you ran backfill in pilot mode for `GTB DCE MTN` then later ran the full backfill, the manifest now shows tickers from the full run — but **DCE** might appear as "skipped" because the parquet already existed.

**Impact:** The `tickers` dict in the manifest is **not a complete inventory** of what's on disk. To get the full inventory:

```python
from pathlib import Path
all_parquets = list(Path("data/output/processed/prices/historical").glob("*.parquet"))
```

**Workaround:** Always scan the directory for the actual file list. Use the manifest for the most-recent-run summary only.

**Status:** Documented. Could be improved by maintaining a separate "inventory" manifest, but not blocking.

---

## 10. Authentication uses borrowed credentials

**Problem:** The BroadStreet account credentials in `.env` belong to a third party who lent them to us. If the account gets banned, the pipeline stops entirely.

**Impact:** Operational risk. Every request goes against this one account.

**Workarounds in place:**
- Polite request delays (2-3s with jitter)
- Realistic User-Agent + From-email header
- Single session per run, never repeated logins
- Soft-block detector that stops on the first sign of trouble
- Killswitch for manual abort
- Hard per-run request cap (10,000 backfill, 50 discovery)

**Workaround (long-term):** Acquire our own BroadStreet account, or move to a paid data source where commercial use is permitted.

**Status:** Mitigated, not eliminated.

---

## 11. Corrupt historical rows — 2010-08-05 cluster + delisted UT* tickers

**Problem:** Surfaced by the dbt data-quality tests after the warehouse migration. ~0.58% of historical rows fail physical-sanity assertions on `volume > 0` days:

| Test | Bad rows | Pattern |
|---|---|---|
| `close > 0` | 66 | `close <= 0` despite real volume |
| `high >= close` | 6,427 | by far the largest cluster |
| `high >= low` | 72 | `low > high` (impossible) |
| `volume >= 0` | 11 | negative volume |

Two clear sources:

- **2010-08-05** has a mass cluster of corrupt rows across many tickers (FLR, FIH, FAN, CUS, CCN, FCM, AFB, CAI, CAP, FTN, BAG, FID, DIA, BIG, CVX, CRU, DFM, 7UP, AIC, CAD, FIN, APL, DCM, BOC, etc.). All show **negative `pclose`** (physically impossible), `close = 0` despite real `volume`, and `change = -pclose`. The math is self-consistent within each row, so it isn't our parser column-swap — it's BroadStreet serving garbage for that one day, likely a backend migration / restatement.
- **`UT*`-prefix tickers** (`UTVSF`, `UTNEW`, `UTVGF`) — delisted entities with junk historical values throughout.

**Impact:** Any downstream feature using `pclose`, `close`, or `change` on these rows will produce nonsense. Returns calculations will explode at these points. The volume-weighted features won't be saved by the `volume > 0` predicate alone — the values themselves are corrupt, not the volume column.

**Workaround (current):** `dbt_utils.expression_is_true` tests on these constraints are set to `severity: warn` in [dbt/models/staging/schema.yml](../dbt/models/staging/schema.yml) so the nightly job doesn't fail on immutable historical garbage. Counts are visible in every `dbt build` log.

**Proper fix (TODO):** Either (a) delete the known-bad rows from BigQuery as a one-off SQL cleanup, or (b) add an upstream parser guard in `data/fetchers/broadstreet.py` that rejects rows with `pclose < 0` / `close < 0` and re-run backfill for the affected dates. Best paired with corporate-actions ingestion, since 2010-08-05 looks like an NGX-wide corporate-event day.

**Status:** Documented; tests warn-level. Not blocking the warehouse migration or the daily refresh.

---

## Reporting new issues

When you hit something not in this doc:

1. Save the failing input (raw HTML in `data/output/raw/...`)
2. Capture the log excerpt from `data/logs/broadstreet.log`
3. Open an issue on the GitHub repo with both attached
4. Add a section here describing what you found
