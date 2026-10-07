"""ONE ROW = ONE ORDER. Aggregate children before one-to-one joins."""

import pandas as pd

from ._checks import (
    fill_counts, require_columns, require_datetimes, require_key,
    require_references, sum_known,
)

DATE_COLUMNS = [
    'order_purchase_timestamp', 'order_approved_at',
    'order_delivered_carrier_date', 'order_delivered_customer_date',
    'order_estimated_delivery_date',
]


def build_order_features(orders, order_items, payments, reviews, customers, products):
    """Build all-status order features from cleaned tables without mutating them.

    Reviews must already contain at most one row per order (phase 4 policy).
    Missing child rows have zero counts but unknown monetary/review values.
    """
    require_key(orders, ['order_id'], 'orders')
    require_columns(orders, ['customer_id', 'order_status'], 'orders')
    require_datetimes(orders, DATE_COLUMNS, 'orders')
    require_key(customers, ['customer_id'], 'customers')
    require_columns(customers, ['customer_unique_id'], 'customers')
    if customers['customer_unique_id'].isna().any():
        raise ValueError('customers.customer_unique_id must be non-null')
    require_key(products, ['product_id'], 'products')
    require_columns(products, ['product_category_name'], 'products')
    require_key(order_items, ['order_id', 'order_item_id'], 'order_items')
    require_columns(order_items, ['product_id', 'seller_id', 'price', 'freight_value'], 'order_items')
    require_key(payments, ['order_id', 'payment_sequential'], 'payments')
    require_columns(payments, ['payment_value'], 'payments')
    require_key(reviews, ['order_id'], 'reviews')
    require_columns(reviews, ['review_score', 'has_comment'], 'reviews')
    require_references(orders, customers, 'customer_id', 'orders -> customers')
    for name, child in [('items', order_items), ('payments', payments), ('reviews', reviews)]:
        require_references(child, orders, 'order_id', f'{name} -> orders')
    require_references(order_items, products, 'product_id', 'items -> products')

    # ONE ROW = ONE ITEM; product lookup is many-to-one.
    items = order_items.merge(
        products[['product_id', 'product_category_name']], on='product_id',
        how='left', validate='many_to_one',
    )
    item_summary = items.groupby('order_id', as_index=False).agg(
        total_item_value=('price', sum_known),
        total_freight=('freight_value', sum_known),
        item_count=('order_item_id', 'size'),
        average_item_price=('price', 'mean'),
        product_count=('product_id', 'nunique'),
        seller_count=('seller_id', 'nunique'),
        category_count=('product_category_name', 'nunique'),
        missing_item_price_count=('price', lambda s: s.isna().sum()),
        missing_freight_count=('freight_value', lambda s: s.isna().sum()),
    )
    payment_aggregations = {
        'total_payment': ('payment_value', sum_known),
        'payment_count': ('payment_sequential', 'size'),
        'missing_payment_value_count': ('payment_value', lambda s: s.isna().sum()),
    }
    payment_flags = [c for c in payments if c.startswith('flag_')]
    payment_aggregations.update({c: (c, 'any') for c in payment_flags})
    payment_summary = payments.groupby('order_id', as_index=False).agg(**payment_aggregations)

    result = orders.merge(customers, on='customer_id', how='left', validate='many_to_one')
    for summary in [item_summary, payment_summary, reviews[['order_id', 'review_score', 'has_comment']]]:
        result = result.merge(summary, on='order_id', how='left', validate='one_to_one')
    fill_counts(result, [
        'item_count', 'product_count', 'seller_count', 'category_count', 'payment_count',
        'missing_item_price_count', 'missing_freight_count', 'missing_payment_value_count',
    ])
    result['has_items'] = result['item_count'] > 0
    result['has_payments'] = result['payment_count'] > 0
    result['has_review'] = result['order_id'].isin(reviews['order_id'])
    for column in ['has_comment', *payment_flags]:
        result[column] = result[column].astype('boolean')

    durations = {
        'approval_delay_days': ('order_purchase_timestamp', 'order_approved_at'),
        'shipping_delay_days': ('order_approved_at', 'order_delivered_carrier_date'),
        'delivery_duration_days': ('order_purchase_timestamp', 'order_delivered_customer_date'),
        'carrier_delivery_days': ('order_delivered_carrier_date', 'order_delivered_customer_date'),
    }
    for feature, (start, end) in durations.items():
        result[feature] = (result[end] - result[start]).dt.total_seconds() / 86400
    # Estimates are calendar dates: delivery on the estimated date is on time.
    actual = result['order_delivered_customer_date'].dt.normalize()
    estimate = result['order_estimated_delivery_date'].dt.normalize()
    result['delivery_delay_days'] = (actual - estimate).dt.days
    result['is_late'] = (result['delivery_delay_days'] > 0).astype('boolean')
    result.loc[actual.isna() | estimate.isna(), 'is_late'] = pd.NA
    result['purchase_year'] = result['order_purchase_timestamp'].dt.year.astype('Int64')
    result['purchase_month'] = result['order_purchase_timestamp'].dt.strftime('%Y-%m').astype('string')
    result['purchase_day_of_week'] = result['order_purchase_timestamp'].dt.dayofweek.astype('Int64')
    result['purchase_hour'] = result['order_purchase_timestamp'].dt.hour.astype('Int64')
    result['payment_item_difference'] = result['total_payment'] - result['total_item_value'] - result['total_freight']
    return result
