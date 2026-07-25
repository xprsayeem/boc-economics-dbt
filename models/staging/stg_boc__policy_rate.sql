with source as (

    select * from {{ source('boc_raw', 'policy_rate') }}

)

select
    cast(obs_date as date) as date_day
    , 'policy_rate' as indicator_code
    , cast(value as {{ dbt.type_float() }}) as value
from source
