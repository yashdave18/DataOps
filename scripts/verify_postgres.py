"""Validate against an isolated PostgreSQL cluster, then stop it.

Requires existing PostgreSQL binaries; never uses or changes a system service.
Run from the repository root with --bin-dir /path/to/postgres/bin.
The cluster and log remain under ignored .local/ for troubleshooting.
"""

import argparse
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile

import psycopg
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.database.loader import load_cleaned_tables, read_cleaned_tables
from src.database.validation import validate_database
from src.database.warehouse import refresh_warehouse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bin-dir', type=Path, required=True)
    parser.add_argument('--kafka-bootstrap', help='Also verify Kafka delivery against this test broker')
    args = parser.parse_args()
    binaries = args.bin_dir.resolve()
    suffix = '.exe' if os.name == 'nt' else ''
    local = ROOT / '.local'
    local.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='pg-validation-', dir=local)).resolve()
    if not directory.is_relative_to(local.resolve()):
        raise ValueError('Unexpected temporary cluster location')
    data_dir = directory / 'data'
    password_file = directory / 'password'
    password = secrets.token_urlsafe(24)
    password_file.write_text(password, encoding='utf-8')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    def run_binary(name, *arguments):
        # A server child can inherit PIPE handles on Windows, preventing EOF
        # after pg_ctl exits. A regular log file avoids waiting on its lifetime.
        log_path = directory / f'{name}.log'
        with log_path.open('w', encoding='utf-8') as output:
            result = subprocess.run(
                [str(binaries / (name + suffix)), *map(str, arguments)],
                stdout=output, stderr=subprocess.STDOUT, text=True,
                startupinfo=startupinfo, timeout=90,
            )
        if result.returncode:
            raise RuntimeError(f'{name} failed: {log_path.read_text(encoding="utf-8")}')

    started = False
    try:
        run_binary('initdb', '-D', data_dir, '-U', 'olist', '--pwfile', password_file, '-A', 'scram-sha-256', '-E', 'UTF8', '--locale=C')
        password_file.unlink()
        run_binary('pg_ctl', '-D', data_dir, '-l', directory / 'postgres.log', '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start')
        started = True
        config = {'host': '127.0.0.1', 'port': port, 'user': 'olist', 'password': password, 'connect_timeout': 10}
        with psycopg.connect(dbname='postgres', autocommit=True, **config) as connection:
            connection.execute('CREATE DATABASE olist_verify')
            connection.execute('CREATE DATABASE olist_integration_test')
        environment = os.environ.copy()
        environment['OLIST_TEST_DATABASE_URL'] = make_conninfo(dbname='olist_integration_test', **config)
        if args.kafka_bootstrap:
            environment['OLIST_TEST_KAFKA_BOOTSTRAP'] = args.kafka_bootstrap
        modules = ['tests.test_database', 'tests.test_streaming_database']
        if args.kafka_bootstrap:
            modules.append('tests.test_kafka_integration')
        subprocess.run([sys.executable, '-m', 'unittest', *modules, '-v'],
                       cwd=ROOT, env=environment, check=True, startupinfo=startupinfo)
        tables = read_cleaned_tables()
        with psycopg.connect(dbname='olist_verify', **config) as connection:
            print(load_cleaned_tables(connection, tables).to_string(index=False), flush=True)
            db_report = validate_database(connection, tables)
            warehouse_report = refresh_warehouse(connection)
            # Ensure the learning-query bundle is executable too.
            connection.execute((ROOT / 'sql/queries/business_queries.sql').read_text(encoding='utf-8'))
        output = ROOT / 'data/processed/reports'
        output.mkdir(parents=True, exist_ok=True)
        db_report.to_csv(output / 'database_validation.csv', index=False)
        warehouse_report.to_csv(output / 'warehouse_validation.csv', index=False)
        print(db_report.to_string(index=False), flush=True)
        print(warehouse_report.to_string(index=False), flush=True)
    finally:
        password_file.unlink(missing_ok=True)
        if started:
            run_binary('pg_ctl', '-D', data_dir, '-m', 'fast', '-w', 'stop')
            print('Isolated PostgreSQL stopped.', flush=True)


if __name__ == '__main__':
    main()
