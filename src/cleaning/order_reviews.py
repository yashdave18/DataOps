import pandas as pd


def clean_order_reviews(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 1. dates: text -> datetime
    for col in ["review_creation_date", "review_answer_timestamp"]:
        df[col] = pd.to_datetime(df[col])

    # 2. True if the review has any comment text
    df["has_comment"] = df["review_comment_title"].notnull() | df["review_comment_message"].notnull()

    # 3. keep only the latest review per order
    df = (
        df.sort_values(["order_id", "review_answer_timestamp", "review_id"])
          .drop_duplicates(subset="order_id", keep="last")
          .sort_index()
    )
    return df