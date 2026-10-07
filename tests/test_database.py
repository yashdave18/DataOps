"""Run with OLIST_TEST_DATABASE_URL pointing to an empty disposable database.

Each test rolls back its whole transaction; no test modifies a production DB.
The opt-in URL must name a database ending in _test.
"""

import os
import unittest
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import psycopg
from psycopg.conninfo import conninfo_to_dict

from src.database.loader import load_cleaned_tables
from src.database.validation import validate_database
from src.database.warehouse import refresh_warehouse
from tests.database_fixtures import cleaned_tables

TEST_DSN = os.environ.get('OLIST_TEST_DATABASE_URL')


@unittest.skipUnless(TEST_DSN, 'Set OLIST_TEST_DATABASE_URL for PostgreSQL integration tests')
class DatabaseTests(unittest.TestCase):
    def setUp(self):
        if not conninfo_to_dict(TEST_DSN).get('dbname', '').endswith('_test'):
            self.fail('Integration database name must end in _test')
        self.connection = psycopg.connect(TEST_DSN)
        self.addCleanup(self.connection.close)
        self.addCleanup(self.connection.rollback)
        self.connection.execute('SELECT 1')  # outer transaction: test changes never commit
        self.tables = cleaned_tables()

    def test_full_load_sql_pandas_parity_and_intentional_replacement(self):
        counts = load_cleaned_tables(self.connection, self.tables)
        self.assertEqual(len(counts), 9)
        self.assertTrue(validate_database(self.connection, self.tables)['passed'].all())
        with self.assertRaisesRegex(ValueError, 'contain data'):
            load_cleaned_tables(self.connection, self.tables)
        load_cleaned_tables(self.connection, self.tables, replace=True)
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM olist.orders').fetchone()[0], 3)

    def test_failed_refresh_restores_preexisting_data(self):
        load_cleaned_tables(self.connection, self.tables)
        self.tables['order_items'].loc[0, 'product_id'] = 'orphan'
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            load_cleaned_tables(self.connection, self.tables, replace=True)
        self.assertEqual(self.connection.execute('SELECT SUM(price) FROM olist.order_items').fetchone()[0], 100)
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM olist.orders').fetchone()[0], 3)

    def test_duplicate_key_failure_rolls_back_refresh(self):
        load_cleaned_tables(self.connection, self.tables)
        self.tables['order_payments'].loc[1, 'payment_sequential'] = 1
        with self.assertRaises(psycopg.errors.UniqueViolation):
            load_cleaned_tables(self.connection, self.tables, replace=True)
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM olist.order_payments').fetchone()[0], 4)

    def test_warehouse_grain_geographic_gaps_and_repeatability(self):
        load_cleaned_tables(self.connection, self.tables)
        for _ in range(2):
            self.assertTrue(refresh_warehouse(self.connection)['passed'].all())
            self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM warehouse.fact_order_items').fetchone()[0], 4)
        missing = self.connection.execute("SELECT has_coordinates FROM warehouse.dim_geography WHERE zip_code_prefix = '04567'").fetchone()
        self.assertEqual(missing, (False,))
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM warehouse.dim_product WHERE category_english IS NULL').fetchone()[0], 1)
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM warehouse.dim_customer').fetchone()[0], 3)

    def test_pipeline_warehouse_failure_rolls_back_cleaned_refresh(self):
        from src.pipeline.runner import STAGES, run_path, run_stage
        from tests.test_pipeline import write_raw_fixture

        load_cleaned_tables(self.connection, self.tables)
        self.tables['order_items'].loc[0, 'price'] = 200.0
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_raw_fixture(root)
            run = run_path(root, 'warehouse-failure')
            for stage in STAGES[:STAGES.index('load_database')]:
                run_stage(stage, run, raw_dir=root / 'raw', with_database=True)
            with patch('src.database.connection.connect_database', return_value=nullcontext(self.connection)), \
                 patch('src.database.loader.read_cleaned_tables', return_value=self.tables), \
                 patch('src.database.warehouse.refresh_warehouse', side_effect=RuntimeError('warehouse failed')):
                with self.assertRaisesRegex(RuntimeError, 'warehouse failed'):
                    run_stage('load_database', run, with_database=True)
            self.assertFalse((run / 'load_database.json').exists())
            self.assertFalse((root / 'processed/CURRENT.json').exists())
        self.assertEqual(self.connection.execute('SELECT SUM(price) FROM olist.order_items').fetchone()[0], 100)


if __name__ == '__main__':
    unittest.main()
