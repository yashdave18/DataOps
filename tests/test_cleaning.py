from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from src.cleaning.customers import clean_customers
from src.cleaning.order_reviews import clean_order_reviews
from src.cleaning.products import clean_products
from src.utils.parquet import verify_parquet, write_verified_parquet


class CleaningPersistenceTests(unittest.TestCase):
    def test_parquet_preserves_leading_zeros_dates_flags_nulls_and_numbers(self):
        raw = pd.DataFrame({'customer_zip_code_prefix': [123, 4567]})
        frame = clean_customers(raw)
        self.assertEqual(raw.iloc[0, 0], 123)
        self.assertEqual(frame.iloc[0, 0], '00123')
        frame['date'] = pd.to_datetime(['2020-01-01', None])
        frame['flag'] = pd.Series([True, pd.NA], dtype='boolean')
        frame['amount'] = [0.01, float('nan')]
        frame.index = [10, 20]  # Storage intentionally omits the source index.
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'clean.parquet'
            write_verified_parquet(frame, path)
            restored = verify_parquet(frame, path)
            self.assertEqual(restored.loc[0, 'customer_zip_code_prefix'], '00123')

    def test_reviews_keep_latest_per_order_and_do_not_mutate_input(self):
        raw = pd.DataFrame({
            'order_id': ['o1', 'o1', 'o2'], 'review_id': ['r1', 'r2', 'r3'],
            'review_score': [1, 5, 3],
            'review_creation_date': ['2020-01-01'] * 3,
            'review_answer_timestamp': ['2020-01-02', '2020-01-03', '2020-01-02'],
            'review_comment_title': [None, 'good', None],
            'review_comment_message': [None, None, None],
        })
        before = raw.copy(deep=True)
        result = clean_order_reviews(raw).set_index('order_id')
        self.assertEqual(result.loc['o1', 'review_score'], 5)
        self.assertTrue(result.loc['o1', 'has_comment'])
        self.assertFalse(result.loc['o2', 'has_comment'])
        pd.testing.assert_frame_equal(raw, before)

    def test_zero_weight_is_flagged_and_unknown_not_imputed(self):
        raw = pd.DataFrame({'product_weight_g': [0., None, 100.], 'product_category_name': [None, 'a', 'b']})
        result = clean_products(raw)
        self.assertTrue(result.loc[0, 'flag_zero_weight'])
        self.assertTrue(pd.isna(result.loc[0, 'product_weight_g']))
        self.assertFalse(result.loc[1, 'flag_zero_weight'])
        self.assertEqual(raw.loc[0, 'product_weight_g'], 0.)


if __name__ == '__main__':
    unittest.main()
