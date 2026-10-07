"""Transactional loading of the nine cleaned tables; no pandas-inferred SQL DDL."""

import argparse
import logging
from pathlib import Path

import pandas as pd
from psycopg import sql

from .connection import connect_database
from src.utils.paths import resolve_processed_dir

ROOT = Path(__file__).resolve().parents[2]
LOGGER = logging.getLogger(__name__)
# Parent-before-child order is intentional.
TABLES = {
    'geolocation': 'olist_geolocation_dataset',
    'category_translation': 'product_category_name_translation',
    'customers': 'olist_customers_dataset',
    'products': 'olist_products_dataset',
    'sellers': 'olist_sellers_dataset',
    'orders': 'olist_orders_dataset',
    'order_items': 'olist_order_items_dataset',
    'order_payments': 'olist_order_payments_dataset',
    'order_reviews': 'olist_order_reviews_dataset',
}


def read_cleaned_tables(processed_dir=ROOT / 'data' / 'processed'):
    processed_dir = resolve_processed_dir(processed_dir)
    missing = [name for name in TABLES.values() if not (processed_dir / f'{name}.parquet').is_file()]
    if missing:
        raise FileNotFoundError(f'Missing cleaned Parquet datasets: {missing}')
    return {table: pd.read_parquet(processed_dir / f'{name}.parquet') for table, name in TABLES.items()}


def copy_frame(connection, schema, table, frame):
    """Copy columns explicitly; NULL, leading-zero strings and timestamps survive."""
    statement = sql.SQL('COPY {}.{} ({}) FROM STDIN').format(
        sql.Identifier(schema), sql.Identifier(table),
        sql.SQL(', ').join(map(sql.Identifier, frame.columns)),
    )
    with connection.cursor().copy(statement) as copy:
        for row in frame.itertuples(index=False, name=None):
            copy.write_row(tuple(None if pd.isna(value) else value for value in row))


def load_cleaned_tables(connection, tables, replace=False):
    """Load atomically; reject populated targets unless replacement is explicit.

    Only the fixed olist tables are replaced. Any failed constraint, COPY, or
    reconciliation rolls back the entire refresh, including deletes.
    """
    if set(tables) != set(TABLES):
        raise ValueError(f'Expected exactly these cleaned tables: {list(TABLES)}')
    with connection.transaction():
        # Serialize refreshes, including the initially empty-table case.
        connection.execute("SELECT pg_advisory_xact_lock(746541, 1)")
        connection.execute((ROOT / 'sql/schema/create_tables.sql').read_text(encoding='utf-8'))
        populated = []
        for table in TABLES:
            exists = connection.execute(sql.SQL('SELECT EXISTS (SELECT 1 FROM olist.{})').format(sql.Identifier(table))).fetchone()[0]
            if exists:
                populated.append(table)
        if populated and not replace:
            raise ValueError(f'Target tables contain data: {populated}. Use --replace for an intentional full refresh.')
        if replace:
            for table in reversed(TABLES):
                connection.execute(sql.SQL('DELETE FROM olist.{}').format(sql.Identifier(table)))
        counts = []
        for table in TABLES:
            copy_frame(connection, 'olist', table, tables[table])
            actual = connection.execute(sql.SQL('SELECT COUNT(*) FROM olist.{}').format(sql.Identifier(table))).fetchone()[0]
            if actual != len(tables[table]):
                raise ValueError(f'{table}: expected {len(tables[table])} rows, loaded {actual}')
            counts.append({'table': table, 'rows': actual})
        from .validation import validate_database
        validate_database(connection, tables)
        LOGGER.info('Loaded and reconciled all nine cleaned tables')
    return pd.DataFrame(counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--processed-dir', type=Path, default=ROOT / 'data/processed')
    parser.add_argument('--replace', action='store_true', help='Intentionally replace the nine olist tables in one transaction.')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    try:
        tables = read_cleaned_tables(args.processed_dir)
        with connect_database() as connection:
            counts = load_cleaned_tables(connection, tables, replace=args.replace)
        print(counts.to_string(index=False))
    except Exception as error:
        # Driver exception text can contain connection details; keep logs secret-free.
        LOGGER.error('Database load failed (%s); transaction rolled back.', type(error).__name__)
        raise SystemExit('Database load failed. Check configuration, source schemas and constraints.') from None


if __name__ == '__main__':
    main()
