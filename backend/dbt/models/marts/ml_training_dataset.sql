{{ config(materialized='table') }}

with returns as (
    select date, ticker, simple_return, log_return
    from {{ ref('fct_returns') }}
),

sentiment as (
    select date, ticker, avg_sentiment, positive_count, negative_count, neutral_count, total_articles
    from {{ source('ngx_market_data', 'daily_sentiment_summary') }}
),

labels as (
    select
        date,
        ticker,
        lead(adj_close, 1) over (partition by ticker order by date) as next_adj_close,
        safe_divide(lead(adj_close, 1) over (partition by ticker order by date) - adj_close, adj_close) as target_return
    from {{ ref('fct_price_adjusted') }}
)

select
    r.date,
    r.ticker,
    r.simple_return,
    r.log_return,
    s.avg_sentiment,
    s.positive_count,
    s.negative_count,
    s.neutral_count,
    s.total_articles,
    l.target_return,
    case when l.target_return > 0 then 1 else 0 end as target_up
from returns r
left join sentiment s using (date, ticker)
left join labels l using (date, ticker)
where l.target_return is not null
