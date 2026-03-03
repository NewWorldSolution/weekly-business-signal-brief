"""Date utilities for ISO week resolution."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd


def week_end_date(week_start: date) -> date:
    """Return the Sunday end date for a week starting on Monday."""
    return week_start + timedelta(days=6)


def resolve_target_week(
    df: pd.DataFrame, target_week: Optional[str]
) -> tuple[date, date]:
    """Resolve current and previous week start dates.

    Args:
        df: DataFrame with 'week_start_date' column.
        target_week: Optional ISO week string like "2024-W47". If None, uses latest.

    Returns:
        Tuple of (current_week_start, previous_week_start).

    Raises:
        ValueError: If target_week not found or no previous week available.
    """
    dates = sorted(df["week_start_date"].dt.date.unique())

    if not dates:
        raise ValueError("No dates found in input data")

    if target_week is None:
        current = dates[-1]
    else:
        # Parse ISO week like "2024-W47"
        parsed = _parse_iso_week(target_week)
        if parsed not in dates:
            raise ValueError(
                f"Target week {target_week!r} ({parsed}) not found in data. "
                f"Available: {dates}"
            )
        current = parsed

    idx = dates.index(current)
    if idx == 0:
        raise ValueError(
            f"No previous week available for {current}. "
            "Need at least 2 rows in the dataset."
        )
    previous = dates[idx - 1]
    return current, previous


def _parse_iso_week(iso_week: str) -> date:
    """Parse ISO week string (YYYY-Www) to the Monday date."""
    import datetime

    # Accepts "2024-W47" or "2024-W47-1"
    parts = iso_week.split("-")
    year = int(parts[0])
    week = int(parts[1].lstrip("W"))
    return datetime.date.fromisocalendar(year, week, 1)
