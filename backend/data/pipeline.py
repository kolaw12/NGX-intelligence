"""
Pipeline orchestrator.

Usage:
    python -m data.pipeline discover                  # Stage 1: master/tickers.csv
    python -m data.pipeline backfill                  # Stage 2: full historical OHLCV
    python -m data.pipeline backfill GTB DCE MTN      # Stage 2 (pilot subset)
    python -m data.pipeline daily                     # Stage 3: incremental price updates
    python -m data.pipeline consolidate               # Stage 4: union all parquets
    python -m data.pipeline macro                     # Stage 5: macro data fetchers (CBN, oil, etc.)
    python -m data.pipeline news                      # Stage 6: news fetchers (BusinessDay, NGX, etc.)
    python -m data.pipeline sentiment-summary         # Stage 6b: build and load daily sentiment summary
    python -m data.pipeline corporate-actions         # Stage 7: raw corp actions (dividends + bonuses)
    python -m data.pipeline corporate-actions GTB UBA # Stage 7 (pilot subset)

Operator controls:
    touch data/.killswitch                            # next request aborts cleanly
    rm data/.killswitch                               # re-enable
"""
import ast
import json
import os
import re
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import pandas as pd
# pyrefly: ignore [missing-import]
from loguru import logger

# Import _utcnow from warehouse
from app.services.warehouse import _utcnow

from data.config import MASTER_DIR, PROCESSED_DIR
from data.fetchers.broadstreet import (
    BroadStreetFetcher,
    KillSwitchError,
    SoftBlockError,
    RequestCapExceeded,
)


# ===================== Warehouse integration =====================

def _archive_github_enabled() -> bool:
    """Robust parse of ARCHIVE_GITHUB (tolerates inline comments/whitespace)."""
    raw = os.getenv("ARCHIVE_GITHUB", "false")
    return raw.split("#")[0].strip().lower() in ("1", "true", "yes")


def _load_prices_to_warehouse(df, replace: bool, cutoff_date = None):
    """Push price data to the warehouse. Fail loudly (exit 5) on error;
    the scraped parquet is already on disk, so a re-run recovers."""
    if df is None or len(df) == 0:
        logger.info("Warehouse: nothing to load (empty dataframe)")
        return
    try:
        # Lazy import so `discover`/`macro` don't pull in GCP/psycopg2
        # or open DB connections.
        from app.services.warehouse import get_warehouse
        wh = get_warehouse()
        wh.write_price(df, replace=replace, cutoff_date=cutoff_date)
        logger.success(
            f"Warehouse: wrote {len(df):,} price rows "
            f"(mode={'replace' if replace else 'append'})"
        )
    except Exception as e:
        logger.error(f"Warehouse write FAILED: {e}")
        logger.error("Scraped parquet is intact on disk — re-run to retry.")
        sys.exit(5)


def _coerce_mentioned_tickers(value):
    """Normalize mentioned tickers from the news article payload."""
    if isinstance(value, list):
        return [str(t).strip().upper() for t in value if str(t).strip()]
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        if value.startswith("[") and value.endswith("]"):
            try:
                parsed = ast.literal_eval(value)
                if isinstance(parsed, list):
                    return [str(t).strip().upper() for t in parsed if str(t).strip()]
            except Exception:
                pass
        return [t.strip().upper() for t in re.split(r"[;,|]", value) if t.strip()]
    if value is None:
        return []
    if isinstance(value, (np.ndarray, pd.Series, tuple)):
        value = list(value)
        if not value:
            return []
        return _coerce_mentioned_tickers(value)
    try:
        if pd.isna(value):
            return []
    except ValueError:
        pass
    return [str(value).strip().upper()] if str(value).strip() else []


_POSITIVE_WORDS = {
    "good", "great", "positive", "up", "gain", "strong", "bull", "surge",
    "beat", "improve", "growth", "rise", "record", "win", "benefit",
}
_NEGATIVE_WORDS = {
    "bad", "poor", "negative", "down", "loss", "weak", "bear", "drop",
    "miss", "decline", "fall", "risks", "challenge", "worse", "pain",
}


def _score_text(text):
    """Return a lightweight sentiment score between -1 and 1."""
    if not isinstance(text, str) or not text.strip():
        return 0.0
    tokens = re.findall(r"\w+", text.lower())
    if not tokens:
        return 0.0
    pos = sum(1 for token in tokens if token in _POSITIVE_WORDS)
    neg = sum(1 for token in tokens if token in _NEGATIVE_WORDS)
    if pos == 0 and neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


def _load_news_articles():
    """Read all processed news article parquet files from disk."""
    articles_dir = Path(PROCESSED_DIR) / "news" / "articles"
    if not articles_dir.exists():
        logger.warning("No processed news articles directory found: %s", articles_dir)
        return pd.DataFrame(
            columns=[
                "published_date", "source", "headline", "article_text",
                "url", "mentioned_tickers",
            ]
        )

    paths = sorted(articles_dir.glob("**/articles.parquet"))
    frames = []
    for path in paths:
        try:
            frames.append(pd.read_parquet(path))
        except Exception as e:
            logger.warning("Skipping unreadable news parquet %s: %s", path, e)
    if not frames:
        return pd.DataFrame(
            columns=[
                "published_date", "source", "headline", "article_text",
                "url", "mentioned_tickers",
            ]
        )
    return pd.concat(frames, ignore_index=True)


