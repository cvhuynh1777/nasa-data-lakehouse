from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import subprocess
import sys

default_args = {
    "owner": "nasa-lakehouse",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

def run_extract():
    subprocess.run([sys.executable, "ingestion/neo/extract.py"], check=True)

def run_transform():
    subprocess.run([sys.executable, "ingestion/neo/transform.py"], check=True)

def run_enrich():
    subprocess.run([sys.executable, "gold/neo/enrich.py"], check=True)

def run_catalog():
    subprocess.run([sys.executable, "catalog/catalog.py"], check=True)

def run_sync():
    subprocess.run([sys.executable, "storage/sync.py"], check=True)

with DAG(
    "neo_pipeline",
    default_args=default_args,
    description="NEO asteroid data pipeline",
    schedule_interval="0 6 * * *",  # daily at 6am
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:

    extract  = PythonOperator(task_id="extract",   python_callable=run_extract)
    transform = PythonOperator(task_id="transform", python_callable=run_transform)
    enrich   = PythonOperator(task_id="enrich",    python_callable=run_enrich)
    catalog  = PythonOperator(task_id="catalog",   python_callable=run_catalog)
    sync     = PythonOperator(task_id="sync",      python_callable=run_sync)

    extract >> transform >> enrich >> catalog >> sync