"""Tests for wbsb.scheduler.auto — scheduler decision logic."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from wbsb.scheduler.auto import MAX_INPUT_BYTES, already_processed, find_latest_input

# ---------------------------------------------------------------------------
# find_latest_input
# ---------------------------------------------------------------------------


def test_find_latest_input_found(tmp_path):
    """Returns the most recently modified matching file."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()

    older = watch_dir / "weekly_data_2026-03-03.csv"
    newer = watch_dir / "weekly_data_2026-03-10.csv"

    older.write_text("data")
    time.sleep(0.01)
    newer.write_text("data")

    result = find_latest_input(watch_dir, "weekly_data_*.csv")

    assert result == newer.resolve()


def test_find_latest_input_no_match(tmp_path):
    """Returns None when files exist but none match the pattern."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    (watch_dir / "report.xlsx").write_text("data")

    result = find_latest_input(watch_dir, "weekly_data_*.csv")

    assert result is None


def test_find_latest_input_empty_dir(tmp_path):
    """Returns None when the watch directory is empty."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()

    result = find_latest_input(watch_dir, "*.csv")

    assert result is None


def test_find_latest_input_path_traversal(tmp_path):
    """Raises ValueError when a matched file resolves outside watch_dir (symlink traversal)."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()

    # Create a file outside the watch directory
    outside = tmp_path / "outside.csv"
    outside.write_text("data")

    # Create a symlink inside watch_dir pointing to the file outside
    symlink = watch_dir / "outside.csv"
    symlink.symlink_to(outside)

    with pytest.raises(ValueError, match="Path traversal detected"):
        find_latest_input(watch_dir, "*.csv")


def test_find_latest_input_oversized_file_skipped(tmp_path):
    """Returns None and logs a warning when the matched file exceeds MAX_INPUT_BYTES."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()

    large_file = watch_dir / "weekly_data_2026-03-10.csv"
    large_file.write_text("data")

    # Patch the file size without writing actual bytes
    original_stat = Path.stat

    def fake_stat(self, *, follow_symlinks=True):
        s = original_stat(self, follow_symlinks=follow_symlinks)
        if self.name == large_file.name:
            # Return a stat-like object with an inflated st_size

            return os.stat_result(
                (
                    s.st_mode,
                    s.st_ino,
                    s.st_dev,
                    s.st_nlink,
                    s.st_uid,
                    s.st_gid,
                    MAX_INPUT_BYTES + 1,  # oversized
                    s.st_atime,
                    s.st_mtime,
                    s.st_ctime,
                )
            )
        return s

    import unittest.mock

    with unittest.mock.patch.object(Path, "stat", fake_stat):
        result = find_latest_input(watch_dir, "*.csv")

    assert result is None


# ---------------------------------------------------------------------------
# already_processed
# ---------------------------------------------------------------------------


def test_already_processed_true(tmp_path):
    """Returns True when the input file is already in the index."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    input_file = watch_dir / "weekly_data_2026-03-10.csv"
    input_file.write_text("data")

    index_path = tmp_path / "index.json"
    entries = [
        {
            "run_id": "20260310T090000Z_abc123",
            "dataset_key": "weekly_data",
            "input_file": str(input_file.resolve()),
            "week_start": "2026-03-09",
            "week_end": "2026-03-15",
            "signal_count": 2,
            "findings_path": str(tmp_path / "findings.json"),
            "registered_at": "2026-03-10T09:00:00Z",
        }
    ]
    index_path.write_text(json.dumps(entries), encoding="utf-8")

    assert already_processed(input_file, index_path) is True


def test_already_processed_false_new_file(tmp_path):
    """Returns False when the input file is not in the index."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    input_file = watch_dir / "weekly_data_2026-03-17.csv"
    input_file.write_text("data")

    index_path = tmp_path / "index.json"
    # Index has a different file for the same dataset
    entries = [
        {
            "run_id": "20260310T090000Z_abc123",
            "dataset_key": "weekly_data",
            "input_file": str((watch_dir / "weekly_data_2026-03-10.csv").resolve()),
            "week_start": "2026-03-09",
            "week_end": "2026-03-15",
            "signal_count": 2,
            "findings_path": str(tmp_path / "findings.json"),
            "registered_at": "2026-03-10T09:00:00Z",
        }
    ]
    index_path.write_text(json.dumps(entries), encoding="utf-8")

    assert already_processed(input_file, index_path) is False


def test_already_processed_index_absent(tmp_path):
    """Returns False when the index file does not exist."""
    input_file = tmp_path / "weekly_data_2026-03-10.csv"
    input_file.write_text("data")
    index_path = tmp_path / "nonexistent_index.json"

    assert already_processed(input_file, index_path) is False
