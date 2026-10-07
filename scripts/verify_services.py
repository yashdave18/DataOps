"""Integration checks for a running local/Compose PostgreSQL and optional Kafka."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from psycopg.conninfo import make_conninfo
from src.database.connection import connect_database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-kafka', action='store_true')
    args = parser.parse_args()
    with connect_database() as connection:
        connection.autocommit = True
        if not connection.execute("SELECT 1 FROM pg_database WHERE datname='olist_integration_test'").fetchone():
            connection.execute('CREATE DATABASE olist_integration_test')
    environment = os.environ.copy()
    environment['OLIST_TEST_DATABASE_URL'] = make_conninfo(os.environ.get('DATABASE_URL', ''), dbname='olist_integration_test')
    modules = ['tests.test_database', 'tests.test_streaming_database']
    if args.with_kafka:
        environment['OLIST_TEST_KAFKA_BOOTSTRAP'] = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', '127.0.0.1:9092')
        modules.append('tests.test_kafka_integration')
    subprocess.run([sys.executable, '-m', 'unittest', *modules, '-v'], env=environment, cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
