"""Rebuild a validated type 1 star-schema snapshot from the cleaned database."""

from pathlib import Path

import pandas as pd

from .connection import connect_database

ROOT = Path(__file__).resolve().parents[2]


def refresh_warehouse(connection):
    with connection.transaction():
        # Same lock as the cleaned loader prevents refreshing mid-load.
        connection.execute('SELECT pg_advisory_xact_lock(746541, 1)')
        for name in ['create_star_schema.sql', 'refresh_star_schema.sql']:
            connection.execute((ROOT / 'sql/warehouse' / name).read_text(encoding='utf-8'))
        checks = [
            ('orders', 'SELECT COUNT(*) FROM warehouse.fact_orders', 'SELECT COUNT(*) FROM olist.orders'),
            ('items', 'SELECT COUNT(*) FROM warehouse.fact_order_items', 'SELECT COUNT(*) FROM olist.order_items'),
            ('customers', 'SELECT COUNT(*) FROM warehouse.dim_customer', 'SELECT COUNT(DISTINCT customer_unique_id) FROM olist.customers'),
            ('products', 'SELECT COUNT(*) FROM warehouse.dim_product', 'SELECT COUNT(*) FROM olist.products'),
            ('sellers', 'SELECT COUNT(*) FROM warehouse.dim_seller', 'SELECT COUNT(*) FROM olist.sellers'),
            ('item_value', 'SELECT SUM(price) FROM warehouse.fact_order_items', 'SELECT SUM(price) FROM olist.order_items'),
            ('freight', 'SELECT SUM(freight_value) FROM warehouse.fact_order_items', 'SELECT SUM(freight_value) FROM olist.order_items'),
            ('payments', 'SELECT SUM(total_payment) FROM warehouse.fact_orders', 'SELECT SUM(payment_value) FROM olist.order_payments'),
            ('order_item_value', 'SELECT SUM(total_item_value) FROM warehouse.fact_orders', 'SELECT SUM(price) FROM olist.order_items'),
        ]
        rows = []
        for name, actual_query, expected_query in checks:
            actual = connection.execute(actual_query).fetchone()[0]
            expected = connection.execute(expected_query).fetchone()[0]
            if actual != expected:
                raise ValueError(f'Warehouse reconciliation failed for {name}: {actual} != {expected}')
            rows.append({'check': name, 'actual': actual, 'expected': expected, 'passed': True})
    return pd.DataFrame(rows)


if __name__ == '__main__':
    with connect_database() as connection:
        print(refresh_warehouse(connection).to_string(index=False))
