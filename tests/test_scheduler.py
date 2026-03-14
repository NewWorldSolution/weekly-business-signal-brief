"""Tests for wbsb.scheduler.auto — scheduler decision logic."""
from __future__ import annotations

import json
import os
import sys
import time
import unittest.mock
from datetime import date, timedelta
from pathlib import Path

import pytest

# Ensure the package is importable when pip install -e . has not been run
# (e.g. fresh worktree checkout without editable reinstall).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from wbsb.scheduler.auto import MAX_INPUT_BYTES, already_processed, find_latest_input


def _this_week() -> str:
    """ISO date of Monday of the current calendar week."""
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


def _last_week() -> str:
    """ISO date of Monday of the previous calendar week."""
    today = date.today()
    return (today - timedelta(days=today.weekday() + 7)).isoformat()


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
    """Raises ValueError when a matched file resolves outside watch_dir."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()

    outside = tmp_path / "outside.csv"
    outside.write_text("data")

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

    original_stat = Path.stat

    def fake_stat(self, *, follow_symlinks=True):
        s = original_stat(self, follow_symlinks=follow_symlinks)
        if self.name == large_file.name:
            return os.stat_result(
                (
                    s.st_mode,
                    s.st_ino,
                    s.st_dev,
                    s.st_nlink,
                    s.st_uid,
                    s.st_gid,
                    MAX_INPUT_BYTES + 1,
                    s.st_atime,
                    s.st_mtime,
                    s.st_ctime,
                )
            )
        return s

    with unittest.mock.patch.object(Path, "stat", fake_stat):
        result = find_latest_input(watch_dir, "*.csv")

    assert result is None


# ---------------------------------------------------------------------------
# already_processed
# ---------------------------------------------------------------------------


def test_already_processed_true(tmp_path):
    """Returns True when the dataset has an entry for the current ISO week."""
    input_file = tmp_path / "weekly_data_2026-03-10.csv"
    input_file.write_text("data")

    index_path = tmp_path / "index.json"
    entries = [
        {
            "run_id": "20260310T090000Z_abc123",
            "dataset_key": "weekly_data",
            "input_file": str(input_file.resolve()),
            "week_start": _this_week(),  # current week → should match
            "week_end": "2026-03-15",
            "signal_count": 2,
            "findings_path": str(tmp_path / "findings.json"),
            "registered_at": "2026-03-10T09:00:00Z",
        }
    ]
    index_path.write_text(json.dumps(entries), encoding="utf-8")

    assert already_processed(input_file, index_path) is True


def test_already_processed_false_new_file(tmp_path):
    """Returns False when the index only contains entries from a previous week."""
    input_file = tmp_path / "weekly_data_2026-03-17.csv"
    input_file.write_text("data")

    index_path = tmp_path / "index.json"
    # Index has last week's entry for the same dataset — current week not yet processed.
    entries = [
        {
            "run_id": "20260310T090000Z_abc123",
            "dataset_key": "weekly_data",
            "input_file": str((tmp_path / "weekly_data_2026-03-10.csv").resolve()),
            "week_start": _last_week(),  # previous week — must not match
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


# ---------------------------------------------------------------------------
# CLI — traversal guard produces a clean skip (no uncaught exception)
# ---------------------------------------------------------------------------


def test_auto_traversal_is_caught_as_skip(tmp_path):
    """A traversal symlink in the watch dir produces exit 0 with a skip message."""
    from typer.testing import CliRunner

    from wbsb.cli import app

    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    outside = tmp_path / "outside.csv"
    outside.write_text("data")
    (watch_dir / "outside.csv").symlink_to(outside)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["run", "--auto", "--watch-dir", str(watch_dir), "--pattern", "*.csv"],
    )

    assert result.exit_code == 0
    assert "skipping" in result.output.lower() or "skipping" in (result.stderr or "").lower()
