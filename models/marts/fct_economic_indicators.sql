with monthly as (

    select * from {{ ref('int_indicators_monthly') }}

)

select
    date_month
    , indicator_code
    , value
from monthly
