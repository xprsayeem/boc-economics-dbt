with source as (

    select * from {{ source('boc_raw', 'fx_usdcad') }}

)

select
    cast(obs_date as date) as date_day
    , 'fx_usdcad' as indicator_code
    , cast(value as {{ dbt.type_float() }}) as value
from source