def _build_daily_sentiment_summary():
    """Summarize news sentiment per date and ticker for warehouse loading."""
    articles = _load_news_articles()
    if articles.empty:
        logger.warning("No news articles available to build sentiment summary.")
        return pd.DataFrame(
            columns=[
                "date", "ticker", "avg_sentiment", "positive_count",
                "negative_count", "neutral_count", "total_articles",
                "ingested_at",
            ]
        )

    if "published_date" not in articles.columns:
        logger.warning("News articles missing published_date column.")
        return pd.DataFrame(
            columns=[
                "date", "ticker", "avg_sentiment", "positive_count",
                "negative_count", "neutral_count", "total_articles",
                "ingested_at",
            ]
        )

    articles["published_date"] = pd.to_datetime(
        articles["published_date"], errors="coerce"
    )
    articles = articles.dropna(subset=["published_date"])
    if articles.empty:
        logger.warning("News articles have no parsable published_date values.")
        return pd.DataFrame(
            columns=[
                "date", "ticker", "avg_sentiment", "positive_count",
                "negative_count", "neutral_count", "total_articles",
                "ingested_at",
            ]
        )

    articles["date"] = articles["published_date"].dt.date
    articles["mentioned_tickers"] = articles["mentioned_tickers"].apply(
        _coerce_mentioned_tickers
    )
    articles = articles.explode("mentioned_tickers")
    articles["ticker"] = (
        articles["mentioned_tickers"]
        .astype(str)
        .str.strip()
        .str.upper()
    )
    # Filter out empty tickers safely
    if len(articles) > 0:
        articles = articles[articles["ticker"].str.len() > 0]
    if articles.empty:
        logger.warning("No ticker mentions found in processed news articles.")
        return pd.DataFrame(
            columns=[
                "date", "ticker", "avg_sentiment", "positive_count",
                "negative_count", "neutral_count", "total_articles",
                "ingested_at",
            ]
        )

    headline = articles["headline"] if "headline" in articles.columns else pd.Series([""] * len(articles), index=articles.index)
    article_text = articles["article_text"] if "article_text" in articles.columns else pd.Series([""] * len(articles), index=articles.index)
    text_source = (headline.fillna("").astype(str) + " " + article_text.fillna("").astype(str))
    articles["sentiment_score"] = text_source.apply(_score_text)
    summary = (
        articles
        .groupby(["date", "ticker"], dropna=False, as_index=False)
        .agg(
            avg_sentiment=("sentiment_score", "mean"),
            positive_count=("sentiment_score", lambda s: int((s > 0).sum())),
            negative_count=("sentiment_score", lambda s: int((s < 0).sum())),
            neutral_count=("sentiment_score", lambda s: int((s == 0).sum())),
            total_articles=("sentiment_score", "count"),
        )
    )
    summary["ingested_at"] = _utcnow()
    return summary


def _save_daily_sentiment_summary_to_disk(df: pd.DataFrame):
    """Persist the daily sentiment summary locally as a parquet file."""
    out_dir = Path(PROCESSED_DIR) / "news"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "daily_sentiment_summary.parquet"
    try:
        df.to_parquet(out_path, index=False)
        logger.info("Wrote daily sentiment summary to %s", out_path)
    except Exception as e:
        logger.error("Failed to write local daily sentiment summary file: %s", e)
        raise


def _write_daily_sentiment_summary_to_warehouse(df: pd.DataFrame):
    """Write the daily sentiment summary dataframe to the configured warehouse."""
    if df is None:
        logger.warning("No sentiment summary dataframe provided.")
        return
    try:
        from app.services.warehouse import get_warehouse
        get_warehouse().write_daily_sentiment_summary(df)
        logger.success(
            f"Warehouse: wrote {len(df):,} daily sentiment summary rows"
        )
    except Exception as e:
        logger.error("Warehouse write FAILED: %s", e)
        sys.exit(5)


# ===================== Run-metrics recorder (Lane B / B1) =====================

_STATUS_FROM_EXIT = {
    0: "success",
    1: "failed",
    2: "killswitch",
    3: "soft_block",
    4: "cap_hit",
    5: "warehouse_failed",
    130: "interrupted",
}


@dataclass
class RunRecord:
    """One row of the pipeline_runs table; populated as a pipeline command
    executes, persisted on exit via the recorder."""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_name: str = ""
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    ended_at: datetime | None = None
    status: str = "running"
    exit_code: int = 0
    rows_written: int = 0
    tickers_updated: int = 0
    tickers_no_new: int = 0
    tickers_failed: int = 0
    error_message: str | None = None
    price_window_cutoff: str | None = None  # Date cutoff used for price windowing


