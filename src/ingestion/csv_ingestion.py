import pandas as pd
from pathlib import Path
raw_directory=Path(__file__).resolve().parents[2]/"data"/"raw"
expected_datasets={
    "olist_customers_dataset",
    "olist_geolocation_dataset",
    "olist_order_items_dataset",
    "olist_order_payments_dataset", 
    "olist_order_reviews_dataset",
    "olist_orders_dataset",
    "olist_products_dataset",
    "olist_sellers_dataset",
    "product_category_name_translation"
}

def load_datasets():
    '''
    Function to load all CSV files from the raw data directory into a dictionary of pandas DataFrames
    '''

    if not raw_directory.exists():
        # raise a FileNotFoundError if the raw data directory does not exist
        raise FileNotFoundError(f"Raw data directory not found: {raw_directory}")
    
    datasets={}
    failed={}
    for file in raw_directory.glob("*.csv"):
        dataset_name=file.stem
        try:
            datasets[dataset_name]=pd.read_csv(file)
        except (
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
            UnicodeDecodeError,
            PermissionError,
            ) as e:
            failed[dataset_name]=str(e)

    if not datasets and not failed:
        raise FileNotFoundError(f"No CSV files found in the raw data directory: {raw_directory}")

    missing=expected_datasets-set(datasets.keys())
    if missing:
        message = f"Missing datasets: {sorted(missing)}."
        if failed:
            details = "; ".join(f"{name}: {reason}" for name, reason in failed.items())
            message += f" Failed to load: {details}"
        raise ValueError(message)
    return datasets

if __name__=="__main__":
    datasets=load_datasets()
    for name, df in datasets.items():
        print(f"Dataset: {name}, Shape: {df.shape}")