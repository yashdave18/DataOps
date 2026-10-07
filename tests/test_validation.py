import unittest
import pandas as pd

from src.validation import data_quality as quality


class QualityTests(unittest.TestCase):
    def test_missing_duplicates_and_composite_keys_are_structured(self):
        frame = pd.DataFrame({'id': ['a', 'a', 'b', None], 'sequence': [1, 1, 2, 3]})
        before = frame.copy(deep=True)
        self.assertEqual(quality.check_missing_values(frame, 'test').iloc[0]['percent'], 25)
        self.assertEqual(quality.check_duplicates(frame, 'test').iloc[0]['count'], 1)
        findings = quality.check_unique_values(frame, 'test', ['id', 'sequence'])
        self.assertEqual(set(findings['check']), {'null_key', 'unique_values'})
        self.assertEqual(list(findings.columns), quality.cols)
        pd.testing.assert_frame_equal(frame, before)

    def test_ranges_dates_and_foreign_keys_exclude_unknown_values(self):
        frame = pd.DataFrame({'n': [-1., 0., 10., None], 'start': ['2020-01-02', None, None, None],
                              'end': ['2020-01-01', '2020-02-01', None, None]})
        self.assertEqual(quality.check_value_range(frame, 't', 'n', 0, 5).iloc[0]['count'], 2)
        self.assertEqual(quality.check_date_order(frame, 't', 'start', 'end').iloc[0]['count'], 1)
        child = pd.DataFrame({'id': ['a', 'orphan', None]})
        parent = pd.DataFrame({'id': ['a']})
        self.assertEqual(quality.check_referential_integrity(child, parent, 'c', 'p', 'id').iloc[0]['count'], 1)

    def test_type_checks_report_absent_columns_and_wrong_types(self):
        frame = pd.DataFrame({'n': [1, 2]})
        self.assertTrue(quality.check_data_type(frame, 't', 'n', 'int64').empty)
        self.assertEqual(quality.check_data_type(frame, 't', 'n', 'float64').iloc[0]['check'], 'data_type')
        self.assertEqual(quality.check_data_type(frame, 't', 'absent', str).iloc[0]['check'], 'missing_column')

    def test_categories_outliers_and_empty_tables(self):
        frame = pd.DataFrame({'category': [' Sao Paulo ', 'sao paulo', 'invalid']})
        findings = quality.check_categorical_values(frame, 't', 'category', ['sao paulo'])
        self.assertEqual(set(findings['check']), {'invalid_category', 'inconsistent_category'})
        numbers = pd.DataFrame({'n': [1, 1, 1, 1, 100]})
        self.assertEqual(quality.check_outliers(numbers, 't', 'n').iloc[0]['count'], 1)
        self.assertTrue(quality.check_outliers(numbers.iloc[:0], 't', 'n').empty)
        self.assertTrue(quality.check_missing_values(frame.iloc[:0], 't').empty)
