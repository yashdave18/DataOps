import pandas as pd
import pandera.pandas as pa

cols=["table", "check", "column", "count", "percent", "severity", "message"]

def check_missing_values(df:pd.DataFrame, table_name:str, threshold:float=0.0) -> pd.DataFrame:
    counts=df.isnull().sum()
    percents=df.isnull().mean()*100

    rows=[]
    for col in df.columns[percents > threshold]:
        rows.append({
            "table":table_name,
            "check": "missing_values",
            "column": col,
            "count": int(counts[col]),
            "percent": round(percents[col], 2),
            "severity": "warning",
            "message": f"{col}: {counts[col]} missing values ({percents[col]:.2f}%)",
        })

    return pd.DataFrame(rows, columns=cols)

def check_duplicates(df:pd.DataFrame, table_name:str) -> pd.DataFrame:
    counts=df.duplicated().sum()
    percent=df.duplicated().mean()*100

    rows=[]
    if counts > 0:
        rows.append({
            "table":table_name,
            "check": "duplicates",
            "column": "all",
            "count": int(counts),
            "percent": round(percent, 2),
            "severity": "warning",
            "message": f"{counts} duplicate rows ({percent:.2f}%)",
        })

    return pd.DataFrame(rows, columns=cols)

def check_unique_values(df:pd.DataFrame, table_name:str, columns:list[str]) -> pd.DataFrame:
    repeats=df.duplicated(subset=columns)
    counts=int(repeats.sum())
    percents=repeats.mean() * 100

    rows=[]
    null_count = int(df[columns].isna().any(axis=1).sum())
    if null_count:
        rows.append(_finding(table_name, 'null_key', ','.join(columns), null_count,
                             len(df), 'error', f'{null_count} rows have null key components'))
    if counts>0:
        rows.append({
            "table":table_name,
            "check": "unique_values",
            "column": ",".join(columns),
            "count": counts,
            "percent": round(percents, 2),
            "severity": "error",
            "message": f"{', '.join(columns)} is not unique: {counts} repeated rows ({percents:.2f}%)",
        })

    return pd.DataFrame(rows, columns=cols)

def check_data_type(df: pd.DataFrame, table_name: str, column: str,expected_type) -> pd.DataFrame:
    if column not in df:
        return pd.DataFrame([_finding(table_name, 'missing_column', column, len(df),
            len(df), 'error', f'Required column {column} is absent')], columns=cols)
    schema = pa.DataFrameSchema({
        column: pa.Column(expected_type, nullable=True)
    })
    rows = []
    try:
        schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors:
        actual_type = df[column].dtype

        rows.append({
            "table": table_name,
            "check": "data_type",
            "column": column,
            "count": None,
            "percent": None,
            "severity": "error",
            "message": f"{column}: expected {expected_type}, found {actual_type}"
        })

    return pd.DataFrame(rows, columns=cols)

def _finding(table_name, check, column, count, total, severity, message):
    percent = round(count / total * 100, 2) if total else 0.0
    return {
        "table": table_name,
        "check": check,
        "column": column,
        "count": int(count),
        "percent": percent,
        "severity": severity,
        "message": message,
    }


def check_value_range(df: pd.DataFrame, table_name: str, column: str, min_value=None, max_value=None) -> pd.DataFrame:
    """Report values below min_value or above max_value. Nulls are ignored."""
    series = df[column]
    invalid = pd.Series(False, index=df.index)
    if min_value is not None:
        invalid |= series < min_value
    if max_value is not None:
        invalid |= series > max_value

    count = int(invalid.sum())
    rows = []
    if count > 0:
        rows.append(_finding(
            table_name, "invalid_range", column, count, len(df), "error",
            f"{column}: {count} values outside [{min_value}, {max_value}]",
        ))
    return pd.DataFrame(rows, columns=cols)


def check_categorical_values(df: pd.DataFrame, table_name: str, column: str,allowed_values=None) -> pd.DataFrame:
    """Report values not in allowed_values, and spelling variants (case, spaces, accents)."""
    series = df[column].dropna().astype(str)
    rows = []

    if allowed_values is not None:
        invalid = ~series.isin(allowed_values)
        count = int(invalid.sum())
        if count > 0:
            bad = sorted(series[invalid].unique())[:5]
            rows.append(_finding(
                table_name, "invalid_category", column, count, len(df), "error",
                f"{column}: {count} rows with unexpected values, e.g. {bad}",
            ))

    cleaned = (
        series.str.strip().str.lower()
        .str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii")
    )
    spellings = series.groupby(cleaned).nunique()
    inconsistent = spellings[spellings > 1]
    if len(inconsistent) > 0:
        count = int(cleaned.isin(inconsistent.index).sum())
        rows.append(_finding(
            table_name, "inconsistent_category", column, count, len(df), "warning",
            f"{column}: {len(inconsistent)} values have several spellings (case, spaces or accents)",
        ))

    return pd.DataFrame(rows, columns=cols)


def check_date_order(df: pd.DataFrame, table_name: str, earlier_col: str, later_col: str) -> pd.DataFrame:
    """Report rows where later_col is before earlier_col. Rows with a missing date are skipped."""
    earlier = pd.to_datetime(df[earlier_col], errors="coerce")
    later = pd.to_datetime(df[later_col], errors="coerce")
    invalid = later < earlier

    count = int(invalid.sum())
    rows = []
    if count > 0:
        rows.append(_finding(
            table_name, "date_order", f"{earlier_col}, {later_col}", count, len(df), "error",
            f"{later_col} is before {earlier_col} in {count} rows",
        ))
    return pd.DataFrame(rows, columns=cols)


def check_outliers(df: pd.DataFrame, table_name: str, column: str, factor: float = 1.5) -> pd.DataFrame:
    """Report values outside the IQR fences: Q1 - factor*IQR and Q3 + factor*IQR."""
    series = df[column].dropna()
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - factor * iqr, q3 + factor * iqr
    outliers = (series < lower) | (series > upper)

    count = int(outliers.sum())
    rows = []
    if count > 0:
        rows.append(_finding(
            table_name, "outliers", column, count, len(df), "warning",
            f"{column}: {count} values outside [{lower:.2f}, {upper:.2f}]",
        ))
    return pd.DataFrame(rows, columns=cols)


def check_referential_integrity(child_df: pd.DataFrame, parent_df: pd.DataFrame, child_table: str, parent_table: str, child_column: str, parent_column: str | None = None) -> pd.DataFrame:
    """Report child rows whose key value does not exist in the parent table."""
    parent_column = parent_column or child_column
    child_values = child_df[child_column].dropna()
    orphans = ~child_values.isin(parent_df[parent_column])

    count = int(orphans.sum())
    rows = []
    if count > 0:
        rows.append(_finding(
            child_table, "referential_integrity", child_column, count, len(child_df), "error",
            f"{child_table}.{child_column}: {count} values not found in {parent_table}.{parent_column}",
        ))
    return pd.DataFrame(rows, columns=cols)
