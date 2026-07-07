# BoC Economics dbt Project

End-to-end analytics pipeline: Bank of Canada Valet API to BigQuery to dbt to Looker Studio.

## Stack
- Warehouse: BigQuery (northamerica-northeast2)
- Transformation: dbt Core (dbt-bigquery)
- Ingestion: Python, lands raw tables in boc_raw
- CI: GitHub Actions runs dbt build on PR
- Viz: Looker Studio on the mart
