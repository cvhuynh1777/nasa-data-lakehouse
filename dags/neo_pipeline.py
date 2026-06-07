import os
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import subprocess
import sys

AIRFLOW_HOME = "/opt/airflow"

default_args = {
    "owner": "nasa-lakehouse",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

def run_extract():
    result = subprocess.run(
        [sys.executable, "ingestion/neo/extract.py"],
        cwd=AIRFLOW_HOME,
        capture_output=True,
        text=True
    )
    print(result.stdout)
    print(result.stderr)
    if result.returncode != 0:
        raise Exception(f"Extract failed: {result.stderr}")

def run_transform():
    result = subprocess.run(
        [sys.executable, "ingestion/neo/transform.py"],
        cwd=AIRFLOW_HOME,
        capture_output=True,
        text=True
    )
    print(result.stdout)
    print(result.stderr)
    if result.returncode != 0:
        raise Exception(f"Transform failed: {result.stderr}")

def run_enrich():
    result = subprocess.run(
        [sys.executable, "gold/neo/enrich.py"],
        cwd=AIRFLOW_HOME,
        capture_output=True,
        text=True
    )
    print(result.stdout)
    print(result.stderr)
    if result.returncode != 0:
        raise Exception(f"Enrich failed: {result.stderr}")

def run_catalog():
    result = subprocess.run(
        [sys.executable, "catalog/catalog.py"],
        cwd=AIRFLOW_HOME,
        capture_output=True,
        text=True
    )
    print(result.stdout)
    print(result.stderr)
    if result.returncode != 0:
        raise Exception(f"Catalog failed: {result.stderr}")

def run_sync():
    result = subprocess.run(
        [sys.executable, "storage/sync.py"],
        cwd=AIRFLOW_HOME,
        capture_output=True,
        text=True
    )
    print(result.stdout)
    print(result.stderr)
    if result.returncode != 0:
        raise Exception(f"Sync failed: {result.stderr}")

with DAG(
    "neo_pipeline",
    default_args=default_args,
    description="NEO asteroid data pipeline",
    schedule_interval="0 6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:

    extract   = PythonOperator(task_id="extract",   python_callable=run_extract)
    transform = PythonOperator(task_id="transform", python_callable=run_transform)
    enrich    = PythonOperator(task_id="enrich",    python_callable=run_enrich)
    catalog   = PythonOperator(task_id="catalog",   python_callable=run_catalog)
    sync      = PythonOperator(task_id="sync",      python_callable=run_sync)

    extract >> transform >> enrich >> catalog >> sync