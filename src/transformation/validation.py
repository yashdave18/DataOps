"""Fail before export if analytical grains, populations, or totals drift."""

import numpy as np
import pandas as pd

from ._checks import require_key


def validate_analytical_datasets(tables, analytical):
    """Return reconciliation evidence, raising ValueError on any failed check.

    Financial comparisons use an absolute one-cent tolerance and no relative
    tolerance. Source null amounts are excluded, never interpreted as ratings.
    """
    orders, customers, products = (analytical[name] for name in ['orders', 'customers', 'products'])
    source_orders = tables['olist_orders_dataset']
    source_customers = tables['olist_customers_dataset']
    source_products = tables['olist_products_dataset']
    items = tables['olist_order_items_dataset']
    payments = tables['olist_order_payments_dataset']
    rows = []

    def check(name, actual, expected, money=False):
        passed = bool(np.isclose(actual, expected, atol=0.01, rtol=0)) if money else bool(actual == expected)
        rows.append({'check': name, 'actual': actual, 'expected': expected, 'passed': passed})

    for name, frame, source, key in [
        ('orders', orders, source_orders, 'order_id'),
        ('customers', customers, source_customers, 'customer_unique_id'),
        ('products', products, source_products, 'product_id'),
    ]:
        require_key(frame, [key], name)
        check(f'{name}: row count', len(frame), source[key].nunique())
        check(f'{name}: full key population', set(frame[key]) == set(source[key]), True)
    for name, actual, expected in [
        ('orders: item value', orders['total_item_value'].sum(), items['price'].sum()),
        ('orders: freight', orders['total_freight'].sum(), items['freight_value'].sum()),
        ('orders: payments', orders['total_payment'].sum(), payments['payment_value'].sum()),
        ('customers: spend', customers['total_spend'].sum(), orders['total_payment'].sum()),
        ('products: revenue', products['revenue'].sum(), items['price'].sum()),
        ('products: freight', products['total_freight'].sum(), items['freight_value'].sum()),
    ]:
        check(name, actual, expected, money=True)
    for name, actual, expected in [
        ('orders: item count', orders['item_count'].sum(), len(items)),
        ('orders: payment count', orders['payment_count'].sum(), len(payments)),
        ('orders: review count', orders['has_review'].sum(), len(tables['olist_order_reviews_dataset'])),
        ('customers: order count', customers['order_count'].sum(), len(orders)),
        ('customers: item count', customers['total_items_purchased'].sum(), len(items)),
        ('customers: reviewed orders', customers['reviewed_order_count'].sum(), orders['review_score'].count()),
        ('products: units sold', products['units_sold'].sum(), len(items)),
        ('products: product/order pairs', products['order_count'].sum(), len(items[['product_id', 'order_id']].drop_duplicates())),
    ]:
        check(name, actual, expected)
    report = pd.DataFrame(rows)
    failed = report.loc[~report['passed']]
    if not failed.empty:
        raise ValueError('Analytical reconciliation failed:\n' + failed.to_string(index=False))
    return report