# Module-level handle so daily()/backfill() can update counters without a
# signature change. CLI is single-threaded so a plain variable is fine.
_current_run: RunRecord | None = None


def _update_run(**kwargs):
    """Counter-update hook called from inside a pipeline command."""
    if _current_run is None:
        return
    for k, v in kwargs.items():
        if hasattr(_current_run, k):
            setattr(_current_run, k, v)


def _git_commit() -> str | None:
    """Resolve the current commit SHA — from CI env first, then local git."""
    sha = os.getenv("GITHUB_SHA")
    if sha:
        return sha
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return None


def _host() -> str:
    return "github-actions" if os.getenv("GITHUB_ACTIONS") else "local"


def _persist_run(rec: RunRecord) -> None:
    """Write the run record to BigQuery. Never raises — a recorder failure
    must not mask the original error that's already propagating."""
    try:
        from app.services.warehouse import get_warehouse
        duration = (rec.ended_at - rec.started_at).total_seconds()
        row = {
            "run_id": rec.run_id,
            "pipeline_name": rec.pipeline_name,
            "started_at": rec.started_at,
            "ended_at": rec.ended_at,
            "duration_seconds": duration,
            "status": rec.status,
            "exit_code": rec.exit_code,
            "rows_written": rec.rows_written,
            "tickers_updated": rec.tickers_updated,
            "tickers_no_new": rec.tickers_no_new,
            "tickers_failed": rec.tickers_failed,
            "error_message": rec.error_message,
            "price_window_cutoff": rec.price_window_cutoff,
            "git_commit": _git_commit(),
            "host": _host(),
        }
        get_warehouse().write_pipeline_run(pd.DataFrame([row]))
        logger.info(
            f"Recorded run: id={rec.run_id} status={rec.status} "
            f"exit={rec.exit_code} rows={rec.rows_written} "
            f"duration={duration:.1f}s"
        )
    except Exception as e:
        logger.error(f"Failed to record pipeline_run (non-fatal): {e}")


@contextmanager
def _record_run(pipeline_name: str):
    """Wrap a pipeline command. Captures exit status, populates the record
    from inside-the-command updates, and persists on exit (success/failure)."""
    global _current_run
    rec = RunRecord(pipeline_name=pipeline_name)
    _current_run = rec
    try:
        yield rec
        if rec.status == "running":
            rec.status = "success"
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        rec.exit_code = code
        rec.status = _STATUS_FROM_EXIT.get(code, "failed")
        rec.error_message = f"SystemExit({code})"
        raise
    except KeyboardInterrupt:
        rec.status = "interrupted"
        rec.exit_code = 130
        rec.error_message = "KeyboardInterrupt"
        raise
    except Exception as e:
        rec.status = "failed"
        rec.exit_code = 1
        rec.error_message = str(e)[:1000]
        raise
    finally:
        rec.ended_at = datetime.now(timezone.utc)
        _persist_run(rec)
        _current_run = None


# ===================== Stage 1 — discover =====================

def discover():
    """
    Stage 1: discover all sectors and tickers, write master/tickers.csv.
    """

    logger.info("=" * 60)
    logger.info("STAGE 1: DISCOVERY")
    logger.info("=" * 60)

    started = time.time()
    fetcher = BroadStreetFetcher(max_requests=50)

    try:
        fetcher.login()
        sectors = fetcher.fetch_sectors()

        all_companies = []
        for sector in sectors:
            companies = fetcher.fetch_companies_in_sector(
                sector["sector_id"],
                sector["sector_name"],
            )
            all_companies.extend(companies)

    except KillSwitchError as e:
        logger.error(f"KILLSWITCH: {e}")
        sys.exit(2)

    except SoftBlockError as e:
        logger.error(f"SOFT BLOCK detected: {e}")
        logger.error("Aborting to protect the account. Investigate before retrying.")
        sys.exit(3)

    except RequestCapExceeded as e:
        logger.error(f"REQUEST CAP hit: {e}")
        sys.exit(4)

    if not all_companies:
        logger.error("No companies discovered. Aborting before writing output.")
        sys.exit(1)

    df = pd.DataFrame(all_companies)
    df = (
        df.drop_duplicates(subset=["ticker"])
          .sort_values("ticker")
          .reset_index(drop=True)
    )

    Path(MASTER_DIR).mkdir(parents=True, exist_ok=True)
    output_path = f"{MASTER_DIR}/tickers.csv"
    df.to_csv(output_path, index=False)

    elapsed = time.time() - started
    logger.success(f"Wrote {len(df)} tickers to {output_path}")
    logger.info(f"Sectors covered: {df['sector'].nunique()}")
    logger.info(f"HTTP requests made: {fetcher.request_count}")
    logger.info(f"Elapsed: {elapsed:.1f}s")

    return df


# ===================== Stage 2 — backfill =====================

