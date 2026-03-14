"""No-new-file detection helper for the alert path.

Distinct from auto.py (I9-4), which owns the full auto-run flow.
This module is used by the alerting path to check for new files without
triggering a pipeline run.
"""
from __future__ import annotations

from pathlib import Path

from wbsb.scheduler.auto import find_latest_input


def detect_new_file(watch_dir: Path, pattern: str) -> Path | None:
    """Return the latest matching file in watch_dir, or None if none found.

    Wraps find_latest_input for use in the alerting path.
    Returns None on any error (missing directory, traversal attempt, etc.)
    so callers can always dispatch a no-file alert safely.
    """
    try:
        return find_latest_input(watch_dir, pattern)
    except (ValueError, OSError):
        return None
