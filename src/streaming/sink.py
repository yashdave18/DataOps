"""Durable event insertion before Kafka offset acknowledgement."""

from datetime import datetime
from pathlib import Path

from psycopg.types.json import Jsonb

from .events import validate_event

ROOT = Path(__file__).resolve().parents[2]


class PostgresEventSink:
    def __init__(self, connection):
        if not connection.autocommit:
            raise ValueError('The streaming sink requires autocommit so each explicit transaction commits before Kafka acknowledgement')
        self.connection = connection
        connection.execute((ROOT / 'sql/schema/streaming.sql').read_text(encoding='utf-8'))

    def store(self, event):
        validate_event(event)
        with self.connection.transaction():
            result = self.connection.execute('''
                INSERT INTO streaming.order_events
                    (event_id, schema_version, event_type, order_id, customer_id, occurred_at, payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO NOTHING RETURNING event_id
            ''', (event['event_id'], event['schema_version'], event['event_type'], event['order_id'],
                  event['customer_id'], datetime.fromisoformat(event['timestamp']), Jsonb(event)))
            return result.fetchone() is not None

    def reject(self, topic, partition, offset, payload, reason):
        with self.connection.transaction():
            self.connection.execute('''
                INSERT INTO streaming.rejected_messages (topic, partition_id, offset_id, payload, reason)
                VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
            ''', (topic, partition, offset, payload, reason[:1000]))
