import pandas as pd


def clean_products(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 1. fix the misspelled column names
    df = df.rename(columns={
        "product_name_lenght": "product_name_length",
        "product_description_lenght": "product_description_length",
    })

    # 2. mark zero weights BEFORE changing them, or the information is lost
    df["flag_zero_weight"] = df["product_weight_g"] == 0

    # 3. a weight of 0 g is impossible, so set it to unknown (null)
    df.loc[df["flag_zero_weight"], "product_weight_g"] = float("nan")

    # 4. products with no category get their own visible group
    df["product_category_name"] = df["product_category_name"].fillna("unknown")

    return df