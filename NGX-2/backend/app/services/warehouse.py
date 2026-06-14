from abc import ABC, abstractmethod
import os
import logging
from datetime import datetime, timezone, timedelta

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

try:
    from google.cloud import bigquery
    from google.oauth2 import service_account
    _GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    _GOOGLE_CLOUD_AVAILABLE = False

    class _GCPStub:
        """Stub so BigQueryAdapter class body parses when google-cloud is absent."""
        def __getattr__(self, name):
            return lambda *a, **kw: None

    bigquery = _GCPStub()        # type: ignore[assignment]
    service_account = _GCPStub()  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Canonical price schema (matches data/SCHEMAS.md and pipeline.consolidate()).
# NOTE: there is NO `open` column in this dataset. It is pclose + change.
PRICE_COLUMNS = ["date", "ticker", "pclose", "high", "low", "close", "volume", "change"]


def _utcnow():
    """Timezone-aware UTC now (datetime.utcnow() is deprecated in 3.12+)."""
    return datetime.now(timezone.utc)


# Base class for all warehouse adapters
class WarehouseAdapter(ABC):
    """Base class - defines what all warehouses must do"""

    @abstractmethod
    def write_price(self, df: pd.DataFrame, replace: bool = False):
        """Save price data. replace=True does a one-time full reload (idempotent)."""
        pass

    @abstractmethod
    def write_news_sentiment(self, df: pd.DataFrame):
        """Save news sentiment data"""
        pass

    @abstractmethod
    def write_news_articles(self, df: pd.DataFrame):
        """Save raw news article history"""
        pass

    @abstractmethod
    def write_daily_sentiment_summary(self, df: pd.DataFrame):
        """Save daily sentiment summary"""
        pass

    @abstractmethod
    def write_tickers(self, df: pd.DataFrame):
        """Save ticker metadata"""
        pass

    @abstractmethod
    def write_pipeline_run(self, df: pd.DataFrame):
        """Log pipeline run"""
        pass

    @abstractmethod
    def read_price(self, ticker: str = None, start_date: str = None):
        """Retrieve price data"""
        pass

    @abstractmethod
    def get_last_dates(self) -> dict:
        """Return {ticker: last known date} — the incremental watermark."""
        pass



