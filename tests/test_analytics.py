from copy import deepcopy
import unittest

import pandas as pd

from src.analytics import metrics
from src.analytics.reports import build_reports
from src.database.loader import TABLES
from src.transformation.transformations import build_analytical_datasets
from tests.database_fixtures import cleaned_tables


def analytical_fixture():
    tables = cleaned_tables()
    analytical = build_analytical_datasets({TABLES[name]: frame for name, frame in tables.items()})
    return {'orders': analytical['orders'], 'products': analytical['products'],
            'items': tables['order_items'], 'sellers': tables['sellers']}


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.data = analytical_fixture()

    def test_filters_include_entire_end_date_and_can_select_no_statuses(self):
        frame = self.data['orders'].copy()
        frame.loc[0, 'order_purchase_timestamp'] = pd.Timestamp('2020-01-01 23:59:59')
        self.assertEqual(len(metrics.select_orders(frame, ['delivered'], '2020-01-01', '2020-01-01')), 1)
        self.assertTrue(metrics.select_orders(frame, []).empty)

    def test_rates_exclude_unknown_outcomes_and_unknown_payments(self):
        result = metrics.overview(self.data['orders']).iloc[0]
        self.assertEqual(result['order_count'], 3)
        self.assertEqual(result['known_delivery_outcomes'], 2)
        self.assertEqual(result['late_delivery_rate'], 0.5)
        self.assertEqual(result['average_order_value'], 53.)
        self.assertEqual(result['repeat_customer_rate'], 0.5)

    def test_reports_reconcile_revenue_and_do_not_mutate_inputs(self):
        before = deepcopy(self.data)
        result = build_reports(self.data)
        # An unknown-revenue month does not erase the observed cumulative total.
        self.assertEqual(result['monthly_sales'].iloc[-1]['running_item_revenue'], 100.)
        for name in ['monthly_sales', 'category_sales', 'product_sales', 'seller_performance', 'geography']:
            self.assertEqual(result[name]['item_revenue'].sum(), 100., name)
        category = result['category_sales'].set_index('category').loc['category a']
        self.assertEqual(category['reviewed_orders'], 2)
        self.assertEqual(category['average_review_score'], 3.)
        for name in before:
            pd.testing.assert_frame_equal(self.data[name], before[name])

    def test_cohorts_zero_fill_observed_gaps_but_not_future_periods(self):
        result = metrics.customer_cohorts(self.data['orders'])
        jan = result[result['cohort_month'] == pd.Timestamp('2020-01-01')]
        march = result[result['cohort_month'] == pd.Timestamp('2020-03-01')]
        self.assertEqual(jan['customers'].tolist(), [1, 1, 0])
        self.assertEqual(march['month_offset'].tolist(), [0])
        self.assertTrue((result.loc[result['month_offset'] == 0, 'retention_rate'] == 1).all())

    def test_rfm_uses_snapshot_not_current_date(self):
        result = metrics.customer_rfm(self.data['orders']).set_index('customer_unique_id')
        self.assertEqual(result.loc['u2', 'recency_days'], 1)
        self.assertTrue(pd.isna(result.loc['u2', 'monetary']))
        with self.assertRaises(ValueError):
            metrics.customer_rfm(self.data['orders'], as_of='2019-12-01')

    def test_empty_selection_has_no_invented_metrics_and_all_reports_work(self):
        reports = build_reports(self.data, statuses=[])
        self.assertEqual(reports['overview'].iloc[0]['order_count'], 0)
        self.assertTrue(pd.isna(reports['overview'].iloc[0]['average_order_value']))
        for name, frame in reports.items():
            if name != 'overview':
                self.assertTrue(frame.empty, name)


if __name__ == '__main__':
    unittest.main()
