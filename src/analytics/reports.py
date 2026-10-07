"""Produce dashboard-ready CSV reports from validated analytical exports."""

import argparse
from pathlib import Path

import pandas as pd

from . import metrics
from src.utils.paths import resolve_processed_dir

ROOT = Path(__file__).resolve().parents[2]


def load_data(processed_dir=ROOT / 'data/processed'):
    directory = resolve_processed_dir(processed_dir)
    paths = {
        'orders': directory / 'analytical/orders.parquet',
        'products': directory / 'analytical/products.parquet',
        'items': directory / 'olist_order_items_dataset.parquet',
        'sellers': directory / 'olist_sellers_dataset.parquet',
    }
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(f'Missing {path}. Run python -m src.transformation.transformations first.')
    return {name: pd.read_parquet(path) for name, path in paths.items()}


def build_reports(data, statuses=None, start=None, end=None):
    orders = metrics.select_orders(data['orders'], statuses, start, end)
    return {
        'overview': metrics.overview(orders),
        'monthly_sales': metrics.monthly_sales(orders),
        'category_sales': metrics.category_sales(orders, data['items'], data['products']),
        'product_sales': metrics.product_sales(orders, data['items'], data['products']),
        'seller_performance': metrics.seller_performance(orders, data['items'], data['sellers']),
        'customer_activity': metrics.customer_activity(orders),
        'customer_cohorts': metrics.customer_cohorts(orders),
        'customer_rfm': metrics.customer_rfm(orders),
        'geography': metrics.geography_performance(orders),
        'review_delivery': metrics.review_delivery(orders),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--processed-dir', type=Path, default=ROOT / 'data/processed')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'data/processed/reports')
    parser.add_argument('--status', action='append', help='Repeat to include several statuses; default is all statuses.')
    args = parser.parse_args()
    reports = build_reports(load_data(args.processed_dir), statuses=args.status)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in reports.items():
        frame.to_csv(args.output_dir / f'{name}.csv', index=False)
        print(f'{name}: {len(frame):,} rows')
    print(reports['overview'].to_string(index=False))


if __name__ == '__main__':
    main()
