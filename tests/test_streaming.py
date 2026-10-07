import json
import unittest
from unittest.mock import Mock
from types import SimpleNamespace

from src.streaming.events import make_event, simulate_events, validate_event
from src.streaming.kafka_client import process_message, publish_events
from tests.database_fixtures import cleaned_tables


def message_for(event, key=b'o1', offset=1):
    return SimpleNamespace(value=json.dumps(event).encode(), key=key, topic='test', partition=0, offset=offset)


class StreamingTests(unittest.TestCase):
    def setUp(self):
        self.event = make_event('o1', 'c1', 'order_created', '2020-01-01')

    def test_replays_have_stable_ids_and_do_not_invent_unknown_timestamps(self):
        tables = cleaned_tables()
        events = simulate_events(tables['orders'], tables['order_reviews'])
        self.assertEqual(events, simulate_events(tables['orders'], tables['order_reviews']))
        self.assertEqual(len(events), len({e['event_id'] for e in events}))
        self.assertEqual([e['event_type'] for e in events if e['order_id'] == 'o3'], ['order_created'])
        self.assertTrue(all(e['timestamp_basis'] == 'source_local' for e in events))

    def test_invalid_schema_and_payload_changes_are_rejected(self):
        for altered in [{**self.event, 'schema_version': True}, {**self.event, 'order_id': 'changed'},
                        {**self.event, 'event_type': 'unknown'}, {**self.event, 'timestamp': '2020-01-01T00:00:00Z'}]:
            with self.assertRaises(ValueError):
                validate_event(altered)

    def test_durable_insert_precedes_offset_commit(self):
        actions = []
        sink = Mock(store=Mock(side_effect=lambda event: actions.append('stored') or True))
        consumer = Mock(commit=Mock(side_effect=lambda **kw: actions.append('committed')))
        self.assertEqual(process_message(message_for(self.event), consumer, sink), 'inserted')
        self.assertEqual(actions, ['stored', 'committed'])
        sink.store.side_effect = OSError('database unavailable')
        consumer.reset_mock()
        with self.assertRaises(OSError):
            process_message(message_for(self.event), consumer, sink)
        consumer.commit.assert_not_called()

    def test_commit_failure_replays_safely_and_duplicates_are_acknowledged(self):
        sink = Mock(store=Mock(side_effect=[True, False]))
        consumer = Mock(commit=Mock(side_effect=[RuntimeError('offset failure'), None]))
        with self.assertRaises(RuntimeError):
            process_message(message_for(self.event), consumer, sink)
        self.assertEqual(process_message(message_for(self.event), consumer, sink), 'duplicate')

    def test_invalid_messages_are_quarantined_before_commit(self):
        sink, consumer = Mock(), Mock()
        self.assertEqual(process_message(message_for(self.event, key=b'wrong'), consumer, sink), 'rejected')
        sink.reject.assert_called_once()
        sink.store.assert_not_called()
        consumer.commit.assert_called_once()
        sink.reject.side_effect = OSError('quarantine failed')
        consumer.reset_mock()
        with self.assertRaises(OSError):
            process_message(message_for(self.event, key=b'wrong'), consumer, sink)
        consumer.commit.assert_not_called()

    def test_producer_does_not_report_success_without_acknowledgements(self):
        producer = Mock()
        producer.send.return_value.get.side_effect = TimeoutError('No broker acknowledgement')
        with self.assertRaises(TimeoutError):
            publish_events(producer, 'test', [self.event])
        producer.send.return_value.get.side_effect = None
        self.assertEqual(publish_events(producer, 'test', [self.event]), 1)
