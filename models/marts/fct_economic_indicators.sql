with monthly as (

    select * from {{ ref('int_indicators_monthly') }}

)

select
    {{ dbt_utils.generate_surrogate_key(['date_month', 'indicator_code']) }} as indicator_month_key
    , date_month
    , indicator_code
    , value
from monthly
