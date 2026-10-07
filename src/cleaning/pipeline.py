"""Reproduce phase 4 from untouched raw CSVs: python -m src.cleaning.pipeline."""

from pathlib import Path

from src.ingestion.csv_ingestion import load_datasets
from src.utils.parquet import write_verified_parquet
from .category_translation import clean_category_translation
from .customers import clean_customers
from .geolocation import clean_geolocation
from .order_items import clean_order_items
from .order_reviews import clean_order_reviews
from .orders import clean_orders
from .payments import clean_payments
from .products import clean_products
from .sellers import clean_sellers

CLEANERS = {
    'olist_customers_dataset': clean_customers,
    'olist_geolocation_dataset': clean_geolocation,
    'olist_order_items_dataset': clean_order_items,
    'olist_order_payments_dataset': clean_payments,
    'olist_order_reviews_dataset': clean_order_reviews,
    'olist_orders_dataset': clean_orders,
    'olist_products_dataset': clean_products,
    'olist_sellers_dataset': clean_sellers,
    'product_category_name_translation': clean_category_translation,
}
PROCESSED_DIR = Path(__file__).resolve().parents[2] / 'data' / 'processed'


def clean_datasets(datasets):
    missing = set(CLEANERS) - set(datasets)
    if missing:
        raise ValueError(f'Missing raw datasets: {sorted(missing)}')
    return {name: cleaner(datasets[name]) for name, cleaner in CLEANERS.items()}


def run_cleaning():
    cleaned = clean_datasets(load_datasets())
    for name, frame in cleaned.items():
        write_verified_parquet(frame, PROCESSED_DIR / f'{name}.parquet')
        print(f'{name}: {len(frame):,} rows; Parquet round trip verified')
    return cleaned


if __name__ == '__main__':
    run_cleaning()
