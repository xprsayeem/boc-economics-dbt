with source as (

    select * from {{ source('boc_raw', 'cpi') }}

)

select
    cast(obs_date as date) as date_day
    , 'cpi' as indicator_code
    , cast(value as float64) as value
from source
