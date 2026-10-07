"""Small, adversarial fixtures exercise grain and missing-data contracts."""

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from src.transformation.transformations import (
    build_analytical_datasets, load_processed_tables, save_analytical_datasets,
)


def example_tables():
    orders = pd.DataFrame({
        'order_id': ['o1', 'o2', 'o3'], 'customer_id': ['c1', 'c2', 'c3'],
        'order_status': ['delivered', 'delivered', 'canceled'],
        'order_purchase_timestamp': pd.to_datetime(['2020-01-01', '2020-02-01', '2020-03-01']),
        'order_approved_at': pd.to_datetime(['2020-01-02', '2020-02-01', None]),
        'order_delivered_carrier_date': pd.to_datetime(['2020-01-01', '2020-02-03', None]),
        'order_delivered_customer_date': pd.to_datetime(['2020-01-10 18:00', '2020-02-12 00:00', None]),
        'order_estimated_delivery_date': pd.to_datetime(['2020-01-10', '2020-02-10', '2020-03-20']),
        'flag_carrier_before_approval': [True, False, False],
    })
    return {
        'olist_orders_dataset': orders,
        'olist_customers_dataset': pd.DataFrame({
            'customer_id': ['c1', 'c2', 'c3', 'c4'],
            'customer_unique_id': ['u1', 'u1', 'u2', 'u3'],
            'customer_zip_code_prefix': ['00123', '00123', '04567', '99999'],
        }),
        'olist_order_items_dataset': pd.DataFrame({
            'order_id': ['o1', 'o1', 'o2', 'o2'], 'order_item_id': [1, 2, 1, 2],
            'product_id': ['p1', 'p1', 'p1', 'p2'], 'seller_id': ['s1', 's1', 's1', 's2'],
            'price': [10., 20., 30., 40.], 'freight_value': [1., 1., 2., 2.],
        }),
        'olist_order_payments_dataset': pd.DataFrame({
            'order_id': ['o1', 'o1', 'o1', 'o2'], 'payment_sequential': [1, 2, 3, 1],
            'payment_value': [5., 15., 12., 74.],
            'flag_zero_installments': [False, True, False, False],
        }),
        'olist_order_reviews_dataset': pd.DataFrame({
            'order_id': ['o1', 'o2'], 'review_score': [5, 1], 'has_comment': [True, False],
        }),
        'olist_products_dataset': pd.DataFrame({
            'product_id': ['p1', 'p2', 'p3'], 'product_category_name': ['a', 'untranslated', 'a'],
            'product_weight_g': [100., float('nan'), 200.],
            'flag_zero_weight': [False, True, False],
        }),
        'product_category_name_translation': pd.DataFrame({
            'product_category_name': ['a'], 'product_category_name_english': ['category a'],
        }),
    }


