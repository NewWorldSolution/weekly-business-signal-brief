"""Scheduler decision logic for wbsb run --auto.

This module is a thin decision layer — not a daemon. It answers two questions:
1. Is there a new input file to process?
2. Has it already been processed?

The pipeline is then called normally if the answer is yes/no respectively.
No delivery to Teams/Slack is triggered here — that is handled by I9-5.
"""
from __future__ import annotations

import fnmatch
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_INPUT_BYTES = 100 * 1024 * 1024  # 100 MB


def find_latest_input(watch_dir: Path, pattern: str) -> Path | None:
    """Scan watch_dir for files matching pattern (glob).

    Returns the most recently modified matching file, or None if no match.

    Security:
        Raises ValueError if any matched file resolves outside watch_dir
        (guards against symlink-based path traversal attacks).

    Size guard:
        If the selected file exceeds MAX_INPUT_BYTES, logs a warning and
        returns None to prevent resource exhaustion from oversized inputs.

    Args:
        watch_dir: Directory to scan for input files.
        pattern: Glob pattern to match filenames (e.g. "weekly_data_*.csv").

    Returns:
        Path to the most recently modified matching file, or None.

    Raises:
        ValueError: If a matched file resolves outside watch_dir.
    """
    watch_resolved = watch_dir.resolve()

    if not watch_resolved.is_dir():
        return None

    candidates: list[Path] = []
    for entry in watch_resolved.iterdir():
        if not entry.is_file() and not entry.is_symlink():
            continue
        if not fnmatch.fnmatch(entry.name, pattern):
            continue
        resolved = entry.resolve()
        try:
            resolved.relative_to(watch_resolved)
        except ValueError:
            raise ValueError(
                f"Path traversal detected: {resolved!s} is outside "
                f"watch directory {watch_resolved!s}"
            )
        candidates.append(resolved)

    if not candidates:
        return None

    latest = max(candidates, key=lambda p: p.stat().st_mtime)

    if latest.stat().st_size > MAX_INPUT_BYTES:
        logger.warning(
            "input_file_too_large: skipping — path=%s size=%d",
            latest,
            latest.stat().st_size,
        )
        return None

    return latest


def already_processed(input_path: Path, index_path: Path) -> bool:
    """Check whether input_path has already been processed this cycle.

    Reads runs/index.json (written by I6 pipeline integration) and checks
    whether any entry matches both the dataset key and the resolved input
    file path. Uses derive_dataset_key() for dataset-scoped lookup,
    consistent with the pipeline.

    Returns False if the index file is absent or unreadable.

    Args:
        input_path: Path to the candidate input file.
        index_path: Path to the history index (e.g. runs/index.json).

    Returns:
        True if the file has already been registered in the index.
    """
    from wbsb.history.store import derive_dataset_key

    if not index_path.exists():
        return False

    try:
        entries: list[dict] = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    dataset_key = derive_dataset_key(input_path)
    input_str = str(input_path.resolve())

    for entry in entries:
        if (
            entry.get("dataset_key") == dataset_key
            and entry.get("input_file") == input_str
        ):
            return True

    return False