def backfill():
    """
    Stage 2: backfill historical OHLCV for all (or a pilot subset of) tickers.
    Writes one parquet per ticker to data/output/processed/prices/historical/.
    Resumable — tickers whose parquet exists are skipped.
    """

    pilot = sys.argv[2:] if len(sys.argv) > 2 else None

    tickers_path = f"{MASTER_DIR}/tickers.csv"
    if not os.path.exists(tickers_path):
        logger.error(f"{tickers_path} not found. Run `discover` first.")
        sys.exit(1)

    tickers_df = pd.read_csv(tickers_path)

    if pilot:
        tickers_df = tickers_df[tickers_df["ticker"].isin(pilot)]
        if len(tickers_df) == 0:
            logger.error(f"No tickers matched pilot list: {pilot}")
            sys.exit(1)
        logger.info(f"PILOT MODE: {len(tickers_df)} of {len(pilot)} requested matched")

    out_dir = Path(PROCESSED_DIR) / "prices" / "historical"
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info(f"STAGE 2: HISTORICAL BACKFILL ({len(tickers_df)} tickers)")
    logger.info("=" * 60)

    started = time.time()
    cap = 500 if pilot else 10000
    fetcher = BroadStreetFetcher(max_requests=cap)

    per_ticker_stats = {}
    done, skipped, failed, partial = 0, 0, 0, 0

    try:
        fetcher.login()

        for _, row in tickers_df.iterrows():

            ticker = row["ticker"]
            out_path = out_dir / f"{ticker}.parquet"

            if out_path.exists():
                logger.info(f"{ticker}: parquet exists, skipping")
                skipped += 1
                continue

            try:
                df, complete = fetcher.fetch_historical_prices(ticker)
            except (KillSwitchError, SoftBlockError, RequestCapExceeded):
                raise
            except Exception as e:
                logger.error(f"{ticker}: fetch failed — {e}")
                failed += 1
                continue

            if df.empty:
                logger.warning(f"{ticker}: empty history, skipping write")
                failed += 1
                continue

            df.to_parquet(out_path, index=False)
            per_ticker_stats[ticker] = {
                "rows": len(df),
                "first_date": str(df["date"].min()),
                "last_date": str(df["date"].max()),
                "status": "complete" if complete else "partial",
            }
            if complete:
                done += 1
            else:
                partial += 1
                logger.warning(
                    f"{ticker}: PARTIAL parquet written. "
                    f"Delete it and re-run backfill to retry the tail."
                )

            # Persist manifest after each ticker so progress is visible mid-run.
            _write_backfill_manifest(out_dir, started, fetcher, done, partial,
                                      skipped, failed, per_ticker_stats,
                                      status="in_progress")

    except KeyboardInterrupt:
        logger.warning("Ctrl+C received — saving manifest and exiting cleanly.")
        _write_backfill_manifest(out_dir, started, fetcher, done, partial, skipped, failed, per_ticker_stats, status="interrupted")
        sys.exit(130)

    except KillSwitchError as e:
        logger.error(f"KILLSWITCH: {e}")
        _write_backfill_manifest(out_dir, started, fetcher, done, partial, skipped, failed, per_ticker_stats, status="killswitch")
        sys.exit(2)

    except SoftBlockError as e:
        logger.error(f"SOFT BLOCK: {e}")
        logger.error("Aborting to protect the account.")
        _write_backfill_manifest(out_dir, started, fetcher, done, partial, skipped, failed, per_ticker_stats, status="soft_block")
        sys.exit(3)

    except RequestCapExceeded as e:
        logger.error(f"REQUEST CAP: {e}")
        logger.info(f"Progress so far: {done} done, {partial} partial, {skipped} skipped, {failed} failed")
        _write_backfill_manifest(out_dir, started, fetcher, done, partial, skipped, failed, per_ticker_stats, status="cap_hit")
        sys.exit(4)

    _write_backfill_manifest(out_dir, started, fetcher, done, partial, skipped, failed, per_ticker_stats, status="ok")

    elapsed = time.time() - started
    logger.success(
        f"Backfill complete: {done} new, {partial} partial, "
        f"{skipped} skipped, {failed} failed"
    )
    logger.info(f"Elapsed: {elapsed:.1f}s, Requests: {fetcher.request_count}")

    # Auto-rebuild the consolidated long-format table so downstream
    # consumers always see a fresh single-table artifact after every backfill.
    logger.info("Running consolidate step...")
    consolidated = consolidate()
    
    # Calculate cutoff for consistent windowing during write
    from datetime import timedelta
    window_days = int(os.getenv("POSTGRES_PRICE_WINDOW_DAYS", 730))
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=window_days)).date()
    
    _load_prices_to_warehouse(consolidated, replace=True, cutoff_date=cutoff_date)

    # Surface counters to the Lane B run recorder.
    _update_run(
        tickers_updated=done + partial,
        tickers_no_new=skipped,
        tickers_failed=failed,
        rows_written=len(consolidated) if consolidated is not None else 0,
        price_window_cutoff=str(cutoff_date),
    )


