# NGX AI Stock Broker — Backend

End-to-end documentation for the data engineering layer: what was built, why it
was built that way, where state lives, and what's coming next. Read this first
if you're joining the project or returning to it after time away.

For tightly-scoped reference docs, see also:

| Doc | Purpose |
|---|---|
| [data/HANDOFF.md](../data/HANDOFF.md) | Original ingestion-team → data-eng-team handoff. Pre-warehouse; some sections superseded by this README. |
| [data/OPERATIONS.md](../data/OPERATIONS.md) | Runbooks for `backfill` / `daily` / killswitch / recovery. |
| [data/SCHEMAS.md](../data/SCHEMAS.md) | Column contracts for every dataset. |
| [data/KNOWN_ISSUES.md](../data/KNOWN_ISSUES.md) | Source-data gotchas (BroadStreet quirks, the 2010-08-05 cluster, etc.). |
| [dbt/README.md](../dbt/README.md) | How to run the dbt quality project locally. |
| [app/RUNBOOKS.md](RUNBOOKS.md) | Operator playbook — what to do when a workflow step goes red, indexed by failing step / exit code. |

---

## 1. What this backend does

A scheduled pipeline scrapes daily Nigerian Exchange (NGX) equity prices from
BroadStreet, writes them to a **hybrid warehouse** (BigQuery + Postgres-on-Neon),
and a separate quality gate validates the data after every run. Downstream
consumers (the app/API, future ML models, analytics) read from the warehouse —
never from local files or GitHub.

The "hybrid" split is deliberate:

- **BigQuery** (`ngx_market_data.price`) — full history, partitioned by date,
  clustered by ticker. Analytics, ML training, ad-hoc queries. **1.12M rows.**
- **Postgres on Neon** (`price` table) — only the last
  `POSTGRES_PRICE_WINDOW_DAYS` (default **730**) days, upserted on each daily
  run. The serving store for the app/API. **~78k rows.**

Why both: BQ is excellent for big scans and SQL transformations but slow and
costly for the per-request reads an API does; Postgres is the inverse. Each
store does what it's best at, and the warehouse adapter writes to both
transparently.

---

## 2. Architecture

```
   ┌──────────────────┐
   │   BroadStreet    │   scrape (Mon-Fri 18:15 WAT)
   └────────┬─────────┘
            │ HTTP, politeness 2-3s/req
            ▼
   ┌──────────────────┐
   │ data/pipeline.py │   daily() / backfill() / consolidate()
   └────────┬─────────┘
            │ get_warehouse().write_price(df, replace=…)
            ▼
   ┌──────────────────────────────────┐
   │  app/services/warehouse.py       │
   │  HybridWarehouse                 │
   │  ├─ BigQueryAdapter (full hist)  │
   │  └─ PostgresAdapter (730d window)│
   └─────┬──────────────────────┬─────┘
         │                      │
         ▼                      ▼
   ┌─────────────┐      ┌──────────────────┐
   │  BigQuery   │      │ Postgres (Neon)  │
   │ ngx_market_ │      │  ngx_ai_platform │
   │  data.price │      │     .price       │
   │ (1.12M rows)│      │  (~78k rows)     │
   └──────┬──────┘      └────────┬─────────┘
          │                       │
          │   Lane A quality gate (after every daily)
          │   ┌────────────────────────────────────┐
          └──▶│  dbt build (schema + value tests)  │
              │  dbt source freshness (SLA)        │
              │  scripts/check_cross_store.py       │
              └────────────────────────────────────┘
                              │
                              ▼
                  (red CI run on any failure)
```

State lives in three places: BigQuery (source of truth), Postgres (serving),
and the BroadStreet credentials/`tickers.csv` (input). Nothing else is
authoritative — local parquet under `data/output/` is a regenerable cache, and
GitHub no longer stores price data at all (see §6).

---

## 3. Data flow end-to-end

### 3a. The scheduled `daily` run

What happens every weekday at 18:15 WAT (17:15 UTC) on a GitHub-hosted runner:

1. [.github/workflows/daily.yml](../.github/workflows/daily.yml) fires.
2. Workflow checks out the repo, sets up Python 3.11, installs
   [requirements.txt](../requirements.txt), and writes the GCP service-account
   JSON from `secrets.GCP_SA_KEY` to a temp file.
