"""
Quick cross-store consistency check with row-level details.

Run from ai-stock-broker-backend:
    python scripts/quick_check.py
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


def _pg_connect():
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


window_days = int(os.getenv("POSTGRES_PRICE_WINDOW_DAYS", 730))
cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).date()

print(f"Window: {window_days} days, cutoff: {cutoff}\n")

# PostgreSQL counts
conn = _pg_connect()
try:
    with conn.cursor() as cur:
        # Count by date
        cur.execute("""
            SELECT date, COUNT(*) cnt FROM price GROUP BY date ORDER BY date DESC LIMIT 10
        """)
        print("PostgreSQL - Last 10 days:")
        for date, cnt in cur.fetchall():
            print(f"  {date}: {cnt:,} rows")

        # Check for oldest date
        cur.execute("SELECT MIN(date) FROM price")
        min_pg = cur.fetchone()[0]
        print(f"\nPostgreSQL date range: {min_pg} to ?")

        # Total count
        cur.execute("SELECT COUNT(*) FROM price")
        pg_total = cur.fetchone()[0]
        print(f"Total PG rows: {pg_total:,}")

        # Check windowed count
        cur.execute("SELECT COUNT(*) FROM price WHERE date >= %s", (cutoff,))
        pg_windowed = cur.fetchone()[0]
        print(f"Windowed (>= {cutoff}): {pg_windowed:,}")

finally:
    conn.close()

# BigQuery counts
client = _bq_client()
project = os.getenv("GCP_PROJECT_ID")
dataset = os.getenv("BIGQUERY_MARKET_DATASET", "ngx_market_data")

# Count by date in BQ (same window)
query = f"""
    SELECT date, COUNT(*) cnt
    FROM `{project}.{dataset}.price`
    WHERE date >= @cutoff
    GROUP BY date
    ORDER BY date DESC
    LIMIT 10
"""
job_config = bigquery.QueryJobConfig(
    query_parameters=[bigquery.ScalarQueryParameter("cutoff", "DATE", cutoff)]
)
print("\nBigQuery - Last 10 days (windowed):")
df = client.query(query, job_config=job_config).to_dataframe()
for _, row in df.iterrows():
    print(f"  {row['date'].date()}: {int(row['cnt']):,} rows")

# Total windowed count in BQ
query = f"""
    SELECT COUNT(*) cnt
    FROM `{project}.{dataset}.price`
    WHERE date >= @cutoff
"""
df = client.query(query, job_config=job_config).to_dataframe()
bq_windowed = int(df['cnt'].iloc[0])
print(f"\nBigQuery windowed (>= {cutoff}): {bq_windowed:,}")

print(f"\n{'='*50}")
print(f"Drift: PG={pg_windowed:,} - BQ={bq_windowed:,} = {pg_windowed - bq_windowed:+,}")
print(f"Drift %: {abs(pg_windowed - bq_windowed)/max(bq_windowed, 1)*100:.3f}%")

# Check for duplicates in BQ
query = f"""
    SELECT date, ticker, COUNT(*) cnt
    FROM `{project}.{dataset}.price`
    WHERE date >= @cutoff
    GROUP BY date, ticker
    HAVING COUNT(*) > 1
"""
print("\nBigQuery duplicates (date, ticker pairs):")
df = client.query(query, job_config=job_config).to_dataframe()
if len(df) > 0:
    print(f"  Found {len(df)} duplicate (date, ticker) pairs:")
    for _, row in df.head(20).iterrows():
        print(f"    {row['date'].date()} {row['ticker']}: {int(row['cnt'])} copies")
else:
    print("  None found (dedup working correctly)")
