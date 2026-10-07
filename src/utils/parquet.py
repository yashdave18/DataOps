"""Parquet persistence with exact value, null, and dtype verification."""

from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd


def verify_parquet(frame, path):
    """Verify all columns; row indices are deliberately not part of exports."""
    restored = pd.read_parquet(path)
    pd.testing.assert_frame_equal(
        frame.reset_index(drop=True), restored.reset_index(drop=True),
        check_dtype=True, check_exact=True,
    )
    return restored


def write_verified_parquet(frame, path):
    """Replace a single output only after its temporary file passes verification."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, suffix='.parquet', delete=False) as handle:
        temporary = Path(handle.name)
    try:
        frame.to_parquet(temporary, index=False)
        verify_parquet(frame, temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