3. Runs `python -m data.pipeline daily`, which:
   - Calls `get_warehouse().get_last_dates()` to read each ticker's `MAX(date)`
     from BigQuery (the **watermark**). This is what makes `daily()`
     stateless — no local parquet required.
   - Logs in to BroadStreet, scrapes one or two pages per ticker since each
     ticker's last known date.
   - Computes `new_rows` per ticker, stamps the `ticker` column on it,
     accumulates across tickers, then calls
     `get_warehouse().write_price(df, replace=False)` — Postgres upserts via
     `ON CONFLICT (date, ticker)`, BigQuery appends.
   - Exits 5 on any warehouse-write failure (the scraped parquet is left
     intact on disk for re-run).
4. **Quality gate** (only if step 3 succeeded):
   - `dbt deps` → install dbt_utils
   - `dbt source freshness` → `MAX(ingested_at)` within SLA?
   - `dbt build` → run staging view + 9 tests
   - `python scripts/check_cross_store.py` → PG ↔ BQ drift within tolerance?
5. On any failure, the `data/logs/` and `dbt/target/` directories upload as a
   workflow artifact for downloadable inspection.

### 3b. Schema (canonical)

```
price (
  date         DATE          NOT NULL,    -- trading date (NGX calendar)
  ticker       TEXT          NOT NULL,    -- BroadStreet symbol
  pclose       DOUBLE/FLOAT64,             -- previous close
  high         DOUBLE/FLOAT64,
  low          DOUBLE/FLOAT64,
  close        DOUBLE/FLOAT64,
  volume       BIGINT/INT64,               -- shares traded (nullable; 0 = no-trade)
  change       DOUBLE/FLOAT64,             -- close − pclose (price, not %)
  ingested_at  TIMESTAMPTZ/TIMESTAMP,
  PRIMARY KEY (date, ticker)
)
```

Postgres uses `DOUBLE PRECISION` / `BIGINT`; BigQuery uses `FLOAT64` / `INT64`.
There is **no `open` column** — the source doesn't expose one.

### 3c. Key invariant

For any `(date, ticker)`:

```
change ≈ close − pclose
```

Holds in every row, including the corrupt 2010-08-05 cluster (see KNOWN_ISSUES
§11) — which is how we know that cluster is *source corruption*, not a parser
bug on our side.

---

## 4. Component map

What lives where and what each piece is responsible for.

### `app/services/warehouse.py` — the warehouse adapter

The abstraction every writer/reader goes through. Contains:

- `WarehouseAdapter` (ABC) — contract for `write_price`, `read_price`,
  `get_last_dates`, and the news/sentiment write methods (scaffolded; unused).
- `PostgresAdapter` — uses `psycopg2`. Accepts either discrete fields
  (`host`/`port`/...) or a DSN URI (auto-detected when `POSTGRES_HOST` starts
  with `postgresql://`). `sslmode` driven by `POSTGRES_SSLMODE`. Enforces the
  recent-window filter on writes; full window history lives in BQ only.
- `BigQueryAdapter` — uses `google-cloud-bigquery`. Loads service-account
  creds from `GCP_CREDENTIALS_PATH` (falls back to ADC). Explicit
  `_PRICE_SCHEMA` so types never drift.
- `HybridWarehouse` — composes the two; `write_price` hits both,
  `get_last_dates` delegates to BigQuery (authoritative), `read_price` reads
  from Postgres (serving).
- `get_warehouse()` — factory selecting one of `hybrid`/`bigquery`/`postgres`
  from `DATA_WAREHOUSE_MODE`.

### `data/pipeline.py` — the orchestrator

CLI entry points (`python -m data.pipeline <cmd>`):

| Command | What it does |
|---|---|
| `discover` | Scrape master ticker list to [data/master/tickers.csv](../data/master/tickers.csv) |
| `backfill [TICKERS]` | Full historical scrape; auto-consolidates; pushes to warehouse with `replace=True` |
| `daily` | Incremental: watermark from BQ → scrape new closes only → append to warehouse |
| `consolidate` | Build the unified long-format dataframe in memory; only writes the file when `ARCHIVE_GITHUB=true` |
| `macro` | Stage-5 macro fetchers (currently CBN + Yahoo brent stubs; not in routine schedule) |

Exit-code map:

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Generic input error (missing tickers.csv etc.) |
| 2 | Killswitch tripped (`data/.killswitch` present) |
| 3 | Soft block detected (login form / captcha) |
| 4 | Per-run request cap hit |
| 5 | Warehouse write failed (scrape OK; parquet preserved) |
| 7 | Cross-store consistency drift (from `scripts/check_cross_store.py`) |
| 130 | KeyboardInterrupt |

