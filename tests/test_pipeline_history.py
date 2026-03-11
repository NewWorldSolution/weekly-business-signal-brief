"""Integration tests — pipeline history registration (I6-3).

Verifies that pipeline.execute() registers completed runs in the history
index and that failed runs do not produce index entries.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

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

    # All keys present
    required_fields = {
        "run_id", "dataset_key", "input_file", "week_start",
        "week_end", "signal_count", "findings_path", "registered_at",
    }
    assert required_fields == set(entry.keys()), (
        f"Missing fields: {required_fields - set(entry.keys())}"
    )

    # Type and format assertions
    iso_date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    iso_datetime_re = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

    assert isinstance(entry["run_id"], str) and entry["run_id"]
    assert isinstance(entry["dataset_key"], str) and entry["dataset_key"]
    assert isinstance(entry["input_file"], str) and entry["input_file"]
    assert iso_date_re.match(entry["week_start"]), (
        f"week_start must be YYYY-MM-DD: {entry['week_start']}"
    )
    assert iso_date_re.match(entry["week_end"]), (
        f"week_end must be YYYY-MM-DD: {entry['week_end']}"
    )
    assert isinstance(entry["signal_count"], int), (
        f"signal_count must be int: {type(entry['signal_count'])}"
    )
    assert isinstance(entry["findings_path"], str) and entry["findings_path"]
    assert iso_datetime_re.match(entry["registered_at"]), (
        f"registered_at must be ISO datetime: {entry['registered_at']}"
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


def test_pipeline_register_run_error_propagates(tmp_path):
    """When register_run raises, pipeline must return exit code 1."""
    with patch("wbsb.pipeline.register_run", side_effect=ValueError("index corrupted")):
        exit_code, index_path = _run(tmp_path)

    assert exit_code == 1, "register_run failure must cause pipeline to return exit code 1"
    assert not index_path.exists(), "failed registration must not leave a partial index"


def test_pipeline_second_run_appends_index(tmp_path):
    """Two successive runs on the same dataset must produce two index entries."""
    exit_code_1, index_path = _run(tmp_path)
    assert exit_code_1 == 0

    exit_code_2, _ = _run(tmp_path)
    assert exit_code_2 == 0

    entries = json.loads(index_path.read_text())
    assert len(entries) == 2, f"Expected 2 entries after two runs, got {len(entries)}"
    assert entries[0]["run_id"] != entries[1]["run_id"], "Each run must have a unique run_id"


def test_pipeline_passes_trend_context_to_render(tmp_path, monkeypatch):
    """Pipeline must call render_llm with a trend_context keyword argument."""
    captured: list[dict] = []

    import wbsb.pipeline as pipeline_module
    original_render_llm = pipeline_module.render_llm

    def _capturing_render_llm(**kwargs):
        captured.append(kwargs)
        return original_render_llm(**kwargs)

    monkeypatch.setattr(pipeline_module, "render_llm", _capturing_render_llm)

    exit_code = pipeline_module.execute(
        input_path=CLEAN_DATASET,
        output_dir=tmp_path,
        llm_mode="full",
        llm_provider="anthropic",
        config_path=CONFIG_PATH,
        target_week=None,
    )

    # Pipeline may fall back gracefully (no API key in test env); exit code 0 either way
    assert exit_code == 0, f"Pipeline returned non-zero exit code: {exit_code}"
    assert len(captured) == 1, "render_llm must be called exactly once"
    assert "trend_context" in captured[0], (
        "render_llm must receive trend_context keyword argument"
    )
    assert isinstance(captured[0]["trend_context"], dict), (
        "trend_context must be a dict"
    )


def test_pipeline_compute_trends_called_with_before_week_start(tmp_path, monkeypatch):
    """compute_trends must be called with before_week_start=week_start.isoformat()."""
    import wbsb.pipeline as pipeline_module

    compute_calls: list[dict] = []
    original_compute_trends = pipeline_module.compute_trends

    def _capturing_compute_trends(history_reader, metric_ids, **kwargs):
        compute_calls.append({"metric_ids": metric_ids, **kwargs})
        return original_compute_trends(history_reader, metric_ids, **kwargs)

    monkeypatch.setattr(pipeline_module, "compute_trends", _capturing_compute_trends)

    exit_code = pipeline_module.execute(
        input_path=CLEAN_DATASET,
        output_dir=tmp_path,
        llm_mode="full",
        llm_provider="anthropic",
        config_path=CONFIG_PATH,
        target_week=None,
    )

    assert exit_code == 0
    assert len(compute_calls) == 1, "compute_trends must be called exactly once"
    call = compute_calls[0]
    assert "before_week_start" in call, (
        "compute_trends must receive before_week_start argument"
    )
    # before_week_start must be a valid ISO date string
    import re
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", call["before_week_start"]), (
        f"before_week_start must be YYYY-MM-DD, got: {call['before_week_start']}"
    )


def test_pipeline_compute_trends_error_continues_with_empty_context(tmp_path, monkeypatch):
    """When compute_trends raises, pipeline must still call render_llm with trend_context={}."""
    import wbsb.pipeline as pipeline_module

    def _raising_compute_trends(*a, **kw):
        raise RuntimeError("simulated trend failure")

    monkeypatch.setattr(pipeline_module, "compute_trends", _raising_compute_trends)

    render_calls: list[dict] = []
    original_render_llm = pipeline_module.render_llm

    def _capturing_render_llm(**kwargs):
        render_calls.append(kwargs)
        return original_render_llm(**kwargs)

    monkeypatch.setattr(pipeline_module, "render_llm", _capturing_render_llm)

    exit_code = pipeline_module.execute(
        input_path=CLEAN_DATASET,
        output_dir=tmp_path,
        llm_mode="full",
        llm_provider="anthropic",
        config_path=CONFIG_PATH,
        target_week=None,
    )

    assert exit_code == 0, "Pipeline must succeed even when compute_trends raises"
    assert len(render_calls) == 1, "render_llm must still be called after trend failure"
    assert render_calls[0]["trend_context"] == {}, (
        "trend_context must be {} when compute_trends raises"
    )
