"""Olist-specific expectations, using the reusable quality framework."""

import pandas as pd

from src.validation import data_quality as dq
from src.ingestion.csv_ingestion import expected_datasets

KEYS = {
    'customers': ['customer_id'], 'orders': ['order_id'], 'products': ['product_id'],
    'sellers': ['seller_id'], 'order_items': ['order_id', 'order_item_id'],
    'order_payments': ['order_id', 'payment_sequential'],
}
REQUIRED = {
    'customers': ['customer_id', 'customer_unique_id', 'customer_zip_code_prefix', 'customer_city', 'customer_state'],
    'orders': ['order_id', 'customer_id', 'order_status', 'order_purchase_timestamp', 'order_approved_at',
               'order_delivered_carrier_date', 'order_delivered_customer_date', 'order_estimated_delivery_date'],
    'products': ['product_id', 'product_category_name', 'product_weight_g', 'product_length_cm',
                 'product_height_cm', 'product_width_cm', 'product_photos_qty'],
    'sellers': ['seller_id', 'seller_zip_code_prefix', 'seller_city', 'seller_state'],
    'order_items': ['order_id', 'order_item_id', 'product_id', 'seller_id', 'price', 'freight_value', 'shipping_limit_date'],
    'order_payments': ['order_id', 'payment_sequential', 'payment_type', 'payment_installments', 'payment_value'],
    'order_reviews': ['order_id', 'review_id', 'review_score', 'review_comment_title', 'review_comment_message',
                      'review_creation_date', 'review_answer_timestamp'],
    'geolocation': ['geolocation_zip_code_prefix', 'geolocation_lat', 'geolocation_lng', 'geolocation_city', 'geolocation_state'],
}


def quality_report(tables, cleaned=False):
    missing = expected_datasets - set(tables)
    if missing:
        raise ValueError(f'Missing required datasets: {sorted(missing)}')
    frames = {name: tables[f'olist_{name}_dataset'] for name in REQUIRED}
    frames['translation'] = tables['product_category_name_translation']
    findings = []
    columns = {**REQUIRED, 'translation': ['product_category_name', 'product_category_name_english']}
    for name, frame in frames.items():
        absent = set(columns[name]) - set(frame)
        if absent:
            raise ValueError(f'{name}: missing required columns {sorted(absent)}')
        findings.extend([dq.check_missing_values(frame, name), dq.check_duplicates(frame, name)])
    keys = {**KEYS, 'translation': ['product_category_name']}
    if cleaned:
        keys.update(order_reviews=['order_id'], geolocation=['geolocation_zip_code_prefix'])
    for name, key in keys.items():
        findings.append(dq.check_unique_values(frames[name], name, key))
    for child, parent, key in [
        ('orders', 'customers', 'customer_id'), ('order_items', 'orders', 'order_id'),
        ('order_items', 'products', 'product_id'), ('order_items', 'sellers', 'seller_id'),
        ('order_payments', 'orders', 'order_id'), ('order_reviews', 'orders', 'order_id'),
    ]:
        findings.append(dq.check_referential_integrity(frames[child], frames[parent], child, parent, key))
        if frames[child][key].isna().any():
            findings.append(pd.DataFrame([dq._finding(child, 'null_foreign_key', key,
                frames[child][key].isna().sum(), len(frames[child]), 'error', 'Required relationship is unknown')]))
    for name, column, lower, upper in [
        ('order_items', 'price', 0, None), ('order_items', 'freight_value', 0, None),
        ('order_payments', 'payment_value', 0, None), ('order_reviews', 'review_score', 1, 5),
    ]:
        findings.append(dq.check_value_range(frames[name], name, column, lower, upper))
    for first, second in [('order_approved_at', 'order_delivered_carrier_date'),
                           ('order_delivered_carrier_date', 'order_delivered_customer_date')]:
        finding = dq.check_date_order(frames['orders'], 'orders', first, second)
        finding['severity'] = 'warning'  # Documented anomalies, retained with cleaning flags.
        findings.append(finding)
    if cleaned:
        for name in ['customers', 'sellers', 'geolocation']:
            prefix = {'customers': 'customer', 'sellers': 'seller', 'geolocation': 'geolocation'}[name]
            column = f'{prefix}_zip_code_prefix'
            values = frames[name][column]
            valid = values.map(lambda value: isinstance(value, str) and len(value) == 5 and value.isdigit())
            if not valid.all():
                findings.append(pd.DataFrame([dq._finding(name, 'zip_format', column, (~valid).sum(),
                    len(values), 'error', 'ZIP prefixes must remain five-digit strings')]))
    nonempty = [finding for finding in findings if not finding.empty]
    return pd.concat(nonempty, ignore_index=True)[dq.cols] if nonempty else pd.DataFrame(columns=dq.cols)


def require_quality(report):
    errors = report[report['severity'] == 'error']
    if not errors.empty:
        raise ValueError('Quality gate failed:\n' + errors[['table', 'check', 'column', 'count']].to_string(index=False))
