"""
Bank of Canada Valet API -> BigQuery raw ingestion.

Idempotent, truncate-and-reload. One raw table per series in `boc_raw`.
This is plumbing for the pipeline, not the showpiece; it is deliberately simple
(no incremental logic, no orchestration).

Run:
    python ingestion/ingest_boc.py

Auth:
    Reads the service-account key path from the DBT_KEYFILE env var, the same
    variable dbt uses, so local and CI share one config. Set it first, e.g.:
        $env:DBT_KEYFILE = "$HOME\\.gcp\\dbt-runner-key.json"
"""

from __future__ import annotations

import os
import sys
import time

import requests
from google.cloud import bigquery
from google.oauth2 import service_account

# --- config -------------------------------------------------------------
VALET_BASE = "https://www.bankofcanada.ca/valet"

PROJECT = "boc-dbt-portfolio-project"
RAW_DATASET = "boc_raw"
LOCATION = "northamerica-northeast2"

# indicator_code (our name, and the raw table name) -> Valet series name.
# All four confirmed against the live Valet API on 2026-07-07.
SERIES = {
    "policy_rate": "V39079",             # Target for the overnight rate (daily)
    "cpi":         "V41690973",          # Total CPI, index level (monthly)
    "fx_usdcad":   "FXUSDCAD",           # USD/CAD daily average exchange rate
    "bond_5yr":    "BD.CDN.5YR.DQ.YLD",  # GoC 5-year benchmark bond yield (daily)
}

START_DATE = "2000-01-01"  # ample history while keeping the dataset small
REQUEST_TIMEOUT = 30
MAX_RETRIES = 4            # BoC's endpoint intermittently resets the TLS handshake
RETRY_BACKOFF = 2.0        # seconds, doubled each attempt (also keeps us polite)
# -----------------------------------------------------------------------


def _get_json(url: str, params: dict) -> dict:
    """GET with retry + exponential backoff for flaky connections."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            if attempt == MAX_RETRIES:
                raise
            wait = RETRY_BACKOFF * (2 ** (attempt - 1))
            print(f"    attempt {attempt} failed ({exc.__class__.__name__}); "
                  f"retrying in {wait:.0f}s")
            time.sleep(wait)
    raise RuntimeError("unreachable")


def fetch_observations(series_name: str) -> list[dict]:
    """Pull all observations for one series from the Valet API.

    Valet returns observations shaped like:
        {"d": "2020-01-02", "<series_name>": {"v": "1.75"}}
    Rows with a missing/empty value (weekends, holidays) are dropped.
    """
    url = f"{VALET_BASE}/observations/{series_name}/json"
    payload = _get_json(url, params={"start_date": START_DATE})

    rows: list[dict] = []
    for obs in payload.get("observations", []):
        obs_date = obs.get("d")
        cell = obs.get(series_name)
        if not obs_date or not cell:
            continue
        raw_value = cell.get("v")
        if raw_value in (None, ""):
            continue
        rows.append(
            {
                "obs_date": obs_date,
                "series_name": series_name,
                "value": float(raw_value),
            }
        )
    return rows


def bq_client() -> bigquery.Client:
    key_path = os.environ.get("DBT_KEYFILE")
    if not key_path or not os.path.exists(key_path):
        sys.exit(
            "DBT_KEYFILE is not set or does not point to a file.\n"
            "Set it to the service-account key path, e.g.\n"
            '  $env:DBT_KEYFILE = "$HOME\\.gcp\\dbt-runner-key.json"'
        )
    creds = service_account.Credentials.from_service_account_file(key_path)
    return bigquery.Client(project=PROJECT, credentials=creds, location=LOCATION)


def load_table(client: bigquery.Client, table_name: str, rows: list[dict]) -> None:
    """Truncate-and-reload one raw table with an explicit schema."""
    table_id = f"{PROJECT}.{RAW_DATASET}.{table_name}"
    job_config = bigquery.LoadJobConfig(
        schema=[
            bigquery.SchemaField("obs_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("series_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("value", "FLOAT64", mode="REQUIRED"),
        ],
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    job = client.load_table_from_json(rows, table_id, job_config=job_config)
    job.result()  # block until the load completes
    print(f"  loaded {len(rows):>6} rows -> {table_id}")


def main() -> None:
    client = bq_client()
    print(f"Ingesting {len(SERIES)} series into {PROJECT}.{RAW_DATASET} "
          f"(from {START_DATE})\n")
    for table_name, series_name in SERIES.items():
        print(f"- {table_name} ({series_name})")
        rows = fetch_observations(series_name)
        if not rows:
            print(f"  WARNING: no observations returned for {series_name}; skipping")
            continue
        load_table(client, table_name, rows)
    print("\nDone.")


if __name__ == "__main__":
    main()
