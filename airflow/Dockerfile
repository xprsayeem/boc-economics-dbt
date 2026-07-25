# Airflow image for the BoC pipeline: stock Airflow 2.10 plus an ISOLATED
# virtualenv holding dbt + the ingestion deps. Keeping dbt in its own venv means
# its dependencies never collide with Airflow's pinned ones. The DAG calls
# /opt/dbt-venv/bin/{python,dbt} directly.
FROM apache/airflow:2.10.5-python3.12

USER root
RUN python -m venv /opt/dbt-venv
COPY requirements.txt /tmp/requirements.txt
RUN /opt/dbt-venv/bin/pip install --no-cache-dir --upgrade pip \
 && /opt/dbt-venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
USER airflow
