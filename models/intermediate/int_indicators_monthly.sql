with unioned as (

    select date_day, indicator_code, value from {{ ref('stg_boc__policy_rate') }}
    union all
    select date_day, indicator_code, value from {{ ref('stg_boc__cpi') }}
    union all
    select date_day, indicator_code, value from {{ ref('stg_boc__fx_usdcad') }}
    union all
    select date_day, indicator_code, value from {{ ref('stg_boc__bond_5yr') }}

)

-- Align every series to a common monthly grain. The daily series (policy_rate,
-- fx_usdcad, bond_5yr) collapse to their month-end observation; CPI is already
-- monthly. The month is keyed to its first day.
select
    date_trunc(date_day, month) as date_month
    , indicator_code
    , value
from unioned
qualify row_number() over (
    partition by indicator_code, date_trunc(date_day, month)
    order by date_day desc
) = 1
