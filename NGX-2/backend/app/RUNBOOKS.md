# Runbooks — NGX Backend Pipeline

When the **Daily price refresh** workflow goes red, find the failing step in
the index below and jump to its section. Each entry is structured the same:

> **Symptom** → what you see.
> **Immediate response** → what to do right now (≤ 2 minutes).
> **Investigation** → where to look for the why.
> **Permanent fix / escalate** → when to fix at the source or call for help.

The whole point of this doc is **one click from a red run to the right fix**.
Update it whenever you handle a new failure mode — paste-quality wins over
prose-quality.

---

## Index

| Step in `daily.yml` | Exit / kind | Section |
|---|---|---|
| Run daily pipeline | exit **1** (generic) | [§1](#1-pipeline-exit-1--generic-input-error) |
| Run daily pipeline | exit **2** (killswitch) | [§2](#2-pipeline-exit-2--killswitch-tripped) |
| Run daily pipeline | exit **3** (soft block) | [§3](#3-pipeline-exit-3--soft-block-detected) |
| Run daily pipeline | exit **4** (request cap) | [§4](#4-pipeline-exit-4--request-cap-hit) |
| Run daily pipeline | exit **5** (warehouse) | [§5](#5-pipeline-exit-5--warehouse-write-failed) |
| Run daily pipeline | exit **130** (interrupt) | [§6](#6-pipeline-exit-130--interrupted) |
| dbt source freshness | error_after breach | [§7](#7-dbt-source-freshness-error_after-breach) |
| dbt build (data-quality tests) | a hard-severity test errored | [§8](#8-dbt-build-hard-test-failure) |
| dbt build (warnings) | `WARN=N` in green run | [§9](#9-dbt-build-warnings-informational) |
| Cross-store consistency check | exit **7** (drift) | [§10](#10-cross-store-drift-exit-7) |

> **Don't see your symptom?** [§11 — Escalation](#11-escalation--when-nothing-here-fixes-it).

---

## General first response (≤ 30 seconds, every incident)

1. **GitHub → Actions → the failed run.** Note which step is red.
2. **Bottom of the run page → Artifacts → `pipeline-logs`.** Download it.
   Contains `data/logs/broadstreet.log` and `dbt/target/` for forensics.
3. **Open the failing step's log** — the exception, the exit code, and the
   last meaningful line are usually right next to each other.
4. **Cross-reference `pipeline_runs`** in BigQuery for context:
   ```sql
   SELECT started_at, status, exit_code, rows_written,
          tickers_updated, tickers_failed, error_message, git_commit
   FROM `stock-market-pipeline-496521.ngx_raw_data.pipeline_runs`
   WHERE pipeline_name = 'daily'
   ORDER BY started_at DESC
   LIMIT 10;
   ```
   This tells you whether this is a one-off, a regression at a specific
   commit, or a degrading trend.
5. Find the section below matching the failing step.

---

## 1. Pipeline exit 1 — generic input error

**Symptom**
- Step "Run daily pipeline" fails fast (under a minute).
- Log shows e.g. `data/master/tickers.csv not found` or `historical/ not found`.

**Immediate response**
- Confirm whether the missing input is a code/asset that should exist in the
  repo (e.g. `tickers.csv` is committed) — if yes, the CI checkout may have
  been incomplete; re-run the workflow once before deeper investigation.

**Investigation**
- `git ls-files data/master/tickers.csv` — confirm it's tracked.
- If `historical/` is missing, that's expected on CI (we removed parquet
  tracking in step 5 of the migration). The `daily` flow doesn't need it
  after 6.1, so this shouldn't surface — if it does, the watermark code path
  isn't being hit; check that you're on a default-branch commit that
  includes `from app.services.warehouse import get_warehouse` inside
  `daily()`.

**Permanent fix**
- If `tickers.csv` is genuinely missing, run `python -m data.pipeline discover`
  locally and commit the regenerated file.

---

## 2. Pipeline exit 2 — killswitch tripped

**Symptom**
- Log line `KILLSWITCH: data/.killswitch present, aborting`.
- `pipeline_runs.status = 'killswitch'`.

**Immediate response**
- This only happens if `data/.killswitch` is in the workspace. On a fresh
  GitHub-hosted runner it shouldn't be — if it is, the file got committed
  somewhere it shouldn't have been.

**Investigation**
- `git ls-files data/.killswitch` — should return nothing. If it returns the
  file, someone committed it.

**Permanent fix**
- `git rm data/.killswitch && git commit && git push`.
- Confirm `data/.killswitch` is in [.gitignore](../.gitignore) (it is).
- Local-only operators: `rm data/.killswitch` then re-run.

---

## 3. Pipeline exit 3 — soft block detected

**Symptom**
- Log line `SOFT BLOCK detected: Response contains login form` (or captcha /
  403 / 451).
- `pipeline_runs.status = 'soft_block'`.

**Immediate response**
- **Do NOT auto-retry.** Soft blocks indicate the account is being
  challenged; hammering the endpoint risks a hard ban.
- Verify the BroadStreet account is still healthy: open
  https://broadstreetlagos.com in a browser and log in with the credentials
  from `BROADSTREET_USERNAME` / `BROADSTREET_PASSWORD`. If login fails,
  **STOP** and contact the account owner — see KNOWN_ISSUES §10.

**Investigation**
- Download `pipeline-logs` artifact → check `data/logs/broadstreet.log` for
  the request/response that triggered detection.
- Check recent run history:
  ```sql
  SELECT started_at, status, host
  FROM `stock-market-pipeline-496521.ngx_raw_data.pipeline_runs`
  WHERE pipeline_name = 'daily' AND status = 'soft_block'
  ORDER BY started_at DESC LIMIT 20;
  ```
  Multiple soft_blocks in a row from `host='github-actions'` and zero from
  `host='local'` = cold-IP issue, not account issue.

**Permanent fix**
- **One-off:** wait 30+ minutes, re-run.
- **Persistent (multiple consecutive runs):** the GitHub-runner IP is the
  problem. Two options:
  1. Switch the workflow to a **self-hosted runner** on a machine with a
     friendlier IP. Only the `runs-on:` label in [daily.yml](../.github/workflows/daily.yml) changes.
  2. Move the schedule off CI entirely — back to local Windows Task
     Scheduler on your machine where the account hasn't been challenged.
- **Long-term:** acquire our own BroadStreet account (KNOWN_ISSUES §10).

---

## 4. Pipeline exit 4 — request cap hit

**Symptom**
- Log line `REQUEST CAP: reached N/1000`.
- `pipeline_runs.status = 'cap_hit'`.

**Immediate response**
- A `daily` shouldn't exceed the cap under normal conditions (272 tickers ×
  1–2 pages each ≈ 300–500 requests, cap is 1000). If it did, something is
  retrying a lot.

**Investigation**
- Inspect `broadstreet.log` for repeated retries / backoffs on a specific
  ticker. The fetcher's tenacity retries can multiply request count fast
  under transient errors.
- Cross-check `pipeline_runs.tickers_failed` — if high, those failures
  consumed cap.

**Permanent fix**
- One-off: re-run; cache + watermark mean you'll pick up where you stopped.
- Pattern: raise the cap in `data/pipeline.py` `daily()` (`fetcher =
  BroadStreetFetcher(max_requests=1000)`), or fix whatever's causing
  retries. Don't blindly raise the cap if soft-blocks are appearing — that
  compounds the problem (cross-ref §3).

---

## 5. Pipeline exit 5 — warehouse write failed

**Symptom**
- Log line `Warehouse write FAILED: <exception>`.
- `pipeline_runs.status = 'warehouse_failed'`.
- Then: `Scraped parquet is intact on disk — re-run to retry.`

**Immediate response**
- Pipeline already preserved the scrape; re-running recovers fully.
  **No data is lost.**
- Re-trigger the workflow once.

**Investigation**
- The failing call is usually one of (in the log):
  - Neon connect error → check `POSTGRES_HOST` secret, confirm Neon project
    isn't paused/cold (rare; check Neon console).
  - BigQuery auth error → check the `GCP_SA_KEY` secret hasn't been rotated
    or revoked.
  - `Not found: Dataset/Table` → schema diverged from
    [app/db/bigquery_schema.sql](db/bigquery_schema.sql); re-apply the DDL.
- Check whether the same exit 5 happened on the previous run too:
  ```sql
  SELECT started_at, error_message
  FROM `stock-market-pipeline-496521.ngx_raw_data.pipeline_runs`
  WHERE pipeline_name = 'daily' AND status = 'warehouse_failed'
  ORDER BY started_at DESC LIMIT 5;
  ```

**Permanent fix**
- Depends on which side failed; see Investigation.
- If Neon was paused (free-tier cold start), no fix needed — the next run
  succeeds.
- If GCP creds rotated, regenerate the JSON key, update the `GCP_SA_KEY`
  secret.

---

## 6. Pipeline exit 130 — interrupted

**Symptom**
- `pipeline_runs.status = 'interrupted'`, `exit_code = 130`.
- Happens when someone Ctrl-C's a local run, or when CI cancels the job
  (e.g. someone clicked "Cancel" or another concurrent run is queued —
  unlikely with our `concurrency: cancel-in-progress: false`).

**Immediate response**
- If on CI: re-run. The pipeline is restart-safe; the warehouse only
  contains rows from completed loads.

**Investigation**
- Confirm nobody intentionally cancelled. If yes, the row will still be in
  `pipeline_runs` with `status='interrupted'` — useful as audit trail.

**Permanent fix** — none required.

---

## 7. dbt source freshness — `error_after` breach

**Symptom**
- Step "dbt source freshness" fails with `ERROR: ngx_market_data.price is
  over 80 hours old`.
- The `Run daily pipeline` step before it succeeded — but no fresh rows
  landed.

**Immediate response**
- The pipeline completed but didn't add new rows on recent runs. Check the
  most recent run:
  ```sql
  SELECT MAX(ingested_at), COUNT(*)
  FROM `stock-market-pipeline-496521.ngx_market_data.price`;
  ```
  Compare `MAX(ingested_at)` to "now" — confirm it's truly > 80 hours.

**Investigation**
- Cross-check `pipeline_runs` for recent days:
  ```sql
  SELECT started_at, status, rows_written, tickers_updated
  FROM `stock-market-pipeline-496521.ngx_raw_data.pipeline_runs`
  WHERE pipeline_name = 'daily'
  ORDER BY started_at DESC LIMIT 7;
  ```
  - All `success` with `rows_written = 0`: NGX has had no real trading
    activity (long weekend / multi-day holiday). The 80h threshold is
    designed to tolerate this; if it's tripping, extend the threshold in
    [dbt/models/staging/sources.yml](../dbt/models/staging/sources.yml).
  - Mix of `failed`/`warehouse_failed`: real upstream issue — go to that
    exit-code section.
- Confirm BroadStreet itself is publishing prices (open the site, check a
  recent date for any ticker).

**Permanent fix**
- If holidays are the cause and they're a regular thing, raise the freshness
  thresholds (e.g. `error_after: { count: 120, period: hour }`).
- If upstream stopped publishing, escalate to KNOWN_ISSUES owner.

---

## 8. dbt build — hard test failure

**Symptom**
- Step "dbt build (data-quality tests)" fails with
  `Done. PASS=N WARN=N ERROR>=1`.
- One or more `Failure in test ...` lines name the failing test.

**Immediate response**
- These tests **never** fail on stable data (the historical-corruption
  tests are at warn-level — see §9). A new error means **today's load
  introduced a fresh violation**, which is the exact signal you want.

**Investigation**
- Download the `pipeline-logs` artifact → `dbt/target/run_results.json` has
  every test's compiled SQL and bad-row count.
- Reproduce locally with `--store-failures` to materialize bad rows in
  BigQuery for inspection:
  ```bash
  dbt build --project-dir dbt --profiles-dir dbt --store-failures
  ```
  Then query `<dataset>_dbt_test__audit.<test_name>` for the offending rows.
- Likely candidates:
  - `unique_combination_of_columns(date, ticker)` → duplicate rows. NOTE:
    `daily` now auto-dedupes via a CTAS after every append
    (`BigQueryAdapter._dedupe_price`), so this should no longer fire from a
    normal double-run. If it does, the dedupe step failed or rows were loaded
    outside the pipeline (ad-hoc load). Use the manual dedupe below.
  - `not_null` → BroadStreet parser broke for a specific ticker; check
    `broadstreet.log` for parse errors.
  - `date <= current_date()` → time-zone/date-cast issue in the loader.

**Permanent fix**
- Most fresh failures are parser regressions; fix at
  [data/fetchers/broadstreet.py](../data/fetchers/broadstreet.py) and
  re-load the affected date in BigQuery.
- For appended duplicates, dedupe in BQ. **Keep it UNPARTITIONED** — adding
  `PARTITION BY` triggers the sandbox's per-partition 60-day expiration and
  silently deletes all history older than 60 days (this caused a real
  incident — see KNOWN_ISSUES §11 / the price-table recovery):
  ```sql
  CREATE OR REPLACE TABLE `stock-market-pipeline-496521.ngx_market_data.price` AS
  SELECT * EXCEPT(rn) FROM (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY date, ticker ORDER BY ingested_at DESC
    ) AS rn
    FROM `stock-market-pipeline-496521.ngx_market_data.price`
  ) WHERE rn = 1;
  ```
  (`PARTITION BY date,ticker` inside the window function is fine — that's the
  dedupe key. The dangerous part is a table-level `PARTITION BY date` clause.)

---

## 9. dbt build — warnings (informational)

**Symptom**
- Step "dbt build (data-quality tests)" is **green** but log shows
  `Done. PASS=6 WARN=4 ERROR=0 TOTAL=10`.

**Immediate response**
- No action required — these are the historical-corruption warnings
  documented in [data/KNOWN_ISSUES.md §11](../data/KNOWN_ISSUES.md#11-corrupt-historical-rows--2010-08-05-cluster--delisted-ut-tickers).

**Investigation** (only if WARN count climbs over time)
- Compare WARN counts run-over-run by saving the dbt log (already uploaded
  on failure; success runs aren't archived). If you start seeing
  `WARN > 4` on recent successful runs, *new* rows are violating physical
  sanity — treat as §8.

**Permanent fix**
- The proper fix is BigQuery cleanup of the 2010-08-05 cluster + parser
  guard against negative pclose / close. Paired with corporate-actions
  ingestion (Lane C). Don't downgrade these warns away — they're the canary
  for fresh violations against the same constraints.

---

## 10. Cross-store drift — exit 7

**Symptom**
- Step "Cross-store consistency check" fails with one of:
  - `Row drift: PG=X BQ=Y diff=Z (Z% > 0.10%)`
  - `max_date drift: PG=YYYY-MM-DD BQ=YYYY-MM-DD (Nd > 1d)`
  - `NULL max_date — PG=... BQ=...`

**Immediate response**
- The hybrid-write succeeded in one store and failed in the other (or
  half-failed). The data isn't lost — both stores are independently
  consistent with their writes; they just disagree on what happened today.

**Investigation**
- Query both stores directly to see the gap:
  ```sql
  -- BQ
  SELECT COUNT(*), MAX(date) FROM `stock-market-pipeline-496521.ngx_market_data.price`
  WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 730 DAY);
  ```
  ```sql
  -- Postgres (pgAdmin / psql / Neon console)
  SELECT COUNT(*), MAX(date) FROM price;
  ```
- Identify which store is behind:
  - BQ behind PG: today's BQ load failed mid-way; re-run `daily`.
  - PG behind BQ: today's PG upsert failed; same fix — re-run `daily`.
  - Both same `MAX(date)` but row counts diverge by more than 0.1%: real
    schema/window drift; investigate the window filter
    (`POSTGRES_PRICE_WINDOW_DAYS`) — did someone change it without
    re-seeding?

**Permanent fix**
- One-off: re-run `daily` (the warehouse writes are idempotent for `daily`
  except for BQ append — see §8 dedupe SQL if duplicates appear after
  re-run).
- Persistent drift: re-seed PG from BQ via the postgres-only path:
  ```bash
  # in .env: temporarily DATA_WAREHOUSE_MODE=postgres
  python -m scripts.migrate_to_warehouse --yes
  # restore .env: DATA_WAREHOUSE_MODE=hybrid
  ```
  Same 6.3 procedure documented in [app/README.md §6](README.md#6-how-to-operate-the-system).

---

## 11. Escalation — when nothing here fixes it

- If two consecutive runs fail with the **same** exit code and the symptoms
  don't match any section above, treat as a regression in the most recent
  commit. Bisect via:
  ```sql
  SELECT git_commit, status, COUNT(*)
  FROM `stock-market-pipeline-496521.ngx_raw_data.pipeline_runs`
  WHERE pipeline_name = 'daily' AND started_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
  GROUP BY git_commit, status
  ORDER BY MIN(started_at);
  ```
  The first `git_commit` with `status != 'success'` is likely the
  introducer.

- If the failure is BroadStreet-side (soft-block, layout change), update
  [data/KNOWN_ISSUES.md](../data/KNOWN_ISSUES.md) with the new pattern after
  you fix it, and add a new section here.

- For credentials/account issues that you can't resolve, contact the
  BroadStreet account owner per KNOWN_ISSUES §10.

- For schema or DDL issues, the source of truth is
  [app/db/schema.sql](db/schema.sql) and
  [app/db/bigquery_schema.sql](db/bigquery_schema.sql). Any divergence in
  the live tables from those files should be reconciled (apply the SQL).

---

## When you handle a new failure mode

Add a new section before §11 with the same shape. Keep entries < ~40 lines —
operator scan time matters more than thoroughness during an incident.
