{{ config(materialized='table') }}

-- Daily returns on corporate-actions-ADJUSTED close. This is the table ML
-- should read for any return-based feature — returns computed on raw `close`
-- are wrong across split/bonus dates (see fct_price_adjusted / KNOWN_ISSUES).
--
-- One row per (ticker, date) that has a prior trading day. Returns use the
-- previous *available* adjusted close per ticker (gaps are spanned, not
-- zero-filled — be aware when a ticker has long trading gaps).

with adj as (
    select date, ticker, adj_close
    from {{ ref('fct_price_adjusted') }}
    where adj_close > 0          -- exclude no-trade / corrupt rows from the series
),

with_lag as (
    select
        date,
        ticker,
        adj_close,
        lag(adj_close) over (partition by ticker order by date) as prev_adj_close
    from adj
)

select
    date,
    ticker,
    adj_close,
    prev_adj_close,
    safe_divide(adj_close, prev_adj_close) - 1   as simple_return,
    ln(safe_divide(adj_close, prev_adj_close))   as log_return
from with_lag
where prev_adj_close is not null
