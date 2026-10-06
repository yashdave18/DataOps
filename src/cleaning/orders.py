import pandas as pd
cols = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]
def clean_orders(df: pd.DataFrame) -> pd.DataFrame:
    df=df.copy()
    for col in cols:
        df[col] = pd.to_datetime(df[col])
        
    df["flag_carrier_before_approval"] = (
        df["order_delivered_carrier_date"] < df["order_approved_at"]
    )

    df["flag_delivery_before_carrier"] = (
        df["order_delivered_customer_date"] < df["order_delivered_carrier_date"]
    )

    delivered = df["order_status"] == "delivered"
    missing_key_date = (
        df["order_approved_at"].isnull()
        | df["order_delivered_carrier_date"].isnull()
        | df["order_delivered_customer_date"].isnull()
    )
    df["flag_delivered_missing_date"] = delivered & missing_key_date
    return df