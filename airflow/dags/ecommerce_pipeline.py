"""Static-snapshot DAG. Workers share OLIST_DATA_DIR; XCom carries paths only."""

from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path

from airflow.sdk import DAG, task, get_current_context

from src.pipeline.runner import STAGES, run_path, run_stage

with DAG(
    dag_id='ecommerce_pipeline',
    description='Validate, clean, transform, load, and publish an Olist snapshot',
    schedule=os.environ.get('OLIST_SCHEDULE') or None,
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args={'retries': 2, 'retry_delay': timedelta(minutes=2),
                  'execution_timeout': timedelta(minutes=60)},
    tags=['olist', 'batch'],
) as dag:
    @task(task_id='ingest')
    def ingest():
        context = get_current_context()
        identifier = 'airflow-' + hashlib.sha256(context['run_id'].encode()).hexdigest()[:24]
        data_dir = Path(os.environ.get('OLIST_DATA_DIR', '/opt/olist/data'))
        return run_stage('ingest', run_path(data_dir, identifier), raw_dir=data_dir / 'raw',
                         with_database=os.environ.get('OLIST_WITH_DATABASE', 'true').lower() == 'true')

    @task
    def execute_stage(directory, stage):
        return run_stage(stage, directory,
                         with_database=os.environ.get('OLIST_WITH_DATABASE', 'true').lower() == 'true')

    output = ingest()
    for stage_name in STAGES[1:]:
        output = execute_stage.override(task_id=stage_name)(output, stage_name)
