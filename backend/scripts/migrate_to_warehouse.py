"""
One-time migration: historical_consolidated.parquet -> warehouse

Idempotent: uses write_price(replace=True) so re-running fully reloads.
Run from the ai-stock-broker-backend directory:

    python -m scripts.migrate_to_warehouse --limit 5000   # smoke test first
    python -m scripts.migrate_to_warehouse
"""

import argparse
import sys 
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Make `app` / `data` importable no matter how this is invoked.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import pandas as pd
from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / '.env')

from app.services.warehouse import get_warehouse, PRICE_COLUMNS # noqa: E402

PARQUET = BACKEND_ROOT / "data/output/processed/prices/historical_consolidated.parquet"

def _count(table_client, kind):
    """Return COUNT(*) of the price table for a pg or bq adapter."""
    if kind == "pg":
        with table_client.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM price")
            return cur.fetchone()[0]
    q = (f"SELECT COUNT(*) AS n FROM"
            f" `{table_client.project_id}.{table_client.market_dataset}.price`")
    return int(table_client.client.query(q).to_dataframe()["n"].iloc[0])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type = int, default = None, help = "only migrate the first N rows (smoke test)")
    ap.add_argument("--yes", action = "store_true", help = "skip confirmation prompt")
    args = ap.parse_args()

    if not PARQUET.exists():
        sys.exit(f"ERROR: {PARQUET} not found. Run `python -m data.pipeline consolidate`first.")
    
    df = pd.read_parquet(PARQUET)
    missing = [c for c in PRICE_COLUMNS if c not in df.columns]
    if missing:
        sys.exit(f"ERROR: parquet missing columns {missing}; got "
                 f"{df.columns.tolist()}")
        
    # Normalize so both Postgres and BigQuery accept it cleanly.
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df[PRICE_COLUMNS]
    if args.limit:
        df = df.head(args.limit)

    n = len(df)
    window_days = int(__import__("os").getenv("POSTGRES_PRICE_WINDOW_DAYS", 730))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).date()
    expected_pg = int((pd.to_datetime(df["date"]) >= pd.Timestamp(cutoff)).sum())

    print(f"Parquet rows:            {n:,}")
    print(f"Expected in BigQuery:    {n:,} (full history)")
    print(f"Expected in Postgres:    {expected_pg:,} "
          f"(>= {cutoff}, window={window_days}d)")
    if not args.yes:
        if input("This TRUNCATEs and reloads price. Continue? [y/N] ").lower() != "y":
            sys.exit("Aborted.")

    wh = get_warehouse()
    wh.write_price(df, replace=True)

    # ---- verification ----
    ok = True
    pg = getattr(wh, "pg", wh if wh.__class__.__name__ == "PostgresAdapter" else None)
    bq = getattr(wh, "bq", wh if wh.__class__.__name__ == "BigQueryAdapter" else None)

    if bq is not None:
        got = _count(bq, "bq")
        flag = "OK" if got == n else "MISMATCH"
        ok &= got == n
        print(f"BigQuery price count:    {got:,}  [{flag}]")
    if pg is not None:
        got = _count(pg, "pg")
        flag = "OK" if got == expected_pg else "MISMATCH"
        ok &= got == expected_pg
        print(f"Postgres price count:    {got:,}  [{flag}]")
        pg.close()

    if not ok:
        sys.exit("VERIFICATION FAILED - counts do not match. Do NOT proceed.")
    print("Verification passed - counts match expected values.")


if __name__ == "__main__":
    main()