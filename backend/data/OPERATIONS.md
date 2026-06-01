# Operations Guide — Data Layer

How to run the pipeline, monitor it, kill it cleanly, and recover from common failure modes.

---

## TL;DR commands

```bash
# Setup (once)
cd ai-stock-broker-backend
source ../venv/Scripts/activate         # Git Bash on Windows

# Pipeline stages
python -m data.pipeline discover                    # Stage 1: master ticker list
python -m data.pipeline backfill                    # Stage 2: historical OHLCV (all 292)
python -m data.pipeline backfill GTB DCE MTN        # Stage 2: pilot subset
python -m data.pipeline daily                       # Stage 3: daily incremental price updates
python -m data.pipeline consolidate                 # Stage 4: rebuild single-table parquet
python -m data.pipeline macro                       # Stage 5: CBN exchange rates + Brent oil
python -m data.pipeline news                        # Stage 6: NGX + BusinessDay articles

# Daily production sequence (every weekday after market close)
python -m data.pipeline daily && \
    python -m data.pipeline macro && \
    python -m data.pipeline news

# Operator controls
touch data/.killswitch                              # next request aborts cleanly
rm data/.killswitch                                 # re-enable
```

---

## Stage 1 — Discovery

Builds `data/master/tickers.csv` (~292 tickers, 35 sectors).

- **Runtime:** ~2 minutes (36 HTTP requests)
- **Cap:** 50 requests
- **Refresh cadence:** monthly — only if new IPOs or new sectors land on BroadStreet
- **When to run:** before Stage 2 the first time; periodically to refresh

---

## Stage 2 — Historical Backfill

For each ticker, fetches full OHLCV history paginated from `compDetail.php?...&p=qhp`.
Writes one parquet per ticker to `data/output/processed/prices/historical/`.

- **Cap:** 10,000 requests per run
- **Per-request delay:** 2-3s randomized (politeness)
- **Expected total for 292 tickers:** ~50-70 hours of HTTP time → split across 2-3 overnight runs
- **Resumable:** ✅ — if `<TICKER>.parquet` exists, ticker is skipped on next run
- **Cache-aware:** ✅ — already-downloaded HTML in `data/output/raw/broadstreet/tickers/<TICKER>/` is re-used; second runs are nearly free for tickers already touched

### How to run it across multiple nights

```bash
# Tonight, before bed:
python -m data.pipeline backfill
# When you wake up, it'll have stopped (cap hit). Pick up later:
python -m data.pipeline backfill
# Repeat for 2-3 nights total.
```

### Per-ticker speed expectations

| Listing age | Real pages | Time per ticker |
|---|---|---|
| Pre-2000 (FBN, NB, UAC, GTB) | ~150-200 | 25-35 min |
| 2000-2010 (DCE) | ~80-100 | 10-15 min |
| Post-2015 (MTN, BUA Foods) | ~30-60 | 5-10 min |

---

## Stage 3 — Daily Refresh

For each ticker that already has a parquet, fetches only new rows since
the parquet's most recent date and appends them. Designed for end-of-day
runs after NGX market close.

- **Runtime:** ~30-45 minutes for all 272 active tickers (depends on BroadStreet response time)
- **Cap:** 1,000 requests per run
- **Per-ticker cost:** ~2-3 HTTP requests (just 2026 data, ~50 rows max)
- **Skips:** tickers with no existing parquet (those go to `backfill`)
- **Auto-consolidate:** runs `consolidate()` at the end if anything updated
- **Cadence:** weekdays after market close (NGX trades 10:00-14:30 WAT)

```bash
python -m data.pipeline daily
```

---

## Stage 4 — Consolidate

Unions all per-ticker parquets in `data/output/processed/prices/historical/`
into a single long-format table at `historical_consolidated.parquet`.
Skips corrupt files with a warning instead of crashing.

- **Runtime:** ~5-10 seconds for 272 tickers
- **Auto-triggered:** after every `backfill` and `daily` run
- **Manual run:** `python -m data.pipeline consolidate`
- **Output:** `data/output/processed/prices/historical_consolidated.parquet`
  (currently ~1.1M rows across 272 tickers, 1993-2026)

