# Data Layer — NGX AI Stock Advisor

This folder produces clean, typed market data for the ML and Data Engineering teams.

## Quick start (consumers)

```python
import pandas as pd

# Master ticker list
tickers = pd.read_csv("data/master/tickers.csv")

# Full price history for one stock
gtb = pd.read_parquet("data/output/processed/prices/historical/GTB.parquet")

# Today's snapshot across all tickers
today = pd.read_parquet("data/output/processed/prices/snapshots/2026-05-14.parquet")
```

See [SCHEMAS.md](./SCHEMAS.md) for column definitions and types.

## Docs map

- **[SCHEMAS.md](./SCHEMAS.md)** — column contracts for every dataset produced
- **[OPERATIONS.md](./OPERATIONS.md)** — how to run, monitor, killswitch, recover
- **[KNOWN_ISSUES.md](./KNOWN_ISSUES.md)** — gotchas, ticker-code mismatches, defunct companies, JS-rendered pages, etc.

## Quick start (this team — running the pipeline)

```bash
# 1. Activate venv
source ../venv/Scripts/activate
pip install -r ../requirements.txt

# 2. Set credentials in .env (see .env.example)

# 3. Run pipeline stages
python -m data.pipeline discover   # build master/tickers.csv
python -m data.pipeline backfill   # one-time historical pull (~1-2 hrs)
python -m data.pipeline daily      # incremental refresh (~5 min)
```

## Data sources

| Source       | What                              | Status   |
|--------------|-----------------------------------|----------|
| BroadStreet  | NGX equities, OHLCV, fundamentals | working  |
| CBN          | Macro / FX                        | planned  |
| yfinance     | ADRs / supplementary              | planned  |

## Structure

- `fetchers/` — source-specific HTTP + parsing
- `validators/` — schema + sanity checks
- `master/` — reference data (tickers)
- `output/raw/` — exact HTML as scraped (audit / replay)
- `output/processed/` — cleaned parquet for downstream consumption
- `logs/` — runtime logs

## Operational notes

- The pipeline is **rate-limited and resumable**. Safe to ctrl-C and restart.
- Re-running `daily` is idempotent — only appends missing dates.
- If you see auth failures, regenerate the BroadStreet session by re-running `discover`.
