"""Pandas business metrics shared by the notebook, SQL checks and dashboard.

All functions operate on a caller-selected population. Missing monetary values
remain unknown; rates use observed denominators. No input frames are modified.
"""

import pandas as pd


def select_orders(orders, statuses=None, start=None, end=None):
    mask = pd.Series(True, index=orders.index)
    if statuses is not None:
        mask &= orders['order_status'].isin(statuses)
    dates = orders['order_purchase_timestamp'].dt.normalize()
    if start is not None:
        mask &= dates >= pd.Timestamp(start).normalize()
    if end is not None:
        mask &= dates <= pd.Timestamp(end).normalize()
    return orders.loc[mask].copy()


def overview(orders):
    customer_counts = orders.groupby('customer_unique_id').size()
    return pd.DataFrame([{
        'order_count': len(orders),
        'customer_count': orders['customer_unique_id'].nunique(),
        'item_revenue': orders['total_item_value'].sum(min_count=1),
        'freight': orders['total_freight'].sum(min_count=1),
        'payments': orders['total_payment'].sum(min_count=1),
        'average_order_value': orders['total_payment'].mean(),
        'known_payment_orders': orders['total_payment'].count(),
        'average_review_score': orders['review_score'].mean(),
        'reviewed_orders': orders['review_score'].count(),
        'late_delivery_rate': orders['is_late'].mean(),
        'known_delivery_outcomes': orders['is_late'].count(),
        'repeat_customer_rate': (customer_counts > 1).mean(),
    }])


def monthly_sales(orders):
    frame = orders.assign(month=orders['order_purchase_timestamp'].dt.to_period('M').dt.to_timestamp())
    grouped = frame.groupby('month')
    result = grouped.agg(
        order_count=('order_id', 'size'), customer_count=('customer_unique_id', 'nunique'),
        average_order_value=('total_payment', 'mean'), reviewed_orders=('review_score', 'count'),
        average_review_score=('review_score', 'mean'),
    )
    result[['item_revenue', 'freight', 'payments']] = grouped[
        ['total_item_value', 'total_freight', 'total_payment']
    ].sum(min_count=1).rename(columns={
        'total_item_value': 'item_revenue', 'total_freight': 'freight', 'total_payment': 'payments',
    })
    result['order_growth_rate'] = result['order_count'].pct_change(fill_method=None)
    result['running_item_revenue'] = result['item_revenue'].cumsum().ffill()
    return result.reset_index()


def enriched_items(orders, items, products):
    """ONE ROW = ONE ITEM within the selected orders; both joins many-to-one."""
    selected = items.loc[items['order_id'].isin(orders['order_id'])].copy()
    selected = selected.merge(
        orders[['order_id', 'customer_unique_id', 'review_score', 'delivery_duration_days', 'is_late']],
        on='order_id', how='left', validate='many_to_one',
    ).merge(
        products[['product_id', 'product_category_name', 'product_category_name_english']],
        on='product_id', how='left', validate='many_to_one',
    )
    selected['category'] = selected['product_category_name_english'].fillna(selected['product_category_name']).fillna('unknown')
    return selected


def category_sales(orders, items, products):
    frame = enriched_items(orders, items, products)
    grouped = frame.groupby('category')
    result = grouped.agg(units=('order_item_id', 'size'), order_count=('order_id', 'nunique'))
    result['item_revenue'] = grouped['price'].sum(min_count=1)
    result['freight'] = grouped['freight_value'].sum(min_count=1)
    ratings = frame.drop_duplicates(['category', 'order_id']).groupby('category').agg(
        average_review_score=('review_score', 'mean'), reviewed_orders=('review_score', 'count'),
    )
    return result.join(ratings).reset_index().sort_values(['item_revenue', 'category'], ascending=[False, True])


def product_sales(orders, items, products):
    frame = enriched_items(orders, items, products)
    grouped = frame.groupby('product_id')
    result = grouped.agg(
        units=('order_item_id', 'size'), order_count=('order_id', 'nunique'),
        category=('category', 'first'), average_price=('price', 'mean'),
    )
    result['item_revenue'] = grouped['price'].sum(min_count=1)
    ratings = frame.drop_duplicates(['product_id', 'order_id']).groupby('product_id').agg(
        average_review_score=('review_score', 'mean'), reviewed_orders=('review_score', 'count'),
    )
    return result.join(ratings).reset_index().sort_values(['units', 'product_id'], ascending=[False, True])


