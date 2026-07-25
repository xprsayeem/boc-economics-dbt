"""
BoC pipeline DAG: ingest raw data, then dbt build — on a daily schedule.

Two tasks with a dependency (ingest -> dbt_build), retries, daily schedule, and
catchup disabled. dbt runs from its isolated venv (/opt/dbt-venv) against the
mounted project, targeting BigQuery `ci` (boc_analytics_ci) so a scheduled run
never touches the main boc_analytics data or the dashboard.
"""

from __future__ import annotations

import pendulum
from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = "/opt/airflow/boc_project"   # the repo, bind-mounted by docker-compose
DBT = "/opt/dbt-venv/bin/dbt"              # dbt in its isolated venv
PY = "/opt/dbt-venv/bin/python"           # same venv for the ingestion script

default_args = {
    "retries": 2,
    "retry_delay": pendulum.duration(minutes=2),
}

with DAG(
    dag_id="boc_pipeline",
    description="Ingest Bank of Canada raw data, then dbt build (BigQuery ci).",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    default_args=default_args,
    tags=["boc", "dbt", "bigquery"],
) as dag:

    ingest_raw = BashOperator(
        task_id="ingest_raw",
        bash_command=(
            f"cd {PROJECT_DIR} && "
            f"{PY} ingestion/ingest_boc.py --warehouse bigquery"
        ),
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=(
            f"cd {PROJECT_DIR} && "
            f"{DBT} deps && "
            f"{DBT} build --profiles-dir ci --target ci"
        ),
    )

    ingest_raw >> dbt_build
