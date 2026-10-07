"""Simulate deterministic events from cleaned Parquet and publish to Kafka."""

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd
from kafka import KafkaProducer
from src.streaming.events import simulate_events
from src.streaming.kafka_client import publish_events
from src.utils.paths import resolve_processed_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--processed-dir', type=Path, default=ROOT / 'data/processed')
    parser.add_argument('--limit', type=int, default=1000, help='Number of source orders to simulate')
    parser.add_argument('--bootstrap-servers', default=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', '127.0.0.1:9092'))
    parser.add_argument('--topic', default=os.environ.get('KAFKA_TOPIC', 'olist.orders.v1'))
    args = parser.parse_args()
    processed = resolve_processed_dir(args.processed_dir)
    events = simulate_events(pd.read_parquet(processed / 'olist_orders_dataset.parquet'),
                             pd.read_parquet(processed / 'olist_order_reviews_dataset.parquet'), args.limit)
    producer = KafkaProducer(bootstrap_servers=args.bootstrap_servers, enable_idempotence=True,
                             acks='all', max_block_ms=60000)
    try:
        print(f'Delivered {publish_events(producer, args.topic, events)} events')
    finally:
        producer.close(timeout=10)


if __name__ == '__main__':
    main()
