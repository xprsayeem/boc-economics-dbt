# BoC Economics dbt Project

End-to-end analytics pipeline: Bank of Canada Valet API -> BigQuery -> dbt -> Looker Studio.

## Stack
- Warehouse: BigQuery (location: northamerica-northeast2)
- Transformation: dbt Core (dbt-bigquery)
- Ingestion: Python (ingestion/), lands raw tables in `boc_raw`
- CI: GitHub Actions runs `dbt build` on PR
- Viz: Looker Studio on the mart

## Datasets
- boc_raw: raw ingested series
- boc_analytics: dbt target (staging, intermediate, mart)

## Modeling layers
- staging (stg_): one model per BoC series, cleaned and typed
- intermediate (int_): union series into long format (date, indicator_code, value)
- mart: fct_economic_indicators + dim_indicator (seed)

## Series
Policy interest rate, CPI, CAD/USD exchange rate, GoC bond yield.

## Conventions
- All models documented in schema YAML
- Tests: not_null, unique, relationships, accepted_values, plus a custom no-date-gaps test