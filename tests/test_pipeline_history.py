"""Integration tests — pipeline history registration (I6-3).

Verifies that pipeline.execute() registers completed runs in the history
index and that failed runs do not produce index entries.
"""
from __future__ import annotations

import json
from pathlib import Path

from wbsb.history.store import derive_dataset_key
from wbsb.pipeline import execute

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

CLEAN_DATASET = Path("examples/datasets/dataset_01_clean_baseline.csv")
CONFIG_PATH = Path("config/rules.yaml")


def _run(tmp_path: Path, input_path: Path = CLEAN_DATASET) -> tuple[int, Path]:
    """Run the pipeline and return (exit_code, index_path)."""
    exit_code = execute(
        input_path=input_path,
        output_dir=tmp_path,
        llm_mode="off",
        llm_provider="anthropic",
        config_path=CONFIG_PATH,
        target_week=None,
    )
    return exit_code, tmp_path / "index.json"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_pipeline_creates_index_after_successful_run(tmp_path):
    exit_code, index_path = _run(tmp_path)

    assert exit_code == 0
    assert index_path.exists(), "index.json must be created after a successful run"

    entries = json.loads(index_path.read_text())
    assert len(entries) == 1


def test_pipeline_index_entry_has_all_required_fields(tmp_path):
    exit_code, index_path = _run(tmp_path)
    assert exit_code == 0

    entry = json.loads(index_path.read_text())[0]
    required_fields = {
        "run_id",
        "dataset_key",
        "input_file",
        "week_start",
        "week_end",
        "signal_count",
        "findings_path",
        "registered_at",
    }
    assert required_fields == set(entry.keys()), (
        f"Missing fields: {required_fields - set(entry.keys())}"
    )


def test_pipeline_index_entry_findings_path_exists(tmp_path):
    exit_code, index_path = _run(tmp_path)
    assert exit_code == 0

    entry = json.loads(index_path.read_text())[0]
    findings_path = Path(entry["findings_path"])
    assert findings_path.exists(), f"findings_path must point to an existing file: {findings_path}"


def test_pipeline_dataset_key_derived_from_filename(tmp_path):
    exit_code, index_path = _run(tmp_path)
    assert exit_code == 0

    entry = json.loads(index_path.read_text())[0]
    assert entry["dataset_key"] == derive_dataset_key(CLEAN_DATASET)


def test_pipeline_failed_run_does_not_create_index_entry(tmp_path):
    exit_code, index_path = _run(tmp_path, input_path=Path("nonexistent_file.csv"))

    assert exit_code == 1
    assert not index_path.exists(), "index.json must not be created for a failed run"
