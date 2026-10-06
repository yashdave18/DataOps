import pandas as pd


def clean_sellers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 1. zip prefix: integer -> 5-character text (restores leading zeros)
    df["seller_zip_code_prefix"] = df["seller_zip_code_prefix"].astype(str).str.zfill(5)

    # 2. city: lowercase, trim spaces, remove accents
    df["seller_city"] = (
        df["seller_city"].str.strip().str.lower()
        .str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii")
    )

    return df