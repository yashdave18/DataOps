"""Kafka transport with bounded producer delivery and explicit consumer commits."""

import json
import time

from .events import validate_event


def publish_events(producer, topic, events, timeout=60):
    delivered = 0
    for event in events:
        validate_event(event)
        future = producer.send(topic, key=event['order_id'].encode(),
                               value=json.dumps(event, sort_keys=True).encode())
        future.get(timeout=timeout)  # Broker acknowledgement, not just local enqueue.
        delivered += 1
    producer.flush(timeout=timeout)
    return delivered


def process_message(message, consumer, sink):
    """Persist accepted/rejected input, then acknowledge; failures remain replayable."""
    try:
        event = validate_event(json.loads(message.value))
        if message.key != event['order_id'].encode():
            raise ValueError('Kafka key does not match order_id')
    except (ValueError, TypeError, UnicodeDecodeError) as error:
        sink.reject(message.topic, message.partition, message.offset, message.value, str(error))
        outcome = 'rejected'
    else:
        outcome = 'inserted' if sink.store(event) else 'duplicate'
    # Synchronous commit after database durability. Crash between these steps
    # replays the event; the deterministic event_id makes its insertion idempotent.
    from kafka.structs import TopicPartition, OffsetAndMetadata
    consumer.commit(offsets={TopicPartition(message.topic, message.partition):
                             OffsetAndMetadata(message.offset + 1, '', -1)})
    return outcome


def consume_events(consumer, sink, max_messages=None, idle_timeout=None):
    counts = {'inserted': 0, 'duplicate': 0, 'rejected': 0}
    last_message = time.monotonic()
    try:
        while max_messages is None or sum(counts.values()) < max_messages:
            batches = consumer.poll(timeout_ms=1000, max_records=100)
            if not batches:
                if idle_timeout is not None and time.monotonic() - last_message >= idle_timeout:
                    break
                continue
            last_message = time.monotonic()
            for messages in batches.values():
                for message in messages:
                    if max_messages is not None and sum(counts.values()) >= max_messages:
                        return counts
                    counts[process_message(message, consumer, sink)] += 1
        return counts
    finally:
        consumer.close(autocommit=False)
