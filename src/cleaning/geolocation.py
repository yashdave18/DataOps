import pandas as pd

LAT_RANGE = (-33.8, 5.3)
LNG_RANGE = (-73.9, -34.8)


def clean_geolocation(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 1. exact duplicate rows
    df = df.drop_duplicates()

    # 2. zip prefix: integer -> 5-character text
    df["geolocation_zip_code_prefix"] = (
        df["geolocation_zip_code_prefix"].astype(str).str.zfill(5)
    )

    # 3. city: lowercase, trim, remove accents
    df["geolocation_city"] = (
        df["geolocation_city"].str.strip().str.lower()
        .str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii")
    )

    # 4. remove points outside Brazil
    inside = (
        df["geolocation_lat"].between(*LAT_RANGE)
        & df["geolocation_lng"].between(*LNG_RANGE)
    )
    df = df[inside]

    # 5. one row per zip prefix
    df = (
        df.groupby("geolocation_zip_code_prefix", as_index=False)
          .agg(
              geolocation_lat=("geolocation_lat", "median"),
              geolocation_lng=("geolocation_lng", "median"),
              geolocation_city=("geolocation_city", lambda s: s.mode().iat[0]),
              geolocation_state=("geolocation_state", lambda s: s.mode().iat[0]),
          )
    )
    return df