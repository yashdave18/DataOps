"""Run the actual DAG against tiny fixture files inside the Airflow image."""

from datetime import datetime, timezone
import importlib.util
import os
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_pipeline import write_raw_fixture
from src.utils.paths import resolve_processed_dir


if __name__ == '__main__':
    directory = Path(os.environ.get('OLIST_DATA_DIR', '/opt/olist/data')) / ('dag-test-' + uuid4().hex)
    directory.mkdir(parents=True)
    write_raw_fixture(directory)
    os.environ['OLIST_DATA_DIR'] = str(directory)
    os.environ['OLIST_WITH_DATABASE'] = 'false'
    # Load from Airflow's real DAG bundle so dag.test can re-parse it.
    path = Path('/opt/airflow/dags/ecommerce_pipeline.py')
    spec = importlib.util.spec_from_file_location('olist_dag_smoke', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.dag.test(logical_date=datetime.now(timezone.utc))
    if str(result.state) != 'success':
        raise RuntimeError(f'DAG did not succeed: {result.state}')
    processed = resolve_processed_dir(directory / 'processed')
    if not (processed / 'analytical/orders.parquet').is_file():
        raise RuntimeError('DAG did not publish a complete fixture snapshot')
    print('Actual Airflow DAG completed all stages and published the fixture snapshot.')
