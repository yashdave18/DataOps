import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.ingestion.csv_ingestion import expected_datasets, load_datasets


class IngestionTests(unittest.TestCase):
    def test_missing_or_empty_directory(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                load_datasets(Path(directory) / 'absent')
            with self.assertRaisesRegex(FileNotFoundError, 'No CSV'):
                load_datasets(directory)

    def test_nine_files_load_without_transformation_or_source_changes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            content = 'id,value\na,1\nb,\n'
            for name in expected_datasets:
                (root / f'{name}.csv').write_text(content)
            tables = load_datasets(root)
            self.assertEqual(set(tables), expected_datasets)
            self.assertTrue(all(len(frame) == 2 for frame in tables.values()))
            self.assertTrue(all(frame['value'].isna().sum() == 1 for frame in tables.values()))
            self.assertTrue(all(p.read_text() == content for p in root.glob('*.csv')))

    def test_missing_and_malformed_files_are_reported(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name in expected_datasets:
                (root / f'{name}.csv').write_text('id,value\na,1\n')
            (root / 'olist_orders_dataset.csv').write_text('id,value\n"unterminated')
            with self.assertRaisesRegex(ValueError, 'Failed to load.*olist_orders_dataset'):
                load_datasets(root)
            (root / 'olist_orders_dataset.csv').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing datasets.*olist_orders_dataset'):
                load_datasets(root)

    def test_unexpected_failed_csv_is_not_silently_ignored(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name in expected_datasets:
                (root / f'{name}.csv').write_text('id\na\n')
            (root / 'extra.csv').write_text('')
            with self.assertRaisesRegex(ValueError, 'Failed to load.*extra'):
                load_datasets(root)