class TransformationTests(unittest.TestCase):
    def setUp(self):
        self.tables = example_tables()

    def test_child_joins_do_not_multiply_money_or_items(self):
        before = deepcopy(self.tables)
        result = build_analytical_datasets(self.tables)
        order = result['orders'].set_index('order_id').loc['o1']
        self.assertEqual(len(result['orders']), 3)
        self.assertEqual(order['total_item_value'], 30.)
        self.assertEqual(order['total_freight'], 2.)
        self.assertEqual(order['total_payment'], 32.)
        self.assertEqual(order['item_count'], 2)
        self.assertEqual(order['payment_count'], 3)
        self.assertEqual(order['product_count'], 1)
        self.assertTrue(order['flag_zero_installments'])
        for name, frame in self.tables.items():
            pd.testing.assert_frame_equal(frame, before[name])

    def test_missing_children_are_unknown_and_anomalies_preserved(self):
        orders = build_analytical_datasets(self.tables)['orders'].set_index('order_id')
        self.assertEqual(orders.loc['o3', 'item_count'], 0)
        for column in ['total_item_value', 'total_payment', 'review_score', 'has_comment', 'is_late']:
            self.assertTrue(pd.isna(orders.loc['o3', column]), column)
        self.assertEqual(orders.loc['o1', 'shipping_delay_days'], -1.)
        self.assertTrue(orders.loc['o1', 'flag_carrier_before_approval'])
        self.assertFalse(orders.loc['o1', 'is_late'])  # same-day delivery at 18:00
        self.assertEqual(orders.loc['o2', 'delivery_delay_days'], 2)

    def test_unique_customer_identity_and_customers_without_orders(self):
        customers = build_analytical_datasets(self.tables)['customers'].set_index('customer_unique_id')
        self.assertEqual(len(customers), 3)
        self.assertEqual(customers.loc['u1', 'order_count'], 2)
        self.assertEqual(customers.loc['u1', 'total_spend'], 106.)
        self.assertEqual(customers.loc['u1', 'average_order_value'], 53.)
        self.assertTrue(customers.loc['u1', 'is_repeat_customer'])
        self.assertTrue(pd.isna(customers.loc['u2', 'total_spend']))
        self.assertTrue(pd.isna(customers.loc['u2', 'average_review_score']))
        self.assertEqual(customers.loc['u3', 'order_count'], 0)
        self.assertEqual(customers.loc['u3', 'total_spend'], 0.)

    def test_product_reviews_are_weighted_per_order_not_per_unit(self):
        products = build_analytical_datasets(self.tables)['products'].set_index('product_id')
        self.assertEqual(products.loc['p1', 'revenue'], 60.)
        self.assertEqual(products.loc['p1', 'units_sold'], 3)
        self.assertEqual(products.loc['p1', 'customer_count'], 1)
        self.assertEqual(products.loc['p1', 'average_review_score'], 3.)
        self.assertEqual(products.loc['p1', 'review_count'], 2)
        self.assertTrue(products.loc['p2', 'flag_missing_category_translation'])
        self.assertEqual(products.loc['p3', 'revenue'], 0.)
        self.assertEqual(products.loc['p3', 'units_sold'], 0)
        self.assertTrue(pd.isna(products.loc['p3', 'average_review_score']))

    def test_unknown_amounts_are_not_zero(self):
        self.tables['olist_order_items_dataset'].loc[:, 'price'] = float('nan')
        self.tables['olist_order_payments_dataset'].loc[:, 'payment_value'] = float('nan')
        result = build_analytical_datasets(self.tables)
        self.assertTrue(result['orders']['total_payment'].isna().all())
        self.assertTrue(result['orders']['total_item_value'].isna().all())
        self.assertEqual(result['orders']['missing_item_price_count'].sum(), 4)
        self.assertEqual(result['orders']['missing_payment_value_count'].sum(), 4)
        self.assertTrue(result['products'].set_index('product_id').loc[['p1', 'p2'], 'revenue'].isna().all())

    def test_duplicate_grains_fail_instead_of_multiplying_rows(self):
        for name in self.tables:
            with self.subTest(table=name):
                changed = deepcopy(self.tables)
                changed[name] = pd.concat([changed[name], changed[name].iloc[[0]]], ignore_index=True)
                with self.assertRaisesRegex(ValueError, 'unique and non-null'):
                    build_analytical_datasets(changed)

    def test_orphan_and_null_keys_fail_without_silent_data_loss(self):
        cases = [
            ('olist_order_items_dataset', 'order_id'),
            ('olist_order_items_dataset', 'product_id'),
            ('olist_orders_dataset', 'customer_id'),
            ('olist_order_payments_dataset', 'order_id'),
            ('olist_order_reviews_dataset', 'order_id'),
            ('olist_customers_dataset', 'customer_unique_id'),
        ]
        for name, column in cases:
            for value in [None, 'orphan']:
                if column == 'customer_unique_id' and value == 'orphan':
                    continue  # A new non-null customer identity is valid.
                with self.subTest(table=name, column=column, value=value):
                    changed = deepcopy(self.tables)
                    changed[name].loc[0, column] = value
                    with self.assertRaises(ValueError):
                        build_analytical_datasets(changed)

    def test_empty_child_tables_retain_parent_population(self):
        for name in ['olist_order_items_dataset', 'olist_order_payments_dataset', 'olist_order_reviews_dataset']:
            self.tables[name] = self.tables[name].iloc[:0]
        result = build_analytical_datasets(self.tables)
        self.assertEqual(len(result['orders']), 3)
        self.assertEqual(len(result['products']), 3)
        self.assertEqual(result['orders']['item_count'].sum(), 0)
        self.assertTrue(result['orders']['total_payment'].isna().all())

    def test_export_round_trip_and_failed_reconciliation(self):
        result = build_analytical_datasets(self.tables)
        with TemporaryDirectory() as directory:
            report = save_analytical_datasets(self.tables, result, directory)
            self.assertTrue(report['passed'].all())
            for name, frame in result.items():
                pd.testing.assert_frame_equal(frame, pd.read_parquet(Path(directory) / f'{name}.parquet'))
            result['orders'].loc[0, 'total_payment'] += 10
            with self.assertRaisesRegex(ValueError, 'reconciliation failed'):
                save_analytical_datasets(self.tables, result, Path(directory) / 'invalid')
            self.assertFalse((Path(directory) / 'invalid').exists())

    def test_missing_inputs_and_uncleaned_dates_are_actionable(self):
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, 'src.cleaning.pipeline'):
                load_processed_tables(directory)
        self.tables['olist_orders_dataset']['order_purchase_timestamp'] = '2020-01-01'
        with self.assertRaisesRegex(ValueError, 'cleaned datetime'):
            build_analytical_datasets(self.tables)


if __name__ == '__main__':
    unittest.main()
