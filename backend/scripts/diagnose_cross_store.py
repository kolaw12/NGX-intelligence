"""
Detailed cross-store diagnostics to identify missing/duplicate rows.

Run from ai-stock-broker-backend:
    python scripts/diagnose_cross_store.py
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

import psycopg2
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd


def _pg_connect():
    """Connect to PostgreSQL."""
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


def _bq_client():
    creds_path = os.getenv("GCP_CREDENTIALS_PATH")
    project = os.getenv("GCP_PROJECT_ID")
    if creds_path and os.path.exists(creds_path):
        creds = service_account.Credentials.from_service_account_file(creds_path)
        return bigquery.Client(project=project, credentials=creds)
    return bigquery.Client(project=project)


def pg_data(window_days: int):
    """Get all PG price data within window (after filtering)."""
    conn = _pg_connect()
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).date()
        query = """
            SELECT date, ticker, pclose, close, high, low, volume, change
            FROM price
            WHERE date >= %s
            ORDER BY date, ticker
        """
        df = pd.read_sql_query(query, conn, params=[cutoff])
        df['date'] = pd.to_datetime(df['date']).dt.date
        return df
    finally:
        conn.close()


def bq_data(window_days: int):
    """Get all BQ price data within window."""
    client = _bq_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).date()
    project = os.getenv("GCP_PROJECT_ID")
    dataset = os.getenv("BIGQUERY_MARKET_DATASET", "ngx_market_data")
    query = f"""
        SELECT date, ticker, pclose, close, high, low, volume, change
        FROM `{project}.{dataset}.price`
        WHERE date >= @cutoff
        ORDER BY date, ticker
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("cutoff", "DATE", cutoff)]
    )
    df = client.query(query, job_config=job_config).to_dataframe()
    df['date'] = pd.to_datetime(df['date']).dt.date
    return df


def main():
    window = int(os.getenv("POSTGRES_PRICE_WINDOW_DAYS", 730))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window)).date()

    print(f"\n{'='*70}")
    print(f"Cross-Store Diagnostics (window={window}d, cutoff={cutoff})")
    print(f"{'='*70}\n")

    # Fetch data
    print("Fetching PostgreSQL data...")
    pg_df = pg_data(window)
    pg_df['store'] = 'PG'

    print("Fetching BigQuery data...")
    bq_df = bq_data(window)
    bq_df['store'] = 'BQ'

    # Create a unique key for comparison
    pg_df['key'] = pg_df['date'].astype(str) + '|' + pg_df['ticker']
    bq_df['key'] = bq_df['date'].astype(str) + '|' + bq_df['ticker']

    pg_keys = set(pg_df['key'])
    bq_keys = set(bq_df['key'])

    print(f"\nRow Counts:")
    print(f"  PG records:  {len(pg_df):,}")
    print(f"  BQ records:  {len(bq_df):,}")
    print(f"  Drift:       {len(pg_df) - len(bq_df):+,} ({abs(len(pg_df) - len(bq_df))/max(len(bq_df), 1)*100:.3f}%)")

    # Find differences
    pg_only = pg_keys - bq_keys
    bq_only = bq_keys - bq_keys
    common = pg_keys & bq_keys

    print(f"\nKey-level Analysis (date|ticker):")
    print(f"  In both stores:  {len(common):,}")
    print(f"  PG only:         {len(pg_only):,}")
    print(f"  BQ only:         {len(bq_only):,}")

    # Show sample of missing rows
    if pg_only:
        print(f"\n⚠️  Sample of rows IN PostgreSQL but MISSING in BigQuery:")
        sample = pg_df[pg_df['key'].isin(list(pg_only)[:10])][['date', 'ticker', 'pclose', 'volume']]
        for _, row in sample.iterrows():
            print(f"  {row['date']} | {row['ticker']:8s} | pclose={row['pclose']:>8.2f} | vol={row['volume']:>12,.0f}")

    if bq_only:
        print(f"\n✓ Rows IN BigQuery but MISSING in PostgreSQL (expected - older than window):")
        sample = bq_df[bq_df['key'].isin(list(bq_only)[:10])][['date', 'ticker', 'pclose', 'volume']]
        for _, row in sample.iterrows():
            print(f"  {row['date']} | {row['ticker']:8s} | pclose={row['pclose']:>8.2f} | vol={row['volume']:>12,.0f}")

    # Check for duplicate (date, ticker) pairs
    print(f"\nDuplicate Detection (same date|ticker multiple times):")
    pg_dupes = pg_df[pg_df.duplicated(subset=['key'], keep=False)]
    bq_dupes = bq_df[bq_df.duplicated(subset=['key'], keep=False)]
    print(f"  PG duplicates: {len(pg_dupes)}")
    print(f"  BQ duplicates: {len(bq_dupes)}")

    # Check date ranges
    print(f"\nDate Ranges:")
    print(f"  PG: {pg_df['date'].min()} to {pg_df['date'].max()}")
    print(f"  BQ: {bq_df['date'].min()} to {bq_df['date'].max()}")

    # Check ticker coverage
    pg_tickers = set(pg_df['ticker'].unique())
    bq_tickers = set(bq_df['ticker'].unique())
    print(f"\nTicker Coverage:")
    print(f"  PG tickers: {len(pg_tickers)}")
    print(f"  BQ tickers: {len(bq_tickers)}")
    missing_tickers = pg_tickers - bq_tickers
    if missing_tickers:
        print(f"  Missing from BQ: {sorted(missing_tickers)}")

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()