# create postgres adapter
class PostgresAdapter(WarehouseAdapter):
    """Handles PostgreSQL operations.

    PostgreSQL is the app/API serving store. By design it holds only a
    RECENT WINDOW of price history (price_window_days); full history lives
    in BigQuery. Set price_window_days=None to disable the window and load
    everything.
    """

    def __init__(self, host: str, port: int, database: str, user: str,
                 password: str, price_window_days: int | None = 730,
                 sslmode: str = "prefer", dsn: str | None = None):
        """Connect to PostgreSQL.

        If dsn is given (e.g. a Neon 'postgresql://...' URI) it is used
        verbatim. Otherwise the connection is built from discrete fields;
        sslmode 'prefer' works locally, managed hosts need 'require'.
        """
        if dsn:
            self.conn = psycopg2.connect(dsn)
            logger.info("Connected to PostgreSQL via DSN URI")
        else:
            self.conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                sslmode=sslmode,
            )
            logger.info("Connected to PostgreSQL: %s (sslmode=%s)",
                        database, sslmode)
        self.price_window_days = price_window_days

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _window_filter(self, df: pd.DataFrame, cutoff_date=None) -> pd.DataFrame:
        """Keep only rows within the recent serving window (price only).
        If cutoff_date is provided, use it instead of calculating from current time."""
        if self.price_window_days is None or df.empty:
            return df
        if cutoff_date is None:
            cutoff = (_utcnow() - timedelta(days=self.price_window_days)).date()
        else:
            cutoff = cutoff_date
        dates = pd.to_datetime(df["date"]).dt.date
        filtered = df[dates >= cutoff]
        dropped = len(df) - len(filtered)
        if dropped:
            logger.info(
                "Postgres window: kept %d rows >= %s, dropped %d older rows "
                "(full history is in BigQuery)", len(filtered), cutoff, dropped
            )
        return filtered

    def _executemany(self, sql: str, rows: list[tuple]):
        """Batched insert via execute_values — orders of magnitude faster
        than per-row execute() for the 1.1M-row migration."""
        if not rows:
            return 0
        with self.conn.cursor() as cur:
            execute_values(cur, sql, rows, page_size=5000)
        self.conn.commit()
        return len(rows)

    def write_price(self, df: pd.DataFrame, replace: bool = False, cutoff_date=None):
        """Insert price data into PostgreSQL price table.

        Uses the canonical schema (pclose/change, NOT open). Idempotent via
        ON CONFLICT upsert; replace=True truncates first for a clean reload.
        If cutoff_date is provided, it's used for the window filter instead of
        calculating from current time (ensures consistency with pipeline run).
        """
        missing = [c for c in PRICE_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"price df missing columns: {missing}")

        df = self._window_filter(df, cutoff_date=cutoff_date)
        if df.empty:
            logger.info("Postgres price: nothing to write after window filter")
            return

        if replace:
            with self.conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE price")
            self.conn.commit()
            logger.info("Postgres price: TRUNCATEd for full reload")

        ingested = _utcnow()
        rows = [
            (
                r["date"], r["ticker"], r["pclose"], r["high"], r["low"],
                r["close"],
                None if pd.isna(r["volume"]) else int(r["volume"]),
                r["change"], ingested,
            )
            for r in df[PRICE_COLUMNS].to_dict("records")
        ]
        sql = """
            INSERT INTO price
            (date, ticker, pclose, high, low, close, volume, change, ingested_at)
            VALUES %s
            ON CONFLICT (date, ticker) DO UPDATE SET
              pclose = EXCLUDED.pclose, high = EXCLUDED.high,
              low = EXCLUDED.low, close = EXCLUDED.close,
              volume = EXCLUDED.volume, change = EXCLUDED.change,
              ingested_at = EXCLUDED.ingested_at
        """
        try:
            n = self._executemany(sql, rows)
        except Exception as e:
            self.conn.rollback()
            logger.error("Error writing price data: %s", e)
            raise
        logger.info("Wrote %d rows to PostgreSQL price table", n)

    def write_news_sentiment(self, df: pd.DataFrame):
        """Insert news sentiment data into PostgreSQL"""
        ingested = _utcnow()
        rows = [
            (
                r.get("title"), r.get("content"), r.get("source"),
                r.get("sentiment_score"), r.get("sentiment_label"),
                r.get("ticker"), r.get("published_at"), ingested,
            )
            for r in df.to_dict("records")
        ]
        sql = """
            INSERT INTO news_sentiment
            (title, content, source, sentiment_score, sentiment_label,
             ticker, published_at, created_at)
            VALUES %s
            ON CONFLICT DO NOTHING
        """
        try:
            n = self._executemany(sql, rows)
        except Exception as e:
            self.conn.rollback()
            logger.error("Error writing news sentiment: %s", e)
            raise
        logger.info("Wrote %d rows to PostgreSQL news_sentiment table", n)

    def write_news_articles(self, df: pd.DataFrame):
        """Raw article history lives in BigQuery, not the serving Postgres store."""
        logger.debug("Postgres: skipping write_news_articles (%d rows)", len(df))

    def write_daily_sentiment_summary(self, df: pd.DataFrame):
        """Insert daily sentiment summary into PostgreSQL"""
        rows = [
            (
                r.get("date"), r.get("ticker"), r.get("avg_sentiment"),
                r.get("positive_count"), r.get("negative_count"),
                r.get("neutral_count"), r.get("total_articles"),
            )
            for r in df.to_dict("records")
        ]
        sql = """
            INSERT INTO daily_sentiment_summary
            (date, ticker, avg_sentiment, positive_count, negative_count,
             neutral_count, total_articles)
            VALUES %s
            ON CONFLICT (date, ticker) DO UPDATE SET
              avg_sentiment = EXCLUDED.avg_sentiment,
              positive_count = EXCLUDED.positive_count,
              negative_count = EXCLUDED.negative_count,
              neutral_count = EXCLUDED.neutral_count,
              total_articles = EXCLUDED.total_articles
        """
        try:
            n = self._executemany(sql, rows)
        except Exception as e:
            self.conn.rollback()
            logger.error("Error writing daily sentiment summary: %s", e)
            raise
        logger.info("Wrote %d rows to PostgreSQL daily_sentiment_summary table", n)

    def write_tickers(self, df: pd.DataFrame):
        """Insert ticker metadata into PostgreSQL"""
        rows = [
            (r.get("symbol") or r.get("ticker"), r.get("name"),
             r.get("sector"), r.get("industry"))
            for r in df.to_dict("records")
        ]
        sql = """
            INSERT INTO tickers (symbol, name, sector, industry)
            VALUES %s
            ON CONFLICT (symbol) DO UPDATE SET
              name = EXCLUDED.name, sector = EXCLUDED.sector,
              industry = EXCLUDED.industry
        """
        try:
            n = self._executemany(sql, rows)
        except Exception as e:
            self.conn.rollback()
            logger.error("Error writing ticker: %s", e)
            raise
        logger.info("Wrote %d rows to PostgreSQL tickers table", n)

    def write_pipeline_run(self, df: pd.DataFrame):
        """Log pipeline run to PostgreSQL"""
        rows = [
            (
                r.get("pipeline_name"), r.get("status"),
                r.get("started_at"), r.get("ended_at"),
                r.get("records_processed"), r.get("error_message"),
            )
            for r in df.to_dict("records")
        ]
        sql = """
            INSERT INTO pipeline_runs
            (pipeline_name, status, started_at, ended_at,
             records_processed, error_message)
            VALUES %s
        """
        try:
            n = self._executemany(sql, rows)
        except Exception as e:
            self.conn.rollback()
            logger.error("Error writing pipeline run: %s", e)
            raise
        logger.info("Wrote %d rows to PostgreSQL pipeline_runs table", n)

    def read_price(self, ticker: str = None, start_date: str = None):
        """Read price data from PostgreSQL"""
        query = "SELECT * FROM price WHERE 1=1"
        params = []
        if ticker:
            query += " AND ticker = %s"
            params.append(ticker)
        if start_date:
            query += " AND date >= %s"
            params.append(start_date)
        query += " ORDER BY date DESC"
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            cols = [d[0] for d in cur.description]
            df = pd.DataFrame(cur.fetchall(), columns=cols)
        logger.info("Read %d rows from PostgreSQL price table", len(df))
        return df

    def get_last_dates(self) -> dict:
        """{ticker: max(date)} from Postgres (recent window only)."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT ticker, MAX(date) FROM price GROUP BY ticker")
            rows = cur.fetchall()
        return {t: d for t, d in rows if d is not None}


# create bigquery adapter
class BigQueryAdapter(WarehouseAdapter):
    """Handles BigQuery operations. BigQuery holds FULL history (analytics/ML)."""

    # Explicit schema for pipeline_runs so observability data never drifts.
    _PIPELINE_RUNS_SCHEMA = [
        bigquery.SchemaField("run_id", "STRING"),
        bigquery.SchemaField("pipeline_name", "STRING"),
        bigquery.SchemaField("started_at", "TIMESTAMP"),
        bigquery.SchemaField("ended_at", "TIMESTAMP"),
        bigquery.SchemaField("duration_seconds", "FLOAT"),
        bigquery.SchemaField("status", "STRING"),
        bigquery.SchemaField("exit_code", "INTEGER"),
        bigquery.SchemaField("rows_written", "INTEGER"),
        bigquery.SchemaField("tickers_updated", "INTEGER"),
        bigquery.SchemaField("tickers_no_new", "INTEGER"),
        bigquery.SchemaField("tickers_failed", "INTEGER"),
        bigquery.SchemaField("error_message", "STRING"),
        bigquery.SchemaField("price_window_cutoff", "DATE"),
        bigquery.SchemaField("git_commit", "STRING"),
        bigquery.SchemaField("host", "STRING"),
    ]

    # Explicit schema for price so the table type never drifts on auto-detect.
    _PRICE_SCHEMA = [
        bigquery.SchemaField("date", "DATE"),
        bigquery.SchemaField("ticker", "STRING"),
        bigquery.SchemaField("pclose", "FLOAT"),
        bigquery.SchemaField("high", "FLOAT"),
        bigquery.SchemaField("low", "FLOAT"),
        bigquery.SchemaField("close", "FLOAT"),
        bigquery.SchemaField("volume", "INTEGER"),
        bigquery.SchemaField("change", "FLOAT"),
        bigquery.SchemaField("ingested_at", "TIMESTAMP"),
    ]

    # Explicit schema for daily sentiment summary so empty writes still create
    # the table with expected columns.
    _DAILY_SENTIMENT_SUMMARY_SCHEMA = [
        bigquery.SchemaField("date", "DATE"),
        bigquery.SchemaField("ticker", "STRING"),
        bigquery.SchemaField("avg_sentiment", "FLOAT"),
        bigquery.SchemaField("positive_count", "INTEGER"),
        bigquery.SchemaField("negative_count", "INTEGER"),
        bigquery.SchemaField("neutral_count", "INTEGER"),
        bigquery.SchemaField("total_articles", "INTEGER"),
        bigquery.SchemaField("ingested_at", "TIMESTAMP"),
    ]

    _NEWS_ARTICLES_SCHEMA = [
        bigquery.SchemaField("published_date", "TIMESTAMP"),
        bigquery.SchemaField("source", "STRING"),
        bigquery.SchemaField("headline", "STRING"),
        bigquery.SchemaField("article_text", "STRING"),
        bigquery.SchemaField("url", "STRING"),
        bigquery.SchemaField("mentioned_tickers", "STRING", mode="REPEATED"),
        bigquery.SchemaField("ingested_at", "TIMESTAMP"),
    ]

    def __init__(self, project_id: str, raw_dataset: str = "ngx_raw_data",
                 market_dataset: str = "ngx_market_data",
                 credentials_path: str | None = None):
        """Connect to BigQuery with raw and market data datasets"""
        if not _GOOGLE_CLOUD_AVAILABLE:
            raise ImportError(
                "google-cloud-bigquery is not installed. "
                "Set DATA_WAREHOUSE_MODE=postgres to use Postgres only."
            )
        if credentials_path and os.path.exists(credentials_path):
            creds = service_account.Credentials.from_service_account_file(
                credentials_path
            )
            self.client = bigquery.Client(project=project_id, credentials=creds)
        else:
            # falls back to GOOGLE_APPLICATION_CREDENTIALS / ADC
            self.client = bigquery.Client(project=project_id)
        self.raw_dataset = raw_dataset
        self.market_dataset = market_dataset
        self.project_id = project_id
        logger.info(
            "Connected to BigQuery: %s (raw: %s, market: %s)",
            project_id, raw_dataset, market_dataset
        )

    def _load(self, df: pd.DataFrame, table_id: str, disposition: str,
              schema=None):
        job_config = bigquery.LoadJobConfig(write_disposition=disposition)
        if schema:
            job_config.schema = schema
        try:
            job = self.client.load_table_from_dataframe(
                df, table_id, job_config=job_config
            )
            job.result()
            logger.info("Wrote %d rows to BigQuery %s (%s)",
                        len(df), table_id, disposition)
        except Exception as e:
            logger.error("Error writing to BigQuery %s: %s", table_id, e)
            raise

    def write_price(self, df: pd.DataFrame, replace: bool = False, cutoff_date=None):
        """Write price data to BigQuery ngx_market_data.price.

        replace=True  -> WRITE_TRUNCATE (one-time full reload).
        replace=False -> WRITE_APPEND, then a CTAS dedupe.

        cutoff_date parameter is accepted for API consistency with PostgresAdapter
        but not used here since BigQuery stores full history.

        Free-tier design: this project is a BigQuery sandbox, which forbids
        DML (no MERGE upsert) and expires every table/partition after 60 days.
        The append path therefore loads new rows, then does a
        `CREATE OR REPLACE TABLE ... SELECT DISTINCT-latest` (DDL/CTAS, both
        sandbox-allowed). That CTAS does double duty:
          1. Idempotency  - removes any duplicate (date,ticker) from a
             double-run, so re-runs are harmless (mirrors PG's ON CONFLICT).
          2. Durability    - CREATE OR REPLACE resets the table's 60-day
             expiration clock, so as long as daily runs at least every ~60
             days the full history never expires. (Parquet is the backup if
             it ever lapses.)
        The table is kept UNPARTITIONED on purpose - a partitioned table gets
        per-partition 60-day expiration that silently deletes all history.
        """
        missing = [c for c in PRICE_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"price df missing columns: {missing}")
        out = df[PRICE_COLUMNS].copy()
        out["date"] = pd.to_datetime(out["date"]).dt.date
        out["ingested_at"] = _utcnow()
        table_id = f"{self.project_id}.{self.market_dataset}.price"

        if replace:
            self._load(out, table_id, "WRITE_TRUNCATE", schema=self._PRICE_SCHEMA)
            return

        self._load(out, table_id, "WRITE_APPEND", schema=self._PRICE_SCHEMA)
        self._dedupe_price()

    def _dedupe_price(self):
        """Sandbox-safe idempotency: rebuild price keeping the latest row per
        (date,ticker). Unpartitioned CTAS; also resets the 60-day expiration."""
        tid = f"`{self.project_id}.{self.market_dataset}.price`"
        self.client.query(f"""
            CREATE OR REPLACE TABLE {tid} AS
            SELECT * EXCEPT(rn) FROM (
              SELECT *, ROW_NUMBER() OVER (
                PARTITION BY date, ticker ORDER BY ingested_at DESC
              ) AS rn
              FROM {tid}
            )
            WHERE rn = 1
        """).result()
        logger.info("Deduped BigQuery price (CTAS); 60-day expiration reset")

    def write_news_sentiment(self, df: pd.DataFrame):
        table_id = f"{self.project_id}.{self.raw_dataset}.news_sentiment"
        self._load(df, table_id, "WRITE_APPEND")

    def write_news_articles(self, df: pd.DataFrame):
        table_id = f"{self.project_id}.{self.raw_dataset}.news_articles"
        out = df[
            [
                "published_date", "source", "headline", "article_text",
                "url", "mentioned_tickers",
            ]
        ].copy()
        out["published_date"] = pd.to_datetime(
            out["published_date"], errors="coerce", utc=True
        )
        out["mentioned_tickers"] = out["mentioned_tickers"].apply(
            lambda value: value if isinstance(value, list) else []
        )
        out["ingested_at"] = _utcnow()
        out = out.drop_duplicates(subset=["url"], keep="last")
        self._load(out, table_id, "WRITE_APPEND", schema=self._NEWS_ARTICLES_SCHEMA)
        self._dedupe_news_articles()

    def _dedupe_news_articles(self):
        tid = f"`{self.project_id}.{self.raw_dataset}.news_articles`"
        self.client.query(f"""
            CREATE OR REPLACE TABLE {tid}
            PARTITION BY DATE(published_date)
            CLUSTER BY source AS
            SELECT * EXCEPT(rn) FROM (
              SELECT *, ROW_NUMBER() OVER (
                PARTITION BY url ORDER BY ingested_at DESC
              ) AS rn
              FROM {tid}
            )
            WHERE rn = 1
        """).result()
        logger.info("Deduped BigQuery news_articles (CTAS)")

    def write_daily_sentiment_summary(self, df: pd.DataFrame):
        table_id = f"{self.project_id}.{self.market_dataset}.daily_sentiment_summary"
        self._load(df, table_id, "WRITE_APPEND",
                   schema=self._DAILY_SENTIMENT_SUMMARY_SCHEMA)
        self._dedupe_daily_sentiment_summary()

    def _dedupe_daily_sentiment_summary(self):
        tid = f"`{self.project_id}.{self.market_dataset}.daily_sentiment_summary`"
        self.client.query(f"""
            CREATE OR REPLACE TABLE {tid} AS
            SELECT * EXCEPT(rn) FROM (
              SELECT *, ROW_NUMBER() OVER (
                PARTITION BY date, ticker ORDER BY ingested_at DESC
              ) AS rn
              FROM {tid}
            )
            WHERE rn = 1
        """).result()
        logger.info("Deduped BigQuery daily_sentiment_summary (CTAS)")

    def write_tickers(self, df: pd.DataFrame):
        # Reference data — full replace each run.
        table_id = f"{self.project_id}.{self.market_dataset}.tickers"
        self._load(df, table_id, "WRITE_TRUNCATE")

    def write_pipeline_run(self, df: pd.DataFrame):
        table_id = f"{self.project_id}.{self.raw_dataset}.pipeline_runs"
        self._load(df, table_id, "WRITE_APPEND",
                   schema=self._PIPELINE_RUNS_SCHEMA)

    def read_price(self, ticker: str = None, start_date: str = None):
        """Read price data from BigQuery (parameterized — no f-string injection)."""
        query = (
            f"SELECT * FROM `{self.project_id}.{self.market_dataset}.price` "
            f"WHERE 1=1"
        )
        params = []
        if ticker:
            query += " AND ticker = @ticker"
            params.append(bigquery.ScalarQueryParameter("ticker", "STRING", ticker))
        if start_date:
            query += " AND date >= @start_date"
            params.append(
                bigquery.ScalarQueryParameter("start_date", "DATE", start_date)
            )
        query += " ORDER BY date DESC"
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        try:
            df = self.client.query(query, job_config=job_config).to_dataframe()
            logger.info("Read %d rows from BigQuery price table", len(df))
            return df
        except Exception as e:
            logger.error("Error reading from BigQuery: %s", e)
            raise

    def get_last_dates(self) -> dict:
        """{ticker: max(date)} from BigQuery full history. {} if table absent."""
        table = f"`{self.project_id}.{self.market_dataset}.price`"
        df = self.client.query(
            f"SELECT ticker, MAX(date) AS last_date FROM {table} GROUP BY ticker"
        ).to_dataframe()
        return {
            r["ticker"]: pd.to_datetime(r["last_date"]).date()
            for _, r in df.iterrows()
            if pd.notna(r["last_date"])
        }


# create hybrid warehouse that can write to both
class HybridWarehouse:
    """Writes to BOTH PostgreSQL and BigQuery.

    BigQuery gets full history; PostgreSQL gets only its recent serving
    window (enforced inside PostgresAdapter).
    """

    def __init__(self, bq_adapter: BigQueryAdapter, pg_adapter: PostgresAdapter):
        self.bq = bq_adapter
        self.pg = pg_adapter
        logger.info("Hybrid warehouse initialized (PostgreSQL + BigQuery)")

    def write_price(self, df: pd.DataFrame, replace: bool = False, cutoff_date=None):
        logger.info("Writing price data to both warehouses (replace=%s)...", replace)
        self.bq.write_price(df, replace=replace, cutoff_date=cutoff_date)
        self.pg.write_price(df, replace=replace, cutoff_date=cutoff_date)

    def write_news_sentiment(self, df: pd.DataFrame):
        self.bq.write_news_sentiment(df)
        self.pg.write_news_sentiment(df)

    def write_news_articles(self, df: pd.DataFrame):
        self.bq.write_news_articles(df)

    def write_daily_sentiment_summary(self, df: pd.DataFrame):
        self.bq.write_daily_sentiment_summary(df)
        self.pg.write_daily_sentiment_summary(df)

    def write_tickers(self, df: pd.DataFrame):
        self.bq.write_tickers(df)
        self.pg.write_tickers(df)

    def write_pipeline_run(self, df: pd.DataFrame):
        """Observability metrics — BigQuery only.

        pipeline_runs is analytics/observability data: queried by the runbook,
        the dashboard, and post-incident bisects. It has no app/API use case,
        so writing it to Postgres would cost storage + roundtrips for no
        consumer. Mirrors the get_last_dates() pattern (delegate to the right
        store rather than both).
        """
        self.bq.write_pipeline_run(df)

    def read_price(self, ticker: str = None, start_date: str = None):
        """Read from PostgreSQL (primary serving store)."""
        return self.pg.read_price(ticker, start_date)

    def get_last_dates(self) -> dict:
        """Watermark from BigQuery — the authoritative full-history store."""
        return self.bq.get_last_dates()


class NullWarehouse(WarehouseAdapter):
    """No-op warehouse for local development — parquet files are the only store."""

    def write_price(self, df: pd.DataFrame, replace: bool = False, **kwargs):
        logger.debug("NullWarehouse: skipping write_price (%d rows)", len(df))

    def write_news_sentiment(self, df: pd.DataFrame):
        logger.debug("NullWarehouse: skipping write_news_sentiment (%d rows)", len(df))

    def write_news_articles(self, df: pd.DataFrame):
        logger.debug("NullWarehouse: skipping write_news_articles (%d rows)", len(df))

    def write_daily_sentiment_summary(self, df: pd.DataFrame):
        logger.debug("NullWarehouse: skipping write_daily_sentiment_summary (%d rows)", len(df))

    def write_tickers(self, df: pd.DataFrame):
        logger.debug("NullWarehouse: skipping write_tickers (%d rows)", len(df))

    def write_pipeline_run(self, df: pd.DataFrame):
        logger.debug("NullWarehouse: skipping write_pipeline_run")

    def read_price(self, ticker: str = None, start_date: str = None):
        return pd.DataFrame()

    def get_last_dates(self) -> dict:
        """Derive watermarks from local per-ticker parquet files."""
        from pathlib import Path
        price_dir = Path(os.getenv("DATA_OUTPUT_DIR", "data/output")) / "processed" / "prices" / "historical"
        last_dates: dict = {}
        if price_dir.exists():
            for path in price_dir.glob("*.parquet"):
                try:
                    df = pd.read_parquet(path, columns=["date"])
                    if not df.empty:
                        last_dates[path.stem.upper()] = pd.to_datetime(df["date"]).max().date()
                except Exception:
                    pass
        logger.info("NullWarehouse watermark: %d tickers from local parquets", len(last_dates))
        return last_dates


# create helper function
def get_warehouse():
    """Initialize the right warehouse based on .env settings"""
    mode = os.getenv("DATA_WAREHOUSE_MODE", "hybrid")

    if mode == "local":
        return NullWarehouse()

    _pg_host = os.getenv("POSTGRES_HOST") or ""
    _pg_dsn = os.getenv("POSTGRES_URL")
    if not _pg_dsn and _pg_host.startswith(("postgresql://", "postgres://")):
        # User pasted the whole Neon/Supabase URI into POSTGRES_HOST.
        _pg_dsn = _pg_host
    pg = PostgresAdapter(
        host=_pg_host,
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        database=os.getenv("POSTGRES_DATABASE"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        price_window_days=int(os.getenv("POSTGRES_PRICE_WINDOW_DAYS", 730)),
        sslmode=os.getenv("POSTGRES_SSLMODE", "prefer"),
        dsn=_pg_dsn,
    )

    bq = BigQueryAdapter(
        project_id=os.getenv("GCP_PROJECT_ID"),
        raw_dataset=os.getenv("BIGQUERY_RAW_DATASET", "ngx_raw_data"),
        market_dataset=os.getenv("BIGQUERY_MARKET_DATASET", "ngx_market_data"),
        credentials_path=os.getenv("GCP_CREDENTIALS_PATH"),
    )

    if mode == "hybrid":
        return HybridWarehouse(bq, pg)
    elif mode == "bigquery":
        return bq
    else:
        return pg
