{{ config(materialized='view') }}

-- Staging view of NGX daily OHLCV. Downstream models (returns, features,
-- training datasets) read from here, never from the raw source directly.
select
    date,
    ticker,
    pclose,
    high,
    low,
    close,
    volume,
    change,
    ingested_at
from {{ source('ngx_market_data', 'price') }}
