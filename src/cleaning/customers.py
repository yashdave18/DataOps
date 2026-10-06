import pandas as pd
def clean_customers(df: pd.DataFrame) -> pd.DataFrame:
    df=df.copy()
    df['customer_zip_code_prefix'] = df['customer_zip_code_prefix'].astype(str).str.zfill(5)
    return df