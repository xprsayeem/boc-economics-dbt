"""
Bank of Canada Valet API -> warehouse raw ingestion (BigQuery or Snowflake).

Idempotent, truncate-and-reload. One raw table per series in the `boc_raw`
schema. The same shape lands in both warehouses so the dbt models stay
warehouse-agnostic. This is plumbing, not the showpiece — deliberately simple
(no incremental logic, no orchestration).

Run (PowerShell):
    python ingestion\\ingest_boc.py                      # BigQuery (default)
    python ingestion\\ingest_boc.py --warehouse snowflake

The warehouse can also be set via the TARGET_WAREHOUSE env var; --warehouse wins.

Auth (same env vars the matching dbt target reads):
  BigQuery  - DBT_KEYFILE -> service-account key path.
  Snowflake - SNOWFLAKE_ACCOUNT / SNOWFLAKE_USER / SNOWFLAKE_PRIVATE_KEY_PATH /
              SNOWFLAKE_ROLE / SNOWFLAKE_WAREHOUSE / SNOWFLAKE_DATABASE
              (key-pair auth; optional SNOWFLAKE_PRIVATE_KEY_PASSPHRASE).
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import requests

# --- config -------------------------------------------------------------
VALET_BASE = "https://www.bankofcanada.ca/valet"

# BigQuery target
BQ_PROJECT = "boc-dbt-portfolio-project"
BQ_LOCATION = "northamerica-northeast2"

RAW_SCHEMA = "boc_raw"  # BigQuery dataset / Snowflake schema (same name in both)

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


# ---- BigQuery loader ---------------------------------------------------
def load_bigquery(series_rows: dict[str, list[dict]]) -> None:
    """Truncate-and-reload each raw table in BigQuery with an explicit schema."""
    from google.cloud import bigquery
    from google.oauth2 import service_account

    key_path = os.environ.get("DBT_KEYFILE")
    if not key_path or not os.path.exists(key_path):
        sys.exit(
            "DBT_KEYFILE is not set or does not point to a file.\n"
            'Set it, e.g.  $env:DBT_KEYFILE = "$HOME\\.gcp\\dbt-runner-key.json"'
        )
    creds = service_account.Credentials.from_service_account_file(key_path)
    client = bigquery.Client(project=BQ_PROJECT, credentials=creds, location=BQ_LOCATION)

    job_config = bigquery.LoadJobConfig(
        schema=[
            bigquery.SchemaField("obs_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("series_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("value", "FLOAT64", mode="REQUIRED"),
        ],
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    for table_name, rows in series_rows.items():
        table_id = f"{BQ_PROJECT}.{RAW_SCHEMA}.{table_name}"
        client.load_table_from_json(rows, table_id, job_config=job_config).result()
        print(f"  loaded {len(rows):>6} rows -> {table_id}")


# ---- Snowflake loader --------------------------------------------------
def load_snowflake(series_rows: dict[str, list[dict]]) -> None:
    """Truncate-and-reload each raw table in Snowflake (key-pair auth).

    Identifiers are written UNQUOTED so Snowflake folds them to upper case,
    matching dbt's unquoted (upper-folded) source and column references. This is
    the key casing detail: BigQuery preserves lowercase, Snowflake upper-cases,
    and keeping everything unquoted lets raw and staging line up on both.
    """
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization

    required = [
        "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PRIVATE_KEY_PATH",
        "SNOWFLAKE_ROLE", "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE",
    ]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        sys.exit("Missing Snowflake env vars: " + ", ".join(missing))

    key_path = os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"]
    if not os.path.exists(key_path):
        sys.exit(f"SNOWFLAKE_PRIVATE_KEY_PATH does not point to a file: {key_path}")
    passphrase = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE") or None
    with open(key_path, "rb") as fh:
        private_key = serialization.load_pem_private_key(
            fh.read(), password=passphrase.encode() if passphrase else None
        )
    pkb = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    database = os.environ["SNOWFLAKE_DATABASE"]
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key=pkb,
        role=os.environ["SNOWFLAKE_ROLE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=database,
    )
    try:
        cur = conn.cursor()
        cur.execute(f"create schema if not exists {RAW_SCHEMA}")
        for table_name, rows in series_rows.items():
            fq = f"{database}.{RAW_SCHEMA}.{table_name}"
            cur.execute(
                f"create or replace table {fq} "
                "(obs_date date, series_name string, value float)"
            )
            cur.executemany(
                f"insert into {fq} (obs_date, series_name, value) values (%s, %s, %s)",
                [(r["obs_date"], r["series_name"], r["value"]) for r in rows],
            )
            print(f"  loaded {len(rows):>6} rows -> {fq.upper()}")
        conn.commit()
    finally:
        conn.close()


LOADERS = {"bigquery": load_bigquery, "snowflake": load_snowflake}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest BoC series into a warehouse.")
    parser.add_argument(
        "--warehouse",
        choices=sorted(LOADERS),
        default=os.environ.get("TARGET_WAREHOUSE", "bigquery"),
        help="Target warehouse (default: TARGET_WAREHOUSE env var, else bigquery).",
    )
    args = parser.parse_args()

    print(f"Fetching {len(SERIES)} series from the Valet API (from {START_DATE})\n")
    series_rows: dict[str, list[dict]] = {}
    for table_name, series_name in SERIES.items():
        print(f"- {table_name} ({series_name})")
        rows = fetch_observations(series_name)
        if not rows:
            print(f"  WARNING: no observations returned for {series_name}; skipping")
            continue
        series_rows[table_name] = rows

    print(f"\nLoading into {args.warehouse} ({RAW_SCHEMA})\n")
    LOADERS[args.warehouse](series_rows)
    print("\nDone.")


if __name__ == "__main__":
    main()