def _write_backfill_manifest(out_dir, started, fetcher, done, partial, skipped,
                              failed, per_ticker_stats, status):
    """Persist a JSON manifest summarizing the run, even on early abort."""
    manifest = {
        "stage": "backfill",
        "status": status,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(time.time() - started, 1),
        "tickers_complete": done,
        "tickers_partial": partial,
        "tickers_skipped": skipped,
        "tickers_failed": failed,
        "requests_made": fetcher.request_count,
        "tickers": per_ticker_stats,
    }
    with open(out_dir / "_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)


# ===================== Stage 3 — daily =====================

def daily():
    """
    Stage 3: incremental update.

    For each ticker that already has a parquet, fetch any new rows since
    the parquet's most recent date and append them. Designed to run on
    a schedule (e.g. weekdays after NGX market close).

    Skips tickers that don't yet have a parquet — those should be picked
    up by `backfill` first. Calls `consolidate()` at the end if anything
    was updated.
    """

    tickers_path = f"{MASTER_DIR}/tickers.csv"
    if not os.path.exists(tickers_path):
        logger.error(f"{tickers_path} not found. Run `discover` first.")
        sys.exit(1)

    tickers_df = pd.read_csv(tickers_path)

    out_dir = Path(PROCESSED_DIR) / "prices" / "historical"
    out_dir.mkdir(parents=True, exist_ok=True)  # local cache only; empty on CI

    logger.info("=" * 60)
    logger.info(f"STAGE 3: DAILY UPDATE ({len(tickers_df)} tickers)")
    logger.info("=" * 60)

    started = time.time()
    fetcher = BroadStreetFetcher(max_requests=1000)

    updated, no_new, not_backfilled, failed = 0, 0, 0, 0
    new_frames = []  # accumulate new rows across tickers for the warehouse

    # Incremental watermark comes from the WAREHOUSE, not local parquet,
    # so daily() works on a stateless CI runner. Fail before scraping if
    # the warehouse is unreachable — nothing to anchor against.
    try:
        from app.services.warehouse import get_warehouse
        last_dates = get_warehouse().get_last_dates()
    except Exception as e:
        logger.error(f"Could not read warehouse watermark: {e}")
        sys.exit(5)
    logger.info(f"Watermark: {len(last_dates)} tickers known in warehouse")

    try:
        fetcher.login()

        for _, row in tickers_df.iterrows():

            ticker = row["ticker"]
            out_path = out_dir / f"{ticker}.parquet"

            last_date = last_dates.get(ticker)
            if last_date is None:
                # Not in the warehouse yet — must be seeded by `backfill`.
                not_backfilled += 1
                continue

            # Fetch from the year of the last known date — gives us only
            # recent rows, not the full 30+ years of history.
            try:
                new_df, _ = fetcher.fetch_historical_prices(
                    ticker,
                    start_year=last_date.year,
                    use_cache=False,   # don't use stale cache for incremental
                    max_pages=20,      # 20 pages × 50 rows = plenty for a year
                )
            except (KillSwitchError, SoftBlockError, RequestCapExceeded):
                raise
            except Exception as e:
                logger.error(f"{ticker}: fetch failed — {e}")
                failed += 1
                continue

            if new_df.empty:
                no_new += 1
                continue

            new_df["date"] = pd.to_datetime(new_df["date"])
            # Strictly newer than what we already have
            new_rows = new_df[new_df["date"].dt.date > last_date]

            if new_rows.empty:
                no_new += 1
                continue

            # Per-ticker parquets don't carry the ticker column; the
            # warehouse price schema requires it.
            nr = new_rows.copy()
            nr["ticker"] = ticker
            new_frames.append(nr)

            # Local parquet is now just an optional cache: update it only
            # if it already exists (local dev). Skipped on a CI runner.
            if out_path.exists():
                try:
                    existing = pd.read_parquet(out_path)
                    existing["date"] = pd.to_datetime(existing["date"])
                    combined = (
                        pd.concat([existing, new_rows], ignore_index=True)
                          .drop_duplicates(subset=["date"])
                          .sort_values("date")
                          .reset_index(drop=True)
                    )
                    combined["date"] = combined["date"].dt.date
                    combined.to_parquet(out_path, index=False)
                except Exception as e:
                    logger.warning(f"{ticker}: parquet cache update skipped — {e}")

            logger.success(f"{ticker}: +{len(new_rows)} new row(s) since {last_date}")
            updated += 1

    except KillSwitchError as e:
        logger.error(f"KILLSWITCH: {e}")
        sys.exit(2)
    except SoftBlockError as e:
        logger.error(f"SOFT BLOCK: {e}")
        logger.error("Aborting to protect the account.")
        sys.exit(3)
    except RequestCapExceeded as e:
        logger.error(f"REQUEST CAP: {e}")
        sys.exit(4)

    elapsed = time.time() - started
    logger.success(
        f"Daily complete: {updated} updated, {no_new} no-new-data, "
        f"{not_backfilled} not-yet-backfilled, {failed} failed"
    )
    logger.info(f"Elapsed: {elapsed:.1f}s, Requests: {fetcher.request_count}")

    # Push only the genuinely-new rows (append). Postgres upserts safely;
    # BigQuery appends — scheduler must run daily at most once.
    rows_pushed = 0
    
    # Calculate cutoff for consistent windowing during write
    from datetime import timedelta
    window_days = int(os.getenv("POSTGRES_PRICE_WINDOW_DAYS", 730))
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=window_days)).date()
    
    if new_frames:
        combined_new = pd.concat(new_frames, ignore_index=True)
        rows_pushed = len(combined_new)
        _load_prices_to_warehouse(combined_new, replace=False, cutoff_date=cutoff_date)
    else:
        logger.info("No new rows — skipping warehouse write")

    # Surface counters to the Lane B run recorder (no-op if not in recorder).
    _update_run(
        tickers_updated=updated,
        tickers_no_new=no_new,
        tickers_failed=failed,
        rows_written=rows_pushed,
        price_window_cutoff=str(cutoff_date),
    )

    # Consolidated parquet only matters when archiving to GitHub.
    if updated > 0 and _archive_github_enabled():
        logger.info("Running consolidate step...")
        consolidate()
    else:
        logger.info("Skipping consolidate (warehouse is source of truth)")


