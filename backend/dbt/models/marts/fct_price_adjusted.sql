{{ config(materialized='table') }}

-- Corporate-actions-adjusted OHLCV (back-adjustment, CRSP-style).
--
-- adj_factor for a (ticker, date) = product of the price-adjustment factors
-- of every corporate action with ex_date STRICTLY AFTER that date. Prices on
-- or after the most recent action are unadjusted (factor 1.0). A ticker with
-- no actions is an identity (adj_* == raw).
--
-- v1 handles splits and bonuses — the cause of the large artificial price
-- jumps that break ML returns. Cash-dividend adjustment is a documented TODO
-- (needs the pre-ex close; the distortion is far smaller). See KNOWN_ISSUES.
--
-- Product of factors is computed as exp(sum(ln(factor))) since BigQuery has
-- no PRODUCT() aggregate.

with action_factors as (
    select
        ticker,
        ex_date,
        case action_type
            when 'split' then 1.0 / ratio            -- 2:1 split (ratio 2) -> 0.5
            when 'bonus' then 1.0 / (1.0 + ratio)     -- 1-for-10 bonus (ratio 0.1) -> ~0.909
            else 1.0                                  -- cash_dividend: TODO, no-op
        end as factor
    from {{ ref('stg_corporate_actions') }}
    where action_type in ('split', 'bonus')
),

-- One row per (price row × each future action on that ticker). Rows with no
-- future action get a NULL factor via the LEFT JOIN.
price_x_future_actions as (
    select
        p.date,
        p.ticker,
        p.pclose,
        p.high,
        p.low,
        p.close,
        p.volume,
        p.change,
        af.factor
    from {{ ref('stg_price') }} p
    left join action_factors af
        on  af.ticker = p.ticker
        and af.ex_date > p.date
),

with_factor as (
    select
        date,
        ticker,
        any_value(pclose) as pclose,
        any_value(high)   as high,
        any_value(low)    as low,
        any_value(close)  as close,
        any_value(volume) as volume,
        any_value(change) as change,
        exp(sum(ln(coalesce(factor, 1.0)))) as adj_factor
    from price_x_future_actions
    group by date, ticker
)

select
    date,
    ticker,
    close,                                        -- raw close, for reference
    volume,                                       -- raw volume, for reference
    adj_factor,
    round(pclose * adj_factor, 6) as adj_pclose,
    round(high   * adj_factor, 6) as adj_high,
    round(low    * adj_factor, 6) as adj_low,
    round(close  * adj_factor, 6) as adj_close,
    -- shares scale inversely to the price adjustment (more shares post-split)
    case when adj_factor = 0 then volume
         else cast(round(volume / adj_factor) as int64) end as adj_volume
from with_factor
