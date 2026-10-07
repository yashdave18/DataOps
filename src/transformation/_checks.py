"""Input contracts shared by transformations; never change source tables."""

import pandas as pd


def require_columns(frame, columns, name):
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"{name}: missing columns {sorted(missing)}")


def require_key(frame, columns, name):
    require_columns(frame, columns, name)
    if frame[columns].isna().any().any() or frame.duplicated(columns).any():
        raise ValueError(f"{name}: {columns} must be unique and non-null")


def require_references(child, parent, column, name):
    require_columns(child, [column], name)
    invalid = child[column].isna() | ~child[column].isin(parent[column])
    if invalid.any():
        raise ValueError(
            f"{name}: {int(invalid.sum())} missing or unmatched {column} values; "
            "investigate before transforming (no rows were dropped)"
        )


def sum_known(series):
    """Sum observed values while keeping an entirely unknown group null."""
    return series.sum(min_count=1)


def fill_counts(frame, columns):
    for column in columns:
        frame[column] = frame[column].fillna(0).astype('int64')
    return frame


def require_datetimes(frame, columns, name):
    require_columns(frame, columns, name)
    for column in columns:
        if not pd.api.types.is_datetime64_any_dtype(frame[column]):
            raise ValueError(f"{name}.{column}: expected cleaned datetime values")
