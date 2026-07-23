{#
    Generic data-quality test: assert that a monthly series has no gaps.

    For each partition (e.g. one indicator), it walks the ordered months and
    flags any place where consecutive rows are more than one month apart. It is
    partition-aware, so series with different start dates are each checked over
    their own history — a series simply not existing yet is never a "gap".

    Usage (model-level):
        data_tests:
          - no_missing_months:
              date_column: date_month
              partition_by: indicator_code
#}

{% test no_missing_months(model, date_column, partition_by) %}

with ordered as (

    select
        {{ partition_by }} as partition_key
        , {{ date_column }} as month_date
        , lag({{ date_column }}) over (
            partition by {{ partition_by }}
            order by {{ date_column }}
        ) as prev_month_date
    from {{ model }}

)

select
    partition_key
    , prev_month_date
    , month_date
    , {{ dbt.datediff('prev_month_date', 'month_date', 'month') }} as month_gap
from ordered
where prev_month_date is not null
  and {{ dbt.datediff('prev_month_date', 'month_date', 'month') }} > 1

{% endtest %}
