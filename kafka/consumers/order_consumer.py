"""Persist Kafka events to PostgreSQL, committing offsets only after durability."""

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from kafka import KafkaConsumer
from src.database.connection import connect_database
from src.streaming.kafka_client import consume_events
from src.streaming.sink import PostgresEventSink


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bootstrap-servers', default=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', '127.0.0.1:9092'))
    parser.add_argument('--topic', default=os.environ.get('KAFKA_TOPIC', 'olist.orders.v1'))
    parser.add_argument('--group', default=os.environ.get('KAFKA_GROUP_ID', 'olist-postgres-v1'))
    parser.add_argument('--max-messages', type=int)
    parser.add_argument('--idle-timeout', type=float)
    args = parser.parse_args()
    with connect_database() as connection:
        connection.autocommit = True
        sink = PostgresEventSink(connection)
        consumer = KafkaConsumer(args.topic, bootstrap_servers=args.bootstrap_servers, group_id=args.group,
                                 enable_auto_commit=False, auto_offset_reset='earliest')
        print(consume_events(consumer, sink, args.max_messages, args.idle_timeout))


if __name__ == '__main__':
    main()
