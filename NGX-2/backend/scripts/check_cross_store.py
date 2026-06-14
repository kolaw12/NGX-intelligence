"""
Cross-store consistency check — PG (Neon, recent window) vs BQ (full history,
windowed to last POSTGRES_PRICE_WINDOW_DAYS days so it is apples-to-apples).

Asserts:
  - row counts match within ROW_TOLERANCE (default 0.1%)
  - MAX(date) matches within DATE_TOLERANCE_DAYS (default 1 day)

Exit codes:
  0  match within tolerance
  7  drift detected (distinct from pipeline exit 5 = warehouse failure)

Run from ai-stock-broker-backend:
    python scripts/check_cross_store.py
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

import psycopg2  # noqa: E402
from google.cloud import bigquery  # noqa: E402
from google.oauth2 import service_account  # noqa: E402


ROW_TOLERANCE = 0.001          # 0.1% row-count drift allowed
DATE_TOLERANCE_DAYS = 1        # MAX(date) within 1 calendar day
EXIT_DRIFT = 7


def _pg_connect():
    """Connect to Neon via DSN if POSTGRES_HOST is a URI, else discrete fields."""
    host = os.getenv("POSTGRES_HOST") or ""
    if host.startswith(("postgresql://", "postgres://")):
        return psycopg2.connect(host)
    return psycopg2.connect(
        host=host,
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        database=os.getenv("POSTGRES_DATABASE"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        sslmode=os.getenv("POSTGRES_SSLMODE", "prefer"),
    )


def pg_stats(cutoff):
    """Get PG stats windowed to the same cutoff as BQ."""
    conn = _pg_connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), MAX(date) FROM price WHERE date >= %s", (cutoff,))
            n, max_date = cur.fetchone()
        return int(n), max_date
    finally:
        conn.close()


def _bq_client():
    creds_path = os.getenv("GCP_CREDENTIALS_PATH")
    project = os.getenv("GCP_PROJECT_ID")
    if creds_path and os.path.exists(creds_path):
        creds = service_account.Credentials.from_service_account_file(creds_path)
        return bigquery.Client(project=project, credentials=creds)
    return bigquery.Client(project=project)


def get_latest_cutoff():
    """Retrieve the price_window_cutoff from the most recent pipeline run.
    Falls back to None if no recent run found (will calculate fresh cutoff)."""
    try:
        client = _bq_client()
        project = os.getenv("GCP_PROJECT_ID")
        dataset = os.getenv("BIGQUERY_RAW_DATASET", "ngx_raw_data")
        query = f"""
            SELECT price_window_cutoff
            FROM `{project}.{dataset}.pipeline_runs`
            WHERE pipeline_name IN ('daily', 'backfill')
              AND status = 'success'
            ORDER BY ended_at DESC
            LIMIT 1
        """
        df = client.query(query).to_dataframe()
        if not df.empty and df["price_window_cutoff"].iloc[0] is not None:
            return df["price_window_cutoff"].iloc[0]
    except Exception as e:
        logger.warning(f"Could not retrieve cutoff from pipeline_runs: {e}")
    return None


def bq_stats(window_days: int):
    client = _bq_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).date()
    project = os.getenv("GCP_PROJECT_ID")
    dataset = os.getenv("BIGQUERY_MARKET_DATASET", "ngx_market_data")
    query = f"""
        SELECT COUNT(*) AS n, MAX(date) AS max_date
        FROM `{project}.{dataset}.price`
        WHERE date >= @cutoff
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("cutoff", "DATE", cutoff)]
    )
    df = client.query(query, job_config=job_config).to_dataframe()
    return int(df["n"].iloc[0]), df["max_date"].iloc[0], cutoff


def main():
    window = int(os.getenv("POSTGRES_PRICE_WINDOW_DAYS", 730))

    # Try to retrieve the cutoff used by the most recent pipeline run
    # for true apples-to-apples comparison. Fall back to calculating fresh if unavailable.
    cutoff = get_latest_cutoff()
    if cutoff is None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=window)).date()
        print(f"Using calculated cutoff (no recent pipeline run found)")
    else:
        print(f"Using cutoff from latest pipeline run: {cutoff}")
    
    pg_rows, pg_max = pg_stats(cutoff)
    bq_rows, bq_max, _ = bq_stats(window)

    print(f"Cross-store consistency (window={window}d, cutoff={cutoff})")
    print(f"  PG:  {pg_rows:>10,} rows  max_date={pg_max}")
    print(f"  BQ:  {bq_rows:>10,} rows  max_date={bq_max}  (windowed)")

    failures = []

    # Row-count drift
    base = max(bq_rows, 1)
    row_drift_pct = abs(pg_rows - bq_rows) / base
    if row_drift_pct > ROW_TOLERANCE:
        failures.append(
            f"Row drift: PG={pg_rows:,} BQ={bq_rows:,} "
            f"diff={pg_rows - bq_rows:+,} ({row_drift_pct*100:.3f}% > "
            f"{ROW_TOLERANCE*100:.2f}%)"
        )

    # max_date drift
    if pg_max is None or bq_max is None:
        failures.append(f"NULL max_date — PG={pg_max} BQ={bq_max}")
    else:
        delta_days = abs((pg_max - bq_max).days)
        if delta_days > DATE_TOLERANCE_DAYS:
            failures.append(
                f"max_date drift: PG={pg_max} BQ={bq_max} "
                f"({delta_days}d > {DATE_TOLERANCE_DAYS}d)"
            )

    if failures:
        print("FAIL")
        for f in failures:
            print(f"  - {f}")
        sys.exit(EXIT_DRIFT)

    print("OK")


if __name__ == "__main__":
    main()
