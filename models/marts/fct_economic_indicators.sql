with monthly as (

    select * from {{ ref('int_indicators_monthly') }}

)

select
    to_hex(md5(concat(cast(date_month as string), '|', indicator_code))) as indicator_month_key
    , date_month
    , indicator_code
    , value
from monthly
