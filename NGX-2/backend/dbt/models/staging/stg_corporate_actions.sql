{{ config(materialized='view') }}

-- Staging view over the curated corporate_actions seed. Downstream
-- (fct_price_adjusted) reads from here so any future cleaning/normalisation
-- lives in one place. Excludes the EXMPL documentation rows from real
-- adjustment — they exist only to show the format.
select
    ticker,
    ex_date,
    action_type,
    ratio,
    dividend,
    source,
    notes
from {{ ref('corporate_actions') }}
where source != 'EXAMPLE_REPLACE'