# ===================== Stage 4 — consolidate =====================

def consolidate():
    """
    Stage 4: union all per-ticker parquets into a single long-format table.

    Reads every *.parquet in data/output/processed/prices/historical/,
    adds a 'ticker' column derived from the filename, normalizes dtypes,
    and writes the unified table to:
        data/output/processed/prices/historical_consolidated.parquet

    Safe to re-run any time — always rebuilds from scratch.
    """

    raw_dir = Path(PROCESSED_DIR) / "prices" / "historical"
    parquets = sorted(raw_dir.glob("*.parquet"))

    if not parquets:
        logger.error(f"No parquets found in {raw_dir}. Run backfill first.")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info(f"STAGE 4: CONSOLIDATE ({len(parquets)} per-ticker parquets)")
    logger.info("=" * 60)

    frames = []
    bad_files = []
    for p in parquets:
        try:
            df = pd.read_parquet(p)
        except Exception as e:
            logger.warning(f"Skipping unreadable parquet {p.name}: {e}")
            bad_files.append(p.name)
            continue
        df["ticker"] = p.stem
        frames.append(df)

    if bad_files:
        logger.warning(
            f"{len(bad_files)} corrupt parquet(s) skipped. Delete them and "
            f"re-run backfill to recover: {bad_files}"
        )

    if not frames:
        logger.error("No readable parquets found.")
        sys.exit(1)

    all_df = pd.concat(frames, ignore_index=True)
    all_df["date"] = pd.to_datetime(all_df["date"])
    all_df = (
        all_df.sort_values(["ticker", "date"])
              .reset_index(drop=True)
    )

    cols = ["date", "ticker", "pclose", "high", "low", "close", "volume", "change"]
    all_df = all_df[cols]

    logger.success(
        f"Consolidated {len(parquets)} tickers -> {len(all_df):,} rows "
        f"({all_df['ticker'].nunique()} unique tickers, "
        f"{all_df['date'].min().date()} -> {all_df['date'].max().date()})"
    )

    if _archive_github_enabled():
        out_path = Path(PROCESSED_DIR) / "prices" / "historical_consolidated.parquet"
        all_df.to_parquet(out_path, index=False)
        logger.info(f"ARCHIVE_GITHUB=true — wrote {out_path}")
    else:
        logger.info(
            "ARCHIVE_GITHUB not set — skipping consolidated parquet "
            "(warehouse is the source of truth)"
        )

    return all_df


# ===================== Stage 5 — macro =====================

def macro():
    """
    Stage 5: macro data fetchers.

    Runs all macro fetchers (CBN exchange rates, oil prices, etc.) in
    sequence. If one fetcher fails, logs the error and continues to the
    next — partial macro updates are better than no macro updates.

    To add a new fetcher: write a _run_<name>() function below, then
    register it in MACRO_FETCHERS.
    """

    logger.info("=" * 60)
    logger.info(f"STAGE 5: MACRO ({len(MACRO_FETCHERS)} fetcher(s))")
    logger.info("=" * 60)

    started = time.time()
    failures = []

    for label, fn in MACRO_FETCHERS:
        try:
            logger.info(f"Running: {label}")
            fn()
            logger.success(f"{label}: done")
        except Exception as e:
            logger.error(f"{label}: failed — {e}")
            failures.append(label)

    elapsed = time.time() - started
    if failures:
        logger.error(
            f"Macro stage finished with {len(failures)} failure(s) in "
            f"{elapsed:.1f}s: {failures}"
        )
        sys.exit(1)
    else:
        logger.success(
            f"Macro stage complete: {len(MACRO_FETCHERS)} fetcher(s) in {elapsed:.1f}s"
        )