### `data/fetchers/` — the scrapers

- [data/fetchers/broadstreet.py](../data/fetchers/broadstreet.py) — login,
  sector/ticker discovery, historical OHLCV. Politeness 2–3s/req,
  killswitch-aware, soft-block detection, request-cap'd.
- [data/fetchers/cbn.py](../data/fetchers/cbn.py) — exchange-rate fetcher stub.
- [data/fetchers/yfinance.py](../data/fetchers/yfinance.py) — Brent oil stub.
- [data/fetchers/news/](../data/fetchers/news/) — scaffolded news fetchers
  (BusinessDay, NGX announcements, Nairametrics, Proshare). Not yet populating
  the warehouse.

### `dbt/` — the data quality gate (Lane A)

Versioned, declarative tests run via dbt-bigquery:

- [dbt/dbt_project.yml](../dbt/dbt_project.yml) — project config.
- [dbt/profiles.yml](../dbt/profiles.yml) — connection config; pure env-var
  references, no creds in the file.
- [dbt/packages.yml](../dbt/packages.yml) — pin on `dbt_utils 1.3.0`.
- [dbt/models/staging/stg_price.sql](../dbt/models/staging/stg_price.sql) — a
  thin pass-through view. **Everything downstream reads from here**, not from
  the raw source.
- [dbt/models/staging/sources.yml](../dbt/models/staging/sources.yml) —
  declares the raw `price` source + a `freshness` block (warn 30h / error 80h
  on `ingested_at`).
- [dbt/models/staging/schema.yml](../dbt/models/staging/schema.yml) — 9 tests.
  Hard-failure tests for structural invariants (uniqueness, not-null on key
  columns, date sanity); warn-level tests for physical-sanity assertions
  (high≥low, high≥close, close>0, volume≥0) scoped to `volume > 0` rows —
  warn because of immutable historical corruption documented in
  KNOWN_ISSUES.md §11.

### `scripts/`

- [scripts/migrate_to_warehouse.py](../scripts/migrate_to_warehouse.py) — the
  one-time historical loader. Reads `historical_consolidated.parquet`, pushes
  through `get_warehouse().write_price(replace=True)`, verifies row counts
  per store with windowing accounted for. Idempotent.
- [scripts/check_cross_store.py](../scripts/check_cross_store.py) — runs
  after every daily. Compares PG `COUNT(*)`, `MAX(date)` against the same in
  BQ with the recent-window filter. Tolerance: 0.1% rows, 1-day max_date.
  Exit 7 on drift.

### `app/db/`

- [app/db/schema.sql](db/schema.sql) — canonical Postgres DDL. Applied
  manually once per environment (local + Neon).
- [app/db/bigquery_schema.sql](db/bigquery_schema.sql) — canonical BQ DDL.
  Dataset and partitioned/clustered `price` table; applied once per project.

### `app/{ml,nlp,explain,routers,utils}/` — placeholders

Currently empty (only `.gitkeep` files). Reserved for the model serving
layer once features land.

### `.github/workflows/daily.yml`

The schedule + dispatch + pipeline + quality gate combined into one job.
Runs on `ubuntu-latest`, Python 3.11, `timeout-minutes: 90`.

---

## 5. Environment & secrets

### Local `.env` (not committed)

Required for the pipeline to run locally or anywhere outside CI:

| Var | Example | Purpose |
|---|---|---|
| `BROADSTREET_USERNAME` / `…_PASSWORD` | … | Scrape auth |
| `BASE_URL` / `LOGIN_ENDPOINT` | … | BroadStreet endpoints |
| `GCP_PROJECT_ID` | `stock-market-pipeline-496521` | BigQuery project |
| `GCP_CREDENTIALS_PATH` | `C:/.../sa.json` (forward-slashes; unquoted!) | Service-account JSON path |
| `BIGQUERY_MARKET_DATASET` | `ngx_market_data` | Where `price` lives |
| `BIGQUERY_RAW_DATASET` | `ngx_raw_data` | Reserved (future news/raw tables) |
| `POSTGRES_HOST` | full Neon DSN URI | DSN auto-detected; ignores discrete fields below |
| `POSTGRES_SSLMODE` | `require` | Neon mandates TLS |
| `POSTGRES_PRICE_WINDOW_DAYS` | `730` | Recent window kept in PG |
| `DATA_WAREHOUSE_MODE` | `hybrid` | `hybrid` / `bigquery` / `postgres` |
| `ARCHIVE_GITHUB` | `false` | If `true`, also writes `historical_consolidated.parquet` |

