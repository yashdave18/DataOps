"""ONE ROW = ONE UNIQUE CUSTOMER (customer_unique_id, not customer_id)."""

from ._checks import fill_counts, require_columns, require_key, require_references, sum_known


def build_customer_features(orders, customers):
    """Aggregate validated order features, retaining customers with no orders.

    Spend is observed payment value across all statuses, not net revenue.
    No ratings or delivery dates are imputed for unreviewed/undelivered orders.
    """
    require_key(orders, ['order_id'], 'analytical orders')
    require_key(customers, ['customer_id'], 'customers')
    require_columns(customers, ['customer_unique_id'], 'customers')
    require_columns(orders, [
        'customer_unique_id', 'total_payment', 'item_count', 'order_purchase_timestamp',
        'delivery_duration_days', 'review_score', 'payment_count',
    ], 'analytical orders')
    if customers['customer_unique_id'].isna().any():
        raise ValueError('customers.customer_unique_id must be non-null')
    require_references(orders, customers, 'customer_unique_id', 'orders -> unique customers')

    summary = orders.groupby('customer_unique_id', as_index=False).agg(
        order_count=('order_id', 'size'),
        total_spend=('total_payment', sum_known),
        average_order_value=('total_payment', 'mean'),
        total_items_purchased=('item_count', 'sum'),
        first_purchase=('order_purchase_timestamp', 'min'),
        last_purchase=('order_purchase_timestamp', 'max'),
        average_delivery_duration_days=('delivery_duration_days', 'mean'),
        average_review_score=('review_score', 'mean'),
        reviewed_order_count=('review_score', 'count'),
        orders_with_payment=('payment_count', lambda s: (s > 0).sum()),
        orders_with_known_payment=('total_payment', 'count'),
    )
    result = customers[['customer_unique_id']].drop_duplicates().merge(
        summary, on='customer_unique_id', how='left', validate='one_to_one',
    )
    fill_counts(result, [
        'order_count', 'total_items_purchased', 'reviewed_order_count',
        'orders_with_payment', 'orders_with_known_payment',
    ])
    result.loc[result['order_count'] == 0, 'total_spend'] = 0.0
    result['active_period_days'] = (result['last_purchase'] - result['first_purchase']).dt.total_seconds() / 86400
    result['is_repeat_customer'] = result['order_count'] > 1
    return result
