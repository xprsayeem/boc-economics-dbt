with source as (

    select * from {{ source('boc_raw', 'bond_5yr') }}

)

select
    cast(obs_date as date) as date_day
    , 'bond_5yr' as indicator_code
    , cast(value as {{ dbt.type_float() }}) as value
from source
