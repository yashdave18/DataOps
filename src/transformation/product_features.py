"""ONE ROW = ONE PRODUCT. Sales and review aggregates are joined separately."""

from ._checks import fill_counts, require_columns, require_key, require_references, sum_known


def build_product_features(products, order_items, orders, category_translation):
    """Retain all products; one order contributes at most one rating per product.

    Revenue is gross item price across all order statuses, excluding freight.
    An order review describes the whole order, not an individual product.
    """
    require_key(products, ['product_id'], 'products')
    require_columns(products, ['product_category_name'], 'products')
    require_key(order_items, ['order_id', 'order_item_id'], 'order_items')
    require_columns(order_items, ['product_id', 'seller_id', 'price', 'freight_value'], 'order_items')
    require_key(orders, ['order_id'], 'analytical orders')
    require_columns(orders, ['customer_unique_id', 'review_score'], 'analytical orders')
    require_key(category_translation, ['product_category_name'], 'category_translation')
    require_columns(category_translation, ['product_category_name_english'], 'category_translation')
    require_references(order_items, products, 'product_id', 'items -> products')
    require_references(order_items, orders, 'order_id', 'items -> orders')

    # ONE ROW = ONE ITEM; no payment or review child tables are joined here.
    items = order_items.merge(
        orders[['order_id', 'customer_unique_id']], on='order_id',
        how='left', validate='many_to_one',
    )
    sales = items.groupby('product_id', as_index=False).agg(
        units_sold=('order_item_id', 'size'),
        order_count=('order_id', 'nunique'),
        customer_count=('customer_unique_id', 'nunique'),
        revenue=('price', sum_known),
        total_freight=('freight_value', sum_known),
        average_selling_price=('price', 'mean'),
        average_freight=('freight_value', 'mean'),
        seller_count=('seller_id', 'nunique'),
        missing_price_count=('price', lambda s: s.isna().sum()),
        missing_freight_count=('freight_value', lambda s: s.isna().sum()),
    )
    # ONE ROW = ONE PRODUCT / ORDER, so repeated units cannot weight ratings.
    product_orders = order_items[['product_id', 'order_id']].drop_duplicates().merge(
        orders[['order_id', 'review_score']], on='order_id', how='left', validate='many_to_one',
    )
    ratings = product_orders.groupby('product_id', as_index=False).agg(
        average_review_score=('review_score', 'mean'),
        review_count=('review_score', 'count'),
    )
    result = products.merge(
        category_translation, on='product_category_name', how='left', validate='many_to_one',
    )
    result['flag_missing_category_translation'] = result['product_category_name_english'].isna()
    for summary in [sales, ratings]:
        result = result.merge(summary, on='product_id', how='left', validate='one_to_one')
    fill_counts(result, [
        'units_sold', 'order_count', 'customer_count', 'seller_count', 'review_count',
        'missing_price_count', 'missing_freight_count',
    ])
    result.loc[result['units_sold'] == 0, ['revenue', 'total_freight']] = 0.0
    return result
