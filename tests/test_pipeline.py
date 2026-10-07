import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.database.loader import TABLES
from src.pipeline.runner import STAGES, run_pipeline, run_path, run_stage
from src.utils.paths import resolve_processed_dir
from tests.database_fixtures import cleaned_tables


def write_raw_fixture(root):
    raw = Path(root) / 'raw'
    raw.mkdir()
    for name, frame in cleaned_tables().items():
        frame.to_csv(raw / f'{TABLES[name]}.csv', index=False)


class PipelineTests(unittest.TestCase):
    def test_end_to_end_files_retry_and_published_run_immutability(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_raw_fixture(root)
            run = run_pipeline(root, 'first')
            self.assertEqual(resolve_processed_dir(root / 'processed'), run / 'processed')
            self.assertTrue(all((run / f'{stage}.json').exists() for stage in STAGES))
            mtime = (run / 'processed/analytical/orders.parquet').stat().st_mtime_ns
            run_pipeline(root, 'second')
            run_pipeline(root, 'first')  # old retries must not republish an older snapshot
            self.assertEqual(resolve_processed_dir(root / 'processed'), root / 'runs/second/processed')
            self.assertEqual((run / 'processed/analytical/orders.parquet').stat().st_mtime_ns, mtime)
            with self.assertRaisesRegex(ValueError, 'configuration changed'):
                run_pipeline(root, 'first', with_database=True)

    def test_failed_gate_preserves_last_published_snapshot(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_raw_fixture(root)
            good = run_pipeline(root, 'good')
            orders = root / 'raw/olist_orders_dataset.csv'
            content = orders.read_text()
            orders.write_text(content + content.splitlines()[1] + '\n')
            with self.assertRaisesRegex(ValueError, 'Quality gate'):
                run_pipeline(root, 'bad')
            self.assertEqual(resolve_processed_dir(root / 'processed'), good / 'processed')
            self.assertFalse((root / 'runs/bad/completed.json').exists())

    def test_snapshot_source_changes_and_out_of_order_stages_fail(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_raw_fixture(root)
            run = run_path(root, 'retry')
            with self.assertRaisesRegex(ValueError, 'requires completed'):
                run_stage('clean', run)
            run_stage('ingest', run, raw_dir=root / 'raw')
            path = root / 'raw/olist_orders_dataset.csv'
            path.write_text(path.read_text() + '\n')
            with self.assertRaisesRegex(ValueError, 'sources changed'):
                run_stage('ingest', run, raw_dir=root / 'raw')

    def test_paths_cannot_escape_run_storage(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                run_path(root, '../escape')
            processed = root / 'processed'
            processed.mkdir()
            (processed / 'CURRENT.json').write_text(json.dumps({'version': 1, 'processed_path': '../../escape'}))
            with self.assertRaisesRegex(ValueError, 'Invalid published'):
                resolve_processed_dir(processed)
