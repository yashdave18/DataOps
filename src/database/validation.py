"""Compare persisted SQL rows and business queries with independent Pandas results."""

from pathlib import Path

import pandas as pd
from psycopg import sql

from src.analytics import metrics

ROOT = Path(__file__).resolve().parents[2]
KEYS = {
    'geolocation': ['geolocation_zip_code_prefix'],
    'category_translation': ['product_category_name'],
    'customers': ['customer_id'], 'products': ['product_id'], 'sellers': ['seller_id'],
    'orders': ['order_id'], 'order_items': ['order_id', 'order_item_id'],
    'order_payments': ['order_id', 'payment_sequential'], 'order_reviews': ['order_id'],
}
QUERY_KEYS = {
    'overview': [], 'monthly_sales': ['month'], 'category_sales': ['category'],
    'seller_performance': ['seller_id'], 'customer_cohorts': ['cohort_month', 'month_offset'],
}


def query_frame(connection, query):
    cursor = connection.execute(query)
    return pd.DataFrame.from_records(cursor.fetchall(), columns=[column.name for column in cursor.description], coerce_float=True)


def compare_frames(actual, expected, keys):
    """Match by grain, checking nulls and values (SQL types may differ from Pandas)."""
    if keys:
        actual = actual.sort_values(keys)
        expected = expected.sort_values(keys)
    actual = actual.loc[:, expected.columns].reset_index(drop=True)
    expected = expected.reset_index(drop=True)
    # Nullable booleans and SQL NULLs share one explicit missing-value representation.
    actual = actual.convert_dtypes()
    expected = expected.convert_dtypes()
    pd.testing.assert_frame_equal(actual.isna(), expected.isna())
    for column in expected:
        present = expected[column].notna()
        # An entirely-null SQL text column may infer object rather than string.
        # Null positions are already checked; compare only observed values.
        if present.any():
            pd.testing.assert_series_equal(
                actual.loc[present, column].reset_index(drop=True),
                expected.loc[present, column].reset_index(drop=True),
                check_dtype=False, check_exact=False, atol=1e-8, rtol=1e-12,
            )


def pandas_order_metrics(tables):
    """Independent Pandas equivalent of olist.order_metrics, at order grain."""
    orders = tables['orders'].merge(tables['customers'], on='customer_id', validate='many_to_one')
    items = tables['order_items'].groupby('order_id').agg(item_count=('order_item_id', 'size'))
    items[['total_item_value', 'total_freight']] = tables['order_items'].groupby('order_id')[
        ['price', 'freight_value']
    ].sum(min_count=1).rename(columns={'price': 'total_item_value', 'freight_value': 'total_freight'})
    payments = tables['order_payments'].groupby('order_id').agg(payment_count=('payment_sequential', 'size'))
    payments['total_payment'] = tables['order_payments'].groupby('order_id')['payment_value'].sum(min_count=1)
    orders = orders.merge(items, on='order_id', how='left', validate='one_to_one').merge(
        payments, on='order_id', how='left', validate='one_to_one',
    ).merge(tables['order_reviews'][['order_id', 'review_score', 'has_comment']], on='order_id', how='left', validate='one_to_one')
    orders[['item_count', 'payment_count']] = orders[['item_count', 'payment_count']].fillna(0).astype('int64')
    orders['delivery_duration_days'] = (orders['order_delivered_customer_date'] - orders['order_purchase_timestamp']).dt.total_seconds() / 86400
    orders['delivery_delay_days'] = (orders['order_delivered_customer_date'].dt.normalize() - orders['order_estimated_delivery_date'].dt.normalize()).dt.days
    orders['is_late'] = orders['delivery_delay_days'].gt(0).astype('boolean').mask(orders['delivery_delay_days'].isna())
    return orders


def validate_database(connection, tables):
    rows = []
    for table, keys in KEYS.items():
        expected = tables[table]
        statement = sql.SQL('SELECT {} FROM olist.{}').format(
            sql.SQL(', ').join(map(sql.Identifier, expected.columns)), sql.Identifier(table),
        )
        compare_frames(query_frame(connection, statement), expected, keys)
        rows.append({'check': f'{table}: all values and nulls', 'rows': len(expected), 'passed': True})
    orders = pandas_order_metrics(tables)
    compare_frames(query_frame(connection, 'SELECT * FROM olist.order_metrics'), orders, ['order_id'])
    rows.append({'check': 'order_metrics: every order', 'rows': len(orders), 'passed': True})
    products = tables['products'].merge(tables['category_translation'], on='product_category_name', how='left', validate='many_to_one')
    expected_queries = {
        'overview': metrics.overview(orders),
        'monthly_sales': metrics.monthly_sales(orders),
        'category_sales': metrics.category_sales(orders, tables['order_items'], products),
        'seller_performance': metrics.seller_performance(orders, tables['order_items'], tables['sellers']),
        'customer_cohorts': metrics.customer_cohorts(orders),
    }
    for name, expected in expected_queries.items():
        statement = (ROOT / 'sql/queries' / f'{name}.sql').read_text(encoding='utf-8')
        compare_frames(query_frame(connection, statement), expected, QUERY_KEYS[name])
        rows.append({'check': f'{name}: SQL vs Pandas', 'rows': len(expected), 'passed': True})
    return pd.DataFrame(rows)


if __name__ == '__main__':
    from .connection import connect_database
    from .loader import read_cleaned_tables
    with connect_database() as connection:
        print(validate_database(connection, read_cleaned_tables()).to_string(index=False))
