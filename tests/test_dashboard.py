import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from tests.test_analytics import analytical_fixture

ROOT = Path(__file__).resolve().parents[1]


class DashboardTests(unittest.TestCase):
    def test_views_and_empty_filter(self):
        data = analytical_fixture()
        with TemporaryDirectory() as directory:
            target = Path(directory)
            (target / 'analytical').mkdir()
            for name in ['orders', 'products']:
                data[name].to_parquet(target / 'analytical' / f'{name}.parquet', index=False)
            data['items'].to_parquet(target / 'olist_order_items_dataset.parquet', index=False)
            data['sellers'].to_parquet(target / 'olist_sellers_dataset.parquet', index=False)
            with patch.dict(os.environ, {'OLIST_PROCESSED_DIR': str(target)}):
                app = AppTest.from_file(str(ROOT / 'dashboards/app.py'), default_timeout=30).run()
                self.assertFalse(app.exception)
                self.assertEqual(app.metric[1].value, '2')  # delivered default
                for page in ['Sales', 'Customers', 'Logistics', 'Reviews']:
                    app.sidebar.radio[0].set_value(page).run()
                    self.assertFalse(app.exception, page)
                app.sidebar.multiselect[0].set_value([]).run()
                self.assertFalse(app.exception)
                self.assertIn('No orders match', app.info[0].value)

    def test_missing_data_has_actionable_message(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'OLIST_PROCESSED_DIR': directory}):
            app = AppTest.from_file(str(ROOT / 'dashboards/app.py'), default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertIn('not available', app.error[0].value)


if __name__ == '__main__':
    unittest.main()