**Watch out:** values containing `\` in double-quoted form get processed as
escape sequences by python-dotenv. Use forward slashes and don't quote paths.

### GitHub Actions

Same keys, but split between **Secrets** (sensitive) and **Variables**
(non-sensitive). Identical names to the local `.env` keys for the most part;
the GCP key is stored as a single `GCP_SA_KEY` secret containing the entire
JSON and written to a temp file in the workflow.

See §6.4 of the build history (and the live values under
**Settings → Secrets and variables → Actions** in the repo).

---

## 6. How to operate the system

### Daily run (manual)

```bash
# Local
source venv/Scripts/activate
python -m data.pipeline daily

# CI
# Repo → Actions → "Daily price refresh" → Run workflow → pick branch
```

### Backfill a single ticker

```bash
python -m data.pipeline backfill MTN
```

`backfill` calls `consolidate()` and pushes `replace=True` (truncate + reload).
Note: this truncates the *whole* `price` table in both stores, then reloads
from every per-ticker parquet on disk. Use knowingly.

### Re-seed Neon's recent window (e.g. after schema change)

Temporarily set `DATA_WAREHOUSE_MODE=postgres` in `.env`, then:

```bash
python -m scripts.migrate_to_warehouse --yes
```

Postgres-only run; BigQuery untouched. Restore `DATA_WAREHOUSE_MODE=hybrid`
afterward.

### Run the quality gate locally

```bash
export GCP_PROJECT_ID="$(grep -E '^GCP_PROJECT_ID=' .env | cut -d= -f2-)"
export GCP_CREDENTIALS_PATH="$(grep -E '^GCP_CREDENTIALS_PATH=' .env | cut -d= -f2-)"
export BIGQUERY_MARKET_DATASET=ngx_market_data

dbt deps             --project-dir dbt --profiles-dir dbt
dbt source freshness --project-dir dbt --profiles-dir dbt
dbt build            --project-dir dbt --profiles-dir dbt
python scripts/check_cross_store.py
```

Expected: `PASS=6 WARN=4 ERROR=0 TOTAL=10` on `dbt build`, `OK` on the
cross-store check.

### Killswitch

If a scrape misbehaves and you need it stopped *now* without killing the
process:

```bash
touch data/.killswitch       # next request aborts cleanly
rm data/.killswitch          # re-enable
```

---

## 7. Quality signals — what each red CI step means

When `daily.yml` goes red, the failing step name tells you which fix path to
take. Each surface error code is distinct. **For step-by-step incident
response, see [app/RUNBOOKS.md](RUNBOOKS.md)** — the table below is the
quick-reference; the runbook is the playbook.

| Failing step | Exit / kind | What broke | Where to look |
|---|---|---|---|
| Run daily pipeline | exit 1 | Missing tickers.csv etc. | Re-run `discover` |
| Run daily pipeline | exit 2 | Killswitch present | `rm data/.killswitch` |
| Run daily pipeline | exit 3 | Soft-block / login form | Investigate the BroadStreet account before re-running |
| Run daily pipeline | exit 4 | Request-cap reached | Re-run; ongoing pattern = raise cap or split runs |
| Run daily pipeline | exit 5 | Warehouse unreachable | Neon / BigQuery / network; scraped parquet is preserved |
| dbt source freshness | non-zero | `MAX(ingested_at)` > 80h | The daily silently stopped landing — root-cause from logs |
| dbt build | non-zero | A hard-severity test failed | Inspect `dbt/target/run_results.json` from the artifact |
| Cross-store check | exit 7 | PG ↔ BQ drift | A hybrid-write failed half-way; re-seed PG via 6.3 procedure |

Warn-level dbt tests (the four documented in KNOWN_ISSUES §11) appear as
`WARN=4` in the run log but **do not** fail the workflow.

---

## 8. Where we are in the broader plan

### Done

- **Project 1 — Warehouse migration.** Historical data off GitHub
  (1,125,466 rows → BigQuery; ~78k recent-window → Neon Postgres). Pipeline
  writes straight to the warehouse, both `daily` and `backfill`. GitHub no
  longer stores price data (275 parquets untracked via `git rm --cached`,
  `data/output/` gitignored). Scheduled refresh runs daily from CI.
- **Project 2 — Lane A: Reliability & quality.** dbt project with a staging
  view, 9 tests, freshness SLA, and a cross-store consistency check, all
  running on every scheduled and manual run from the default branch.

### Current

Lane A is freshly landed. The first nightly run of the full
**pipeline + quality gate** is the proving point. After that:

### Next (choices, not a fixed order)

| Lane | Scope | When |
|---|---|---|
| **B — Observability & ops** | Failure notifications to Slack/email; a `pipeline_runs` table in BQ recording start/end/rows/errors per run; on-call runbook | Soonest if you want alerts instead of "check the Actions tab" |
| **C — Coverage** | Add the missing datasets: **corporate actions** (critical for any return-based ML; the 2010-08-05 cluster likely lives in this domain), macro (CBN exchange rates, oil), NGX index, fundamentals, news/sentiment. Each new dataset gets its own `stg_*.sql` + `schema.yml` and inherits the same gate. | Whenever ML needs more inputs |
| **D — Curation / transforms** | dbt models for derived data: `fct_price_adjusted` (corporate-actions-adjusted OHLCV — depends on Lane C corp actions), `fct_returns`, `feat_technical`, `feat_macro`, `training_dataset`. Read by ML jobs. | When inputs (Lane C) and reliability (Lane A) are in place |

### Explicitly out of scope (for now)

- Intraday / real-time data — pipeline is end-of-day by design.
- Order book / L2-L3 microstructure — not available from BroadStreet.
- Streaming infra (Airflow / Prefect / Dagster) — overkill for one daily job.
- A feature store (Feast / Tecton) — only worth it when multiple models share
  features in production.

---

## 9. The non-obvious lessons that have come up

A short list of things future-you (or a teammate) will appreciate knowing
without having to re-discover them:

- **Forward-slashes in `.env` Windows paths.** Double-quoted backslash paths
  get `\a` → `\x07` (bell) — silently breaks `GCP_CREDENTIALS_PATH`. Unquoted
  forward-slash paths are safe.
- **`POSTGRES_HOST` accepts a full URI.** `warehouse.py` auto-detects a
  `postgresql://…` scheme and connects via DSN. Pasting Neon's connection
  string straight in just works.
