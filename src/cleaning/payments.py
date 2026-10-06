import pandas as pd
def clean_payments(df: pd.DataFrame) -> pd.DataFrame:
    df=df.copy()
    df["flag_zero_installments"]=df["payment_installments"]<1
    first_sequence = df.groupby("order_id")["payment_sequential"].transform("min")
    df["flag_missing_first_payment"] = first_sequence > 1

    return df
