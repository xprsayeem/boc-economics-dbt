# Airflow orchestration (Phase 2)

Local-only Airflow (Docker Compose) running one DAG: **ingest raw → dbt build**,
daily, with retries. Not a cloud deploy — it demonstrates orchestration on the
same pipeline. The DAG targets BigQuery **`ci`** (`boc_analytics_ci`) so a
scheduled run never touches the main `boc_analytics` data or the dashboard.

- **Executor:** LocalExecutor + Postgres (no Redis/Celery — light, enough for one DAG).
- **Image:** stock `apache/airflow:2.10.5` + an **isolated `/opt/dbt-venv`** holding
  dbt and the ingestion deps, so dbt's dependencies never collide with Airflow's.
- **DAG** ([`dags/boc_pipeline_dag.py`](dags/boc_pipeline_dag.py)): `ingest_raw >> dbt_build`,
  `retries=2`, `schedule="@daily"`, `catchup=False`.
- **Auth:** the GCP key is mounted read-only and `DBT_KEYFILE` points at it; all
  config comes from a gitignored `.env`. Nothing secret is committed.

## Spin it up (PowerShell, Docker Desktop running)

```powershell
cd airflow
Copy-Item .env.example .env      # then edit GCP_KEYFILE_HOST (forward slashes)
docker compose up -d --build     # first build pulls Airflow + installs dbt (~few min)
```

Open **http://localhost:8080**, log in with the user/password from your `.env`
(`airflow` / `airflow` by default), un-pause **`boc_pipeline`**, and trigger it.
You should see `ingest_raw` then `dbt_build` go green.

Stop it (keep the metadata DB):
```powershell
docker compose down
```
Tear everything down including volumes:
```powershell
docker compose down -v
```

## Evidence

Screenshot a successful run (Grid or Graph view, both tasks green) into
`docs/evidence/airflow_run.png` — referenced from the main README.

## Notes

- First `docker compose up --build` is slow (image build); later starts are fast.
- The whole repo is bind-mounted at `/opt/airflow/boc_project`; dbt writes
  `target/` and `dbt_packages/` there (both gitignored).
- To also orchestrate Snowflake later, add a second task/DAG that runs
  `ingest_boc.py --warehouse snowflake` + `dbt build --target snowflake` — the
  models are already warehouse-agnostic.