- **`if __name__ == "__main__"` indentation matters.** Earlier the migration
  script had it indented inside `main()` — the module ran silently and did
  nothing. Always confirm it sits at column 0.
- **dbt's source location.** `--profiles-dir dbt` is not enough; you also
  need `--project-dir dbt`, otherwise dbt looks for `dbt_project.yml` in the
  current working directory.
- **dbt_utils `expression_is_true` uses dbt-native `config: where:`**, not its
  own `condition:` arg (older docs lie). Severity goes under `config:` too.
- **The 2010-08-05 cluster.** Roughly 6,500 historical rows are corrupt at
  the source (negative `pclose`, `close=0` on volume-positive days). Tests
  are warn-level on these constraints until corp-actions cleanup. Details in
  KNOWN_ISSUES.md §11.
- **GitHub Actions scheduled triggers** fire only from the **default branch**.
  `workflow_dispatch` works from any branch.
- **GH-runner IP risk on BroadStreet.** Cold cloud IPs trigger more backoffs
  than your home connection. The 30-min timeout in v1 of the workflow
  exposed this; bumped to 90 min and stable. If soft-blocks become a
  pattern, switch to a self-hosted runner — same workflow, only `runs-on:`
  changes.

---

## 10. Glossary

- **Watermark** — Per-ticker `MAX(date)` from the warehouse, used by `daily`
  to decide what new dates to scrape. Made stateless in 6.1 of the migration.
- **Window filter** — The Postgres-only constraint that only the last
  `POSTGRES_PRICE_WINDOW_DAYS` (730) days of each ticker are persisted; older
  history stays in BigQuery only.
- **Hybrid mode** — Writing to both BigQuery and Postgres in the same call.
  Other modes (`bigquery`, `postgres`) write to one store only — used
  occasionally for one-off operations like a Postgres-only re-seed.
- **Soft block** — BroadStreet's response that looks successful but is
  actually a login form / captcha. Detected and exit-3'd before any
  downstream damage.
- **Warn-level test** — A dbt test that logs a row count of violators but
  doesn't fail the build. Used for known issues we don't fix in v1.
