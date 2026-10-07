import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


@unittest.skipUnless(os.environ.get('OLIST_TEST_SPARK') == '1', 'Set OLIST_TEST_SPARK=1 with Spark and Java 21 installed')
class SparkTests(unittest.TestCase):
    def test_spark_matches_pandas_with_multiple_children_and_missing_payments(self):
        from spark.transformations import run_comparison
        from src.database.loader import TABLES
        from tests.database_fixtures import cleaned_tables
        from src.transformation.transformations import build_analytical_datasets
        tables = {TABLES[name]: frame for name, frame in cleaned_tables().items()}
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name, frame in tables.items():
                frame.to_parquet(root / f'{name}.parquet', index=False)
            (root / 'analytical').mkdir()
            for name, frame in build_analytical_datasets(tables).items():
                frame.to_parquet(root / 'analytical' / f'{name}.parquet', index=False)
            self.assertTrue(run_comparison(root, root / 'spark')['passed'].all())
