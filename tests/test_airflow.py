"""Run in the supplied Airflow image; no fake Airflow runtime is used."""

import importlib.util
import os
from pathlib import Path
import unittest


@unittest.skipUnless(os.environ.get('OLIST_TEST_AIRFLOW') == '1', 'Run inside the Airflow image with OLIST_TEST_AIRFLOW=1')
class AirflowTests(unittest.TestCase):
    def test_dag_import_dependencies_and_retry_policy(self):
        from src.pipeline.runner import STAGES
        path = Path(__file__).resolve().parents[1] / 'airflow/dags/ecommerce_pipeline.py'
        spec = importlib.util.spec_from_file_location('olist_test_dag', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        dag = module.dag
        self.assertEqual(set(dag.task_ids), set(STAGES))
        self.assertEqual(dag.max_active_runs, 1)
        self.assertFalse(dag.catchup)
        for index, name in enumerate(STAGES):
            task = dag.get_task(name)
            self.assertEqual(task.retries, 2)
            self.assertEqual(task.upstream_task_ids, {STAGES[index - 1]} if index else set())
