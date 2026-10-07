"""PostgreSQL connections from environment variables; never log credentials."""

import os

import psycopg


def connect_database(dsn=None):
    """Return a transaction-capable connection; caller owns its context/lifetime.

    DATABASE_URL takes precedence over PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD.
    libpq handles the PG* environment variables, including password files.
    """
    dsn = dsn or os.environ.get('DATABASE_URL')
    if not dsn and not os.environ.get('PGDATABASE'):
        raise ValueError('Set DATABASE_URL or PGDATABASE and the appropriate PG* connection variables.')
    return psycopg.connect(dsn or '', connect_timeout=10, application_name='olist_pipeline')
