import pandas as pd


def clean_order_items(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["shipping_limit_date"] = pd.to_datetime(df["shipping_limit_date"])
    return df