---

## Stage 5 — Macro

Runs all configured macro data fetchers in sequence. If one fails, logs
the error and continues — partial macro data beats none.

- **Runtime:** ~20-30 seconds for all fetchers
- **Currently configured:**
  - **CBN exchange rates** — `/api/GetAllExchangeRates` JSON endpoint;
    14 currencies; full history 2001-present (~61K rows)
  - **Brent crude oil** — via `yfinance` (ticker `BZ=F`); daily close prices
- **Output:**
  - `data/output/processed/macro/cbn_exchange_rates.parquet`
  - `data/output/processed/macro/yahoo_macro.parquet`
- **Schema (both):** long-format `(date, indicator, value, source, unit)`
- **Dedup:** on `(date, indicator)` — safe to re-run any time
- **To add a new macro fetcher:** add a `_run_<name>()` function in
  `pipeline.py` and register it in `MACRO_FETCHERS`.

```bash
python -m data.pipeline macro
```

---

## Stage 6 — News

Runs all configured news fetchers in sequence. Same failure semantics as
Stage 5 — one fetcher's failure doesn't stop the others.

- **Runtime:** ~3-7 minutes for 20 articles per source (NGX is slow)
- **Default cap:** 20 articles per source per run (politeness)
- **Currently configured:**
  - **NGX Announcements** — primary source, company disclosures
  - **BusinessDay Nigeria** — major business daily
- **Pending:** Nairametrics, Proshare (still stubs)
- **Output schema:** `data/output/processed/news/articles/source=<id>/year=<YYYY>/articles.parquet`
- **Schema:** `(published_date, source, headline, article_text, url, mentioned_tickers)`
- **Skips:** paywalled URLs (e.g. BusinessDay `/pro/`), body-less articles
- **Override article cap:** `NEWS_MAX_ARTICLES=200 python -m data.pipeline news`
- **To add a new news fetcher:** implement a class inheriting `NewsFetcherBase`,
  then register a `_run_<name>()` function in `NEWS_FETCHERS` in `pipeline.py`.

```bash
python -m data.pipeline news
```

---

## Monitoring a running backfill

The manifest is written **after every ticker** (and on any clean exit). Check it from another terminal:

```bash
# Quick summary
python -c "import json; m=json.load(open('data/output/processed/prices/historical/_manifest.json')); print(f'{m[\"status\"]}: {m[\"tickers_complete\"]} complete, {m[\"tickers_partial\"]} partial, {m[\"tickers_failed\"]} failed, {m[\"requests_made\"]} requests')"

# How many parquets on disk
ls data/output/processed/prices/historical/*.parquet | wc -l

# Tail the log
tail -f data/logs/broadstreet.log
```

### What healthy looks like

- Steady stream of `GET ...` and `+N rows` log lines
- Per-page time: 2-4s (mostly sleep)
- Per-ticker time: a few seconds to ~30 minutes depending on history
- Manifest `requests_made` grows steadily, never plateaus

### What unhealthy looks like

| Symptom | Probable cause | Action |
|---|---|---|
| Repeated `429 Too Many Requests` | Site rate-limiting us | Stop, wait 30+ min, raise `REQUEST_DELAY_MIN`/`MAX` in `.env` |
| `SOFT BLOCK detected: Response contains login form` | Session expired or account locked | **Stop immediately.** Test login manually in browser. Do not auto-retry. |
| Same ticker stuck on the same page for >2 minutes | Network or server slowness | Kill (Ctrl+C), restart — cache means no rework lost |
| `tickers_failed` growing fast | Parser bug or HTML format change | Stop, check `data/output/raw/broadstreet/tickers/<bad-ticker>/` to inspect the HTML, file an issue |

---

## Killswitch — how to stop cleanly

From any other terminal:

```bash
touch data/.killswitch
```

The next outgoing HTTP request will detect this file and abort with `KillSwitchError`. The pipeline catches it, writes a final manifest with `status: "killswitch"`, and exits with code 2.

