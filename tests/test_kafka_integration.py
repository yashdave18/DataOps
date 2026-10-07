import os
import unittest
from uuid import uuid4

from src.streaming.events import make_event
from src.streaming.kafka_client import consume_events, publish_events
from src.streaming.sink import PostgresEventSink

DSN = os.environ.get('OLIST_TEST_DATABASE_URL')
BROKER = os.environ.get('OLIST_TEST_KAFKA_BOOTSTRAP')


@unittest.skipUnless(DSN and BROKER, 'Set dedicated PostgreSQL and Kafka integration endpoints')
class KafkaIntegrationTests(unittest.TestCase):
    def test_replay_deduplication_quarantine_and_committed_offsets(self):
        import psycopg
        from psycopg.conninfo import conninfo_to_dict
        from kafka import KafkaConsumer, KafkaProducer
        from kafka.admin import KafkaAdminClient, NewTopic
        self.assertTrue(conninfo_to_dict(DSN).get('dbname', '').endswith('_test'))
        topic = 'olist.test.' + uuid4().hex
        admin = KafkaAdminClient(bootstrap_servers=BROKER)
        admin.create_topics([NewTopic(topic, num_partitions=3, replication_factor=1)], timeout_ms=30000)
        events = [make_event(topic, 'customer', kind, '2020-01-01')
                  for kind in ['order_created', 'order_approved', 'order_shipped']]
        group = 'group-' + uuid4().hex

        def consumer(group_id):
            return KafkaConsumer(topic, bootstrap_servers=BROKER, group_id=group_id,
                                 enable_auto_commit=False, auto_offset_reset='earliest')

        with psycopg.connect(DSN, autocommit=True) as connection:
            sink = PostgresEventSink(connection)
            try:
                producer = KafkaProducer(bootstrap_servers=BROKER, enable_idempotence=True, acks='all')
                self.assertEqual(publish_events(producer, topic, events + events), 6)
                producer.send(topic, key=b'bad', value=b'{broken').get(timeout=30)
                producer.close(timeout=10)
                self.assertEqual(consume_events(consumer(group), sink, 7, 30),
                                 {'inserted': 3, 'duplicate': 3, 'rejected': 1})
                self.assertEqual(consume_events(consumer(group), sink, 1, 5),
                                 {'inserted': 0, 'duplicate': 0, 'rejected': 0})
                self.assertEqual(consume_events(consumer(group + '-replay'), sink, 7, 30),
                                 {'inserted': 0, 'duplicate': 6, 'rejected': 1})
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM streaming.order_events WHERE order_id=%s', (topic,)).fetchone()[0], 3)
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM streaming.rejected_messages WHERE topic=%s', (topic,)).fetchone()[0], 1)
            finally:
                connection.execute('DELETE FROM streaming.order_events WHERE order_id=%s', (topic,))
                connection.execute('DELETE FROM streaming.rejected_messages WHERE topic=%s', (topic,))
                admin.delete_topics([topic], timeout_ms=30000)
                admin.close()
