"""Versioned event contract. Source timestamps remain naive/source-local."""

from datetime import datetime
import json
from uuid import NAMESPACE_URL, uuid5

import pandas as pd

EVENT_TIMES = {
    'order_created': 'order_purchase_timestamp', 'order_approved': 'order_approved_at',
    'order_shipped': 'order_delivered_carrier_date', 'order_delivered': 'order_delivered_customer_date',
    'review_submitted': 'review_answer_timestamp',
}
FIELDS = {'schema_version', 'event_id', 'event_type', 'order_id', 'customer_id', 'timestamp', 'timestamp_basis'}


def event_identity(event):
    payload = {key: value for key, value in event.items() if key != 'event_id'}
    return str(uuid5(NAMESPACE_URL, json.dumps(payload, sort_keys=True, separators=(',', ':'))))


def validate_event(event):
    if not isinstance(event, dict) or set(event) != FIELDS:
        raise ValueError('Unexpected event fields')
    if type(event['schema_version']) is not int or event['schema_version'] != 1:
        raise ValueError('Unsupported schema_version')
    if event['event_type'] not in EVENT_TIMES or event['timestamp_basis'] != 'source_local':
        raise ValueError('Unsupported event type or timestamp basis')
    for field in ['order_id', 'customer_id', 'event_id', 'timestamp']:
        if not isinstance(event[field], str) or not event[field] or len(event[field]) > 128:
            raise ValueError(f'Invalid {field}')
    moment = datetime.fromisoformat(event['timestamp'])
    if moment.tzinfo is not None or 'T' not in event['timestamp']:
        raise ValueError('Expected an ISO source-local timestamp without an inferred timezone')
    if event['event_id'] != event_identity(event):
        raise ValueError('event_id does not match the canonical payload')
    return event


def make_event(order_id, customer_id, event_type, timestamp):
    event = {'schema_version': 1, 'order_id': order_id, 'customer_id': customer_id,
             'event_type': event_type, 'timestamp': pd.Timestamp(timestamp).isoformat(),
             'timestamp_basis': 'source_local'}
    event['event_id'] = event_identity(event)
    return validate_event(event)


def simulate_events(orders, reviews, limit=None):
    """Replay observed source dates; no made-up payment completion timestamps."""
    if not orders.order_id.is_unique or not reviews.order_id.is_unique:
        raise ValueError('Simulation requires cleaned unique order and review grains')
    selected = orders.sort_values(['order_purchase_timestamp', 'order_id'])
    if limit is not None:
        if limit < 1:
            raise ValueError('limit must be positive')
        selected = selected.head(limit)
    selected = selected.merge(reviews[['order_id', 'review_answer_timestamp']], on='order_id', how='left', validate='one_to_one')
    events = []
    for row in selected.to_dict('records'):
        for kind, column in EVENT_TIMES.items():
            if pd.notna(row[column]):
                events.append(make_event(row['order_id'], row['customer_id'], kind, row[column]))
    # Timestamp ordering preserves recorded anomalies rather than repairing them.
    return sorted(events, key=lambda event: (event['timestamp'], event['order_id'], event['event_type']))
