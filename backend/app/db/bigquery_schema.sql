-- BigQuery schema for the NGX warehouse (analytics / ML, full history).
-- Run in BigQuery Studio. Replace `your_project` with GCP_PROJECT_ID.
-- Datasets must be created first (Console -> Create dataset):
-- ngx_market_data, ngx_raw_data  (same location for both)

CREATE TABLE IF NOT EXISTS `stock-market-pipeline-496521.ngx_market_data.price` (
  date        DATE,
  ticker      STRING,
  pclose      FLOAT64,
  high        FLOAT64,
  low         FLOAT64,
  close       FLOAT64,
  volume      INT64,
  change      FLOAT64,
  ingested_at TIMESTAMP
)
-- UNPARTITIONED on purpose while this project is a BigQuery free-tier
-- sandbox. The sandbox forces a 60-day expiration on every partition, so a
-- partitioned table silently deletes all history older than 60 days (this
-- happened once — see KNOWN_ISSUES). An unpartitioned table avoids per-
-- partition deletion (the table as a whole still has a 60-day sandbox
-- expiration, but that's the original behaviour). RE-ADD
-- `PARTITION BY DATE_TRUNC(date, MONTH) CLUSTER BY ticker` once billing is
-- enabled and the expiration is removed.
;

-- Pipeline run metrics (Lane B observability). One row per `python -m data.pipeline <cmd>`
-- invocation, recorded on exit (success and failure both).
CREATE TABLE IF NOT EXISTS `stock-market-pipeline-496521.ngx_raw_data.pipeline_runs` (
  run_id                  STRING,
  pipeline_name           STRING,
  started_at              TIMESTAMP,
  ended_at                TIMESTAMP,
  duration_seconds        FLOAT64,
  status                  STRING,
  exit_code               INT64,
  rows_written            INT64,
  tickers_updated         INT64,
  tickers_no_new          INT64,
  tickers_failed          INT64,
  error_message           STRING,
  price_window_cutoff     DATE,
  git_commit              STRING,
  host                    STRING
)
PARTITION BY DATE(started_at)
CLUSTER BY pipeline_name, status;
