"""Compute deltas between current and previous week metrics."""
from __future__ import annotations

from wbsb.utils.math import safe_div


def compute_delta(
    current: float | None, previous: float | None
) -> tuple[float | None, float | None]:
    """Compute absolute and percentage delta.

    Args:
        current: Current week value.
        previous: Previous week value.

    Returns:
        Tuple of (delta_abs, delta_pct). Each may be None if inputs are None.
    """
    if current is None or previous is None:
        return None, None

    delta_abs = current - previous
    delta_pct = safe_div(delta_abs, abs(previous)) if previous != 0 else None
    return delta_abs, delta_pct