To re-enable:

```bash
rm data/.killswitch
python -m data.pipeline backfill    # picks up where it left off
```

Ctrl+C in the same terminal where the pipeline is running also works — the pipeline catches `KeyboardInterrupt`, writes the manifest with `status: "interrupted"`, and exits with code 130.

---

## Manifest status reference

The `status` field in `_manifest.json` tells you why the run ended:

| Status | Meaning | Action |
|---|---|---|
| `in_progress` | Run is currently active and writing | Wait, or check `requests_made` to estimate progress |
| `ok` | All tickers processed cleanly | Done. Move on. |
| `cap_hit` | Hit per-run cap of 10,000 requests | Expected for first night. Rerun to continue. |
| `interrupted` | You pressed Ctrl+C | Rerun to continue. |
| `killswitch` | Operator triggered killswitch file | `rm data/.killswitch` then rerun. |
| `soft_block` | Login page / captcha / 403 / empty body detected | **Investigate before retrying.** Could mean session expired or account is being blocked. |

---

## Recovery scenarios

### "I want to refetch a single ticker (it looks wrong)"

```bash
rm data/output/processed/prices/historical/GTB.parquet
rm -rf data/output/raw/broadstreet/tickers/GTB/    # force fresh HTML too
python -m data.pipeline backfill GTB
```

### "My backfill crashed mid-run"

Just rerun the same command. Cache + skip-existing-parquet means you don't lose work.

```bash
python -m data.pipeline backfill
```

### "A ticker is marked `partial` in the manifest"

The parquet exists but is missing the tail. Delete it and retry:

```bash
rm data/output/processed/prices/historical/<TICKER>.parquet
python -m data.pipeline backfill <TICKER>
```

### "I think I've been rate-limited or blocked"

1. Stop the pipeline immediately (`touch data/.killswitch` or Ctrl+C).
2. Try logging into BroadStreet in your browser. If you can't, **stop everything** and contact the account owner.
3. If you can still log in, wait 30+ minutes, then increase delay in `.env`:
   ```
   REQUEST_DELAY_MIN=4.0
   REQUEST_DELAY_MAX=6.0
   ```
4. Resume the backfill.

### "I lost connection to my laptop and the run died"

If you `touch data/.killswitch` before reconnecting, the next request will abort. Otherwise the manifest's last `in_progress` save tells you roughly where it stopped. Either way, rerun the same command — resumability handles it.

---

## Scheduling (production)

Currently the pipeline is run manually. The plan is to wire it into
GitHub Actions cron once it's stable. Until then, options:

### Option A — Linux/Mac cron

```bash
# Example cron — daily at 6 PM Lagos time (WAT = UTC+1, so 17:00 UTC)
0 17 * * 1-5 cd /path/to/ai-stock-broker-backend && \
    /path/to/venv/bin/python -m data.pipeline daily && \
    /path/to/venv/bin/python -m data.pipeline macro && \
    /path/to/venv/bin/python -m data.pipeline news \
    >> /path/to/logs/cron.log 2>&1
```

### Option B — GitHub Actions (recommended next)

Create `.github/workflows/daily.yml` that runs the same three commands
on a `schedule:` trigger. Requires:
- BroadStreet creds stored in GitHub Secrets
- Write permission for the workflow to git-push updated parquets back to `data-ingestion`
- One manual trigger to verify before relying on the cron

### Option C — Manual (current state)

A team member runs the three commands locally after market close, then
commits and pushes the new parquets. Works fine for the next 1-2 weeks
while we stabilize, but doesn't scale.

Add Slack/email webhook on failure when this matters more.

---

## What this pipeline does NOT do

- ❌ No headless browser — JS-rendered pages (like the exchange-rate page) are not fetched. See `KNOWN_ISSUES.md`.
- ❌ No proxy rotation, no User-Agent rotation. We rely on politeness + a real `From:` header.
- ❌ No multi-machine parallelism. Single sequential run only.
- ❌ No alerting. You watch the manifest yourself.

If you need any of these later, talk to the data-layer maintainer before bolting them on.
