"""Phase 5 entry point: python -m src.transformation.transformations."""

import argparse
from pathlib import Path

import pandas as pd

from src.utils.parquet import write_verified_parquet
from .order_features import build_order_features
from .customer_features import build_customer_features
from .product_features import build_product_features
from .validation import validate_analytical_datasets

PROCESSED_DIR = Path(__file__).resolve().parents[2] / 'data' / 'processed'
REQUIRED_TABLES = (
    'olist_orders_dataset', 'olist_order_items_dataset', 'olist_order_payments_dataset',
    'olist_order_reviews_dataset', 'olist_customers_dataset', 'olist_products_dataset',
    'product_category_name_translation',
)


def load_processed_tables(processed_dir=PROCESSED_DIR):
    processed_dir = Path(processed_dir)
    missing = [name for name in REQUIRED_TABLES if not (processed_dir / f'{name}.parquet').is_file()]
    if missing:
        raise FileNotFoundError(
            f'Missing processed datasets in {processed_dir}: {missing}. '
            'Run python -m src.cleaning.pipeline first.'
        )
    return {name: pd.read_parquet(processed_dir / f'{name}.parquet') for name in REQUIRED_TABLES}


def build_analytical_datasets(tables):
    """Build and validate all three grains entirely in memory."""
    missing = set(REQUIRED_TABLES) - set(tables)
    if missing:
        raise ValueError(f'Missing processed datasets: {sorted(missing)}')
    orders = build_order_features(
        tables['olist_orders_dataset'], tables['olist_order_items_dataset'],
        tables['olist_order_payments_dataset'], tables['olist_order_reviews_dataset'],
        tables['olist_customers_dataset'], tables['olist_products_dataset'],
    )
    analytical = {
        'orders': orders,
        'customers': build_customer_features(orders, tables['olist_customers_dataset']),
        'products': build_product_features(
            tables['olist_products_dataset'], tables['olist_order_items_dataset'], orders,
            tables['product_category_name_translation'],
        ),
    }
    validate_analytical_datasets(tables, analytical)
    return analytical


def save_analytical_datasets(tables, analytical, output_dir):
    """Revalidate before saving; each Parquet export is verified before replacement."""
    report = validate_analytical_datasets(tables, analytical)
    output_dir = Path(output_dir)
    for name, frame in analytical.items():
        write_verified_parquet(frame, output_dir / f'{name}.parquet')
    report.to_csv(output_dir / 'reconciliation.csv', index=False)
    return report


def run_transformations(processed_dir=PROCESSED_DIR):
    tables = load_processed_tables(processed_dir)
    analytical = build_analytical_datasets(tables)
    report = save_analytical_datasets(tables, analytical, Path(processed_dir) / 'analytical')
    print(report.to_string(index=False))
    for name, frame in analytical.items():
        print(f'{name}: {len(frame):,} rows, {len(frame.columns)} columns; Parquet verified')
    return analytical


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build phase 5 analytical Parquet datasets.')
    parser.add_argument('--processed-dir', type=Path, default=PROCESSED_DIR)
    args = parser.parse_args()
    run_transformations(args.processed_dir)