def _run_cbn():
    from data.fetchers.cbn import CBNFetcher
    fetcher = CBNFetcher(max_requests=10)
    df = fetcher.fetch_exchange_rates()
    fetcher.save(df)


def _run_brent_oil():
    from data.fetchers.yfinance import YFinanceFetcher
    fetcher = YFinanceFetcher()
    df = fetcher.fetch_brent_oil()
    fetcher.save(df)


def _run_asi_snapshot():
    """
    NSE All-Share Index daily snapshot from BroadStreet.
    Builds a forward-only historical series — each run captures today's
    close, volume, deals, etc. and appends a row per (date, indicator)
    via the macro long-format schema.
    """
    from pathlib import Path
    from data.fetchers.broadstreet import BroadStreetFetcher

    fetcher = BroadStreetFetcher(max_requests=5)
    fetcher.login()
    df = fetcher.fetch_asi_snapshot()
    if df.empty:
        logger.warning("ASI snapshot returned no rows — skipping save")
        return

    # Save using the same append-and-dedup pattern as CBNFetcher.save()
    out_dir = Path(PROCESSED_DIR) / "macro"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "broadstreet_index.parquet"

    if out_path.exists():
        existing = pd.read_parquet(out_path)
        existing["date"] = pd.to_datetime(existing["date"])
        combined = pd.concat([existing, df], ignore_index=True)
    else:
        combined = df

    combined = (
        combined
        .drop_duplicates(subset=["date", "indicator"], keep="last")
        .sort_values(["indicator", "date"])
        .reset_index(drop=True)
    )
    combined.to_parquet(out_path, index=False)
    logger.success(
        f"[asi] wrote {len(combined):,} rows to {out_path} "
        f"({len(df)} new this run)"
    )


# Register macro fetchers here. New ones go in this list.
MACRO_FETCHERS = [
    ("CBN exchange rates", _run_cbn),
    ("NSE All-Share Index snapshot (BroadStreet)", _run_asi_snapshot),
    # TODO: Brent oil disabled — yfinance + protobuf are incompatible with
    # Python 3.14 (TypeError on metaclasses with custom tp_new). Existing
    # Brent data (2007-05-15) is preserved in yahoo_macro.parquet. Re-enable
    # once yfinance/protobuf supports 3.14, OR replace with EIA / other source.
    # ("Brent crude oil (Yahoo)", _run_brent_oil),
]


# ===================== Stage 6 — news =====================
def news():
    """
    Stage 6: news data fetchers.

    Runs all configured news fetchers in sequence. If one fetcher fails,
    logs the error and continues — partial news ingestion beats none.

    Default cap of 20 articles per source per run keeps the polite-scraping
    contract intact. Override with NEWS_MAX_ARTICLES env var for backfills.
    """

    logger.info("=" * 60)
    logger.info(f"STAGE 6: NEWS ({len(NEWS_FETCHERS)} fetcher(s))")
    logger.info("=" * 60)

    started = time.time()
    failures = []

    for label, fn in NEWS_FETCHERS:
        try:
            logger.info(f"Running: {label}")
            fn()
            logger.success(f"{label}: done")
        except Exception as e:
            logger.error(f"{label}: failed — {e}")
            failures.append(label)

    # --- FIX: Calculate elapsed time right here ---
    elapsed = time.time() - started 

    if failures:
        logger.warning(
            f"News stage finished with {len(failures)} non-fatal failure(s) in "
            f"{elapsed:.1f}s: {failures}. Continuing with available data."
        )
    else:
        logger.success(
            f"News stage complete: {len(NEWS_FETCHERS)} fetcher(s) in {elapsed:.1f}s"
        )

    # Build and persist a news sentiment summary after news ingestion.
    summary_df = _build_daily_sentiment_summary()
    _save_daily_sentiment_summary_to_disk(summary_df)
    _write_daily_sentiment_summary_to_warehouse(summary_df)

    if not failures:
        logger.success(
            f"News stage complete: {len(NEWS_FETCHERS)} fetcher(s) in {elapsed:.1f}s"
        )

    # NEW: Also run full FinBERT pipeline if not disabled
    if os.getenv("NUPAT_DISABLE_FINBERT") != "1":
        try:
            from backend.app.nlp.sentiment_pipeline import run_pipeline
            run_pipeline(since_days_ago=1)
            logger.success("FinBERT sentiment pipeline complete")
        except Exception as e:
            logger.warning(f"FinBERT pipeline failed (non-fatal): {e}")


def sentiment_summary():
    """Build and load the daily sentiment summary from processed news articles."""
    logger.info("=" * 60)
    logger.info("STAGE 6b: NEWS SENTIMENT SUMMARY")
    logger.info("=" * 60)

    summary_df = _build_daily_sentiment_summary()
    _save_daily_sentiment_summary_to_disk(summary_df)
    _write_daily_sentiment_summary_to_warehouse(summary_df)


def _news_max_articles():
    """Default 20 per source; override with NEWS_MAX_ARTICLES env var."""
    raw = os.environ.get("NEWS_MAX_ARTICLES")
    return int(raw) if raw else 20


