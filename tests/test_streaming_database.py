import os
import unittest
from uuid import uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict

from src.streaming.events import make_event
from src.streaming.sink import PostgresEventSink

DSN = os.environ.get('OLIST_TEST_DATABASE_URL')


@unittest.skipUnless(DSN, 'Set OLIST_TEST_DATABASE_URL for durable event tests')
class StreamingDatabaseTests(unittest.TestCase):
    def test_duplicate_events_and_quarantine_are_durable_and_idempotent(self):
        self.assertTrue(conninfo_to_dict(DSN).get('dbname', '').endswith('_test'))
        identifier = 'test-' + uuid4().hex
        event = make_event(identifier, 'customer', 'order_created', '2020-01-01')
        with psycopg.connect(DSN, autocommit=True) as connection:
            sink = PostgresEventSink(connection)
            try:
                self.assertTrue(sink.store(event))
                self.assertFalse(sink.store(event))
                sink.reject(identifier, 0, 1, b'broken', 'invalid')
                sink.reject(identifier, 0, 1, b'broken', 'invalid')
                # A separate connection proves the writes are committed.
                with psycopg.connect(DSN) as reader:
                    self.assertEqual(reader.execute('SELECT COUNT(*) FROM streaming.order_events WHERE event_id=%s', (event['event_id'],)).fetchone()[0], 1)
                    self.assertEqual(reader.execute('SELECT COUNT(*) FROM streaming.rejected_messages WHERE topic=%s', (identifier,)).fetchone()[0], 1)
            finally:
                connection.execute('DELETE FROM streaming.order_events WHERE event_id=%s', (event['event_id'],))
                connection.execute('DELETE FROM streaming.rejected_messages WHERE topic=%s', (identifier,))