def seller_performance(orders, items, sellers):
    frame = items[items['order_id'].isin(orders['order_id'])].merge(
        orders[['order_id', 'review_score', 'delivery_duration_days', 'is_late']],
        on='order_id', how='left', validate='many_to_one',
    )
    grouped = frame.groupby('seller_id')
    result = grouped.agg(units=('order_item_id', 'size'))
    result['item_revenue'] = grouped['price'].sum(min_count=1)
    result['freight'] = grouped['freight_value'].sum(min_count=1)
    deliveries = frame.drop_duplicates(['seller_id', 'order_id']).groupby('seller_id').agg(
        order_count=('order_id', 'size'),
        average_delivery_days=('delivery_duration_days', 'mean'),
        late_delivery_rate=('is_late', 'mean'), known_delivery_outcomes=('is_late', 'count'),
        average_review_score=('review_score', 'mean'),
    )
    return result.join(deliveries).reset_index().merge(
        sellers[['seller_id', 'seller_city', 'seller_state']], on='seller_id', how='left', validate='one_to_one',
    ).sort_values(['item_revenue', 'seller_id'], ascending=[False, True])


def customer_activity(orders):
    frame = orders[['order_id', 'customer_unique_id', 'order_purchase_timestamp']].copy()
    frame['month'] = frame['order_purchase_timestamp'].dt.to_period('M').dt.to_timestamp()
    frame['first_month'] = frame.groupby('customer_unique_id')['month'].transform('min')
    frame = frame.drop_duplicates(['month', 'customer_unique_id'])
    frame['new_customer'] = frame['month'] == frame['first_month']
    result = frame.groupby('month').agg(customers=('customer_unique_id', 'size'), new_customers=('new_customer', 'sum'))
    result['returning_customers'] = result['customers'] - result['new_customers']
    return result.reset_index()


def customer_cohorts(orders):
    """ONE ROW = ONE COHORT / OBSERVABLE MONTH OFFSET; future cells are absent."""
    frame = orders[['customer_unique_id', 'order_purchase_timestamp']].dropna().copy()
    columns = ['cohort_month', 'month_offset', 'customers', 'cohort_size', 'retention_rate']
    if frame.empty:
        return pd.DataFrame(columns=columns)
    frame['month'] = frame['order_purchase_timestamp'].dt.to_period('M')
    frame['cohort'] = frame.groupby('customer_unique_id')['month'].transform('min')
    frame = frame.drop_duplicates(['customer_unique_id', 'month'])
    sizes = frame.groupby('cohort')['customer_unique_id'].nunique()
    active = frame.groupby(['cohort', 'month'])['customer_unique_id'].nunique()
    last_month = frame['month'].max()
    rows = []
    for cohort, size in sizes.items():
        for offset, month in enumerate(pd.period_range(cohort, last_month, freq='M')):
            count = int(active.get((cohort, month), 0))
            rows.append((cohort.to_timestamp(), offset, count, int(size), count / size))
    return pd.DataFrame(rows, columns=columns)


def customer_rfm(orders, as_of=None):
    """Unscored RFM using a reproducible snapshot date, never the wall clock."""
    grouped = orders.groupby('customer_unique_id')
    result = grouped.agg(frequency=('order_id', 'size'), last_purchase=('order_purchase_timestamp', 'max'))
    result['monetary'] = grouped['total_payment'].sum(min_count=1)
    if orders.empty:
        result['recency_days'] = pd.Series(dtype='int64')
    else:
        last = orders['order_purchase_timestamp'].max().normalize()
        reference = pd.Timestamp(as_of).normalize() if as_of is not None else last + pd.Timedelta(days=1)
        if reference < last:
            raise ValueError('as_of must be on or after the last purchase date')
        result['recency_days'] = (reference - result['last_purchase'].dt.normalize()).dt.days
    return result.reset_index()


def geography_performance(orders):
    grouped = orders.groupby('customer_state', dropna=False)
    result = grouped.agg(
        order_count=('order_id', 'size'), customer_count=('customer_unique_id', 'nunique'),
        average_delivery_days=('delivery_duration_days', 'mean'), late_delivery_rate=('is_late', 'mean'),
        known_delivery_outcomes=('is_late', 'count'), average_review_score=('review_score', 'mean'),
    )
    result['item_revenue'] = grouped['total_item_value'].sum(min_count=1)
    result['freight'] = grouped['total_freight'].sum(min_count=1)
    return result.reset_index()


def review_delivery(orders):
    frame = orders.copy()
    frame['delivery_outcome'] = frame['is_late'].map({True: 'late', False: 'on_time'}).fillna('unknown')
    return frame.groupby('delivery_outcome', as_index=False).agg(
        order_count=('order_id', 'size'), reviewed_orders=('review_score', 'count'),
        average_review_score=('review_score', 'mean'),
        commented_reviews=('has_comment', 'sum'), known_comment_indicators=('has_comment', 'count'),
    )