def _run_ngx_announcements():
    from data.fetchers.news.ngx_announcements import NGXAnnouncementsFetcher
    fetcher = NGXAnnouncementsFetcher(max_requests=200)
    fetcher.run(max_articles=_news_max_articles())


def _run_businessday():
    from data.fetchers.news.businessday import BusinessDayFetcher
    fetcher = BusinessDayFetcher(max_requests=200)
    fetcher.run(max_articles=_news_max_articles())


def _run_nairametrics():
    from data.fetchers.news.nairametrics import NairametricsFetcher
    # RSS-based — no request cap needed (only 4 feed URLs fetched per run)
    fetcher = NairametricsFetcher()
    fetcher.run(max_articles=_news_max_articles())


NEWS_FETCHERS = [
    ("Nairametrics (RSS)", _run_nairametrics),       # highest-value NGX source
    ("NGX Announcements", _run_ngx_announcements),   # official exchange notices
    ("BusinessDay Nigeria", _run_businessday),        # business daily
]


# ===================== CLI =====================

# ===================== Stage 7 — corporate actions (raw) =====================

def corporate_actions():
    """
    Stage 7 (piece 1): scrape RAW corporate-action records (cash dividends +
    bonus/share issues) from BroadStreet's Dividend History page for every
    ticker and write them to a staging parquet.

    This is a faithful, UNVALIDATED extraction. It does NOT write the
    warehouse `corporate_actions` table — ex-date and ratio reconciliation
    against the price series (piece 2) does that, so wrong adjustments can't
    be seeded here. Pilot subset: `corporate-actions GTB UBA`.
    """
    tickers_path = f"{MASTER_DIR}/tickers.csv"
    if not os.path.exists(tickers_path):
        logger.error(f"{tickers_path} not found. Run `discover` first.")
        sys.exit(1)

    tickers_df = pd.read_csv(tickers_path)
    pilot = sys.argv[2:] if len(sys.argv) > 2 else None
    if pilot:
        tickers_df = tickers_df[tickers_df["ticker"].isin(pilot)]
        logger.info(f"PILOT MODE: {len(tickers_df)} ticker(s)")

    out_dir = Path(PROCESSED_DIR) / "corporate_actions"
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info(f"STAGE 7: CORPORATE ACTIONS — RAW ({len(tickers_df)} tickers)")
    logger.info("=" * 60)

    started = time.time()
    fetcher = BroadStreetFetcher(max_requests=1000)
    frames, failed = [], 0

    try:
        fetcher.login()
        for _, row in tickers_df.iterrows():
            ticker = row["ticker"]
            try:
                df = fetcher.fetch_corporate_actions(ticker)
                if not df.empty:
                    frames.append(df)
            except (KillSwitchError, SoftBlockError, RequestCapExceeded):
                raise
            except Exception as e:
                logger.error(f"{ticker}: corporate-actions fetch failed — {e}")
                failed += 1
    except KillSwitchError as e:
        logger.error(f"KILLSWITCH: {e}")
        sys.exit(2)
    except SoftBlockError as e:
        logger.error(f"SOFT BLOCK: {e}")
        logger.error("Aborting to protect the account.")
        sys.exit(3)
    except RequestCapExceeded as e:
        logger.error(f"REQUEST CAP: {e}")
        sys.exit(4)

    cols = ["ticker", "declared_date", "action_type", "raw_value", "source"]
    all_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)

    out_path = out_dir / "raw_corporate_actions.parquet"
    all_df.to_parquet(out_path, index=False)

    elapsed = time.time() - started
    n_bonus = int((all_df["action_type"] == "bonus").sum()) if len(all_df) else 0
    n_cash = int((all_df["action_type"] == "cash_dividend").sum()) if len(all_df) else 0
    n_tickers = all_df["ticker"].nunique() if len(all_df) else 0
    logger.success(
        f"Corporate actions (raw): {len(all_df)} records "
        f"({n_bonus} bonus, {n_cash} cash) across {n_tickers} tickers, "
        f"{failed} failed -> {out_path}"
    )
    logger.info(f"Elapsed: {elapsed:.1f}s, Requests: {fetcher.request_count}")
    _update_run(tickers_updated=n_tickers, tickers_failed=failed,
                rows_written=len(all_df))


COMMANDS = {
    "discover": discover,
    "backfill": backfill,
    "daily": daily,
    "consolidate": consolidate,
    "macro": macro,
    "news": news,
    "sentiment-summary": sentiment_summary,
    "corporate-actions": corporate_actions,
}


def main():

    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Usage: python -m data.pipeline <command> [args]")
        print(f"Commands: {', '.join(COMMANDS.keys())}")
        print()
        print("Pilot backfill: python -m data.pipeline backfill GTB DCE MTN")
        sys.exit(1)

    cmd = sys.argv[1]
    with _record_run(cmd):
        COMMANDS[cmd]()


if __name__ == "__main__":
    main()
