"""Tiny complete cleaned schema, including repeated reviews and geography gaps."""

import pandas as pd

from tests.test_transformations import example_tables
from src.database.loader import TABLES


def cleaned_tables():
    source = example_tables()
    tables = {table: source[name].copy() for table, name in TABLES.items() if name in source}
    customers = tables['customers']
    customers['customer_city'] = ['sao paulo', 'sao paulo', 'other', 'other']
    customers['customer_state'] = ['SP', 'SP', 'RJ', 'RJ']
    tables['geolocation'] = pd.DataFrame({
        'geolocation_zip_code_prefix': ['00123'], 'geolocation_lat': [-23.5],
        'geolocation_lng': [-46.6], 'geolocation_city': ['sao paulo'], 'geolocation_state': ['SP'],
    })
    tables['sellers'] = pd.DataFrame({
        'seller_id': ['s1', 's2'], 'seller_zip_code_prefix': ['00123', '88888'],
        'seller_city': ['sao paulo', 'other'], 'seller_state': ['SP', 'RJ'],
    })
    for column in ['product_name_length', 'product_description_length', 'product_photos_qty',
                   'product_length_cm', 'product_height_cm', 'product_width_cm']:
        tables['products'][column] = 1.0
    tables['orders']['flag_delivery_before_carrier'] = False
    tables['orders']['flag_delivered_missing_date'] = False
    tables['order_items']['shipping_limit_date'] = pd.Timestamp('2020-01-05')
    tables['order_payments']['payment_type'] = 'credit_card'
    tables['order_payments']['payment_installments'] = 1
    tables['order_payments']['flag_missing_first_payment'] = False
    reviews = tables['order_reviews']
    reviews['review_id'] = 'shared_review_id'  # legal: the same review_id can occur on different orders
    reviews['review_comment_title'] = pd.Series(['good', None], dtype='string')
    reviews['review_comment_message'] = pd.Series([None, None], dtype='string')
    reviews['review_creation_date'] = pd.Timestamp('2020-02-15')
    reviews['review_answer_timestamp'] = pd.Timestamp('2020-02-16')
    return tables
