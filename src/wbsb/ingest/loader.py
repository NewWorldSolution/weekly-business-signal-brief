"""Load CSV or XLSX input data into a DataFrame."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_data(path: Path) -> pd.DataFrame:
    """Load input file (CSV or XLSX) and return a raw DataFrame.

    Args:
        path: Path to the input file.

    Returns:
        DataFrame with raw data.

    Raises:
        ValueError: If file extension is not supported.
        FileNotFoundError: If the file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path, parse_dates=["week_start_date"])
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path, parse_dates=["week_start_date"])
    else:
        raise ValueError(f"Unsupported file type: {suffix!r}. Use .csv or .xlsx")

    # Normalise date column
    df["week_start_date"] = pd.to_datetime(df["week_start_date"]).dt.normalize()
    df = df.sort_values("week_start_date").reset_index(drop=True)
    return df